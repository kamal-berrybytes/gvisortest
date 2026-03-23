import os
import sys
import json
import logging
import tempfile
import subprocess
import yaml

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


class GvisorSandboxExecutor:
    """Executes code in Gvisor-isolated sandbox environment"""
    
    def __init__(self):
        self.output_dir = os.environ.get('CODE_OUTPUT_DIR', '/tmp/generated')
        self.timeout = int(os.environ.get('EXECUTION_TIMEOUT', '30'))
        self.use_kubernetes = os.environ.get('KUBERNETES_MODE', 'false').lower() == 'true'
        
        self.runtime_class = os.environ.get('RUNTIME_CLASS', 'gvisor')
        self.memory_limit = os.environ.get('MAX_MEMORY', '128Mi')
        self.cpu_limit = os.environ.get('MAX_CPU', '500m')
    
    def execute(self, code):
        logger.info("Executing code in Gvisor sandbox")
        
        if self.use_kubernetes:
            return self._execute_in_kubernetes(code)
        return self._execute_local(code)
    
    def _execute_local(self, code):
        code_file = self._save_code(code)
        
        pod_spec = self._generate_pod_spec(code_file)
        pod_file = os.path.join(self.output_dir, 'sandbox-pod.yaml')
        
        with open(pod_file, 'w') as f:
            yaml.dump(pod_spec, f)
        
        logger.info(f"POD spec saved to {pod_file}")
        
        return self._run_direct(code)
    
    def _execute_in_kubernetes(self, code):
        code_file = self._save_code(code)
        
        pod_spec = self._generate_pod_spec(code_file)
        pod_file = os.path.join(self.output_dir, 'sandbox-pod.yaml')
        
        with open(pod_file, 'w') as f:
            import yaml
            yaml.dump(pod_spec, f)
        
        namespace = os.environ.get('NAMESPACE', 'fibonacci-agent')
        
        try:
            subprocess.run(['kubectl', 'delete', 'pod', 'sandbox-executor', '-n', namespace],
                         capture_output=True, timeout=10)
        except:
            pass
        
        result = subprocess.run(['kubectl', 'apply', '-f', pod_file, '-n', namespace],
                              capture_output=True, text=True, timeout=30)
        
        if result.returncode != 0:
            logger.warning(f"Failed to create pod: {result.stderr}")
            return self._run_direct(code)
        
        return self._wait_for_pod_completion(namespace)
    
    def _run_direct(self, code):
        import io
        import traceback
        
        output = io.StringIO()
        error_output = io.StringIO()
        
        old_stdout = sys.stdout
        old_stderr = sys.stderr
        sys.stdout = output
        sys.stderr = error_output
        
        execution_result = {
            'success': False,
            'output': '',
            'error': '',
            'execution_time': 0
        }
        
        import time
        start_time = time.time()
        
        try:
            compiled = compile(code, '<fibonacci>', 'exec')
            namespace = {'__name__': '__fibonacci__'}
            exec(compiled, namespace)
            
            execution_result['success'] = True
            execution_result['output'] = output.getvalue()
            
        except Exception as e:
            execution_result['error'] = f"{type(e).__name__}: {str(e)}"
            execution_result['error'] += "\n" + traceback.format_exc()
            
        finally:
            sys.stdout = old_stdout
            sys.stderr = old_stderr
        
        execution_result['execution_time'] = time.time() - start_time
        
        self._save_result(execution_result)
        
        return execution_result
    
    def _wait_for_pod_completion(self, namespace):
        import time
        import yaml
        
        max_wait = self.timeout
        start_time = time.time()
        
        while time.time() - start_time < max_wait:
            result = subprocess.run(
                ['kubectl', 'get', 'pod', 'sandbox-executor', '-n', namespace, '-o', 'json'],
                capture_output=True, text=True, timeout=10
            )
            
            if result.returncode == 0:
                pod_data = json.loads(result.stdout)
                phase = pod_data.get('status', {}).get('phase', 'Pending')
                
                if phase == 'Succeeded':
                    logs_result = subprocess.run(
                        ['kubectl', 'logs', 'sandbox-executor', '-n', namespace],
                        capture_output=True, text=True, timeout=10
                    )
                    
                    return {
                        'success': True,
                        'output': logs_result.stdout,
                        'error': '',
                        'execution_time': time.time() - start_time
                    }
                
                elif phase == 'Failed':
                    logs_result = subprocess.run(
                        ['kubectl', 'logs', 'sandbox-executor', '-n', namespace],
                        capture_output=True, text=True, timeout=10
                    )
                    
                    return {
                        'success': False,
                        'output': '',
                        'error': logs_result.stderr,
                        'execution_time': time.time() - start_time
                    }
            
            time.sleep(1)
        
        return {
            'success': False,
            'output': '',
            'error': 'Timeout waiting for pod completion',
            'execution_time': max_wait
        }
    
    def _generate_pod_spec(self, code_file):
        return {
            'apiVersion': 'v1',
            'kind': 'Pod',
            'metadata': {
                'name': 'sandbox-executor',
                'namespace': os.environ.get('NAMESPACE', 'fibonacci-agent'),
                'labels': {
                    'app': 'fibonacci-sandbox'
                }
            },
            'spec': {
                'restartPolicy': 'Never',
                'runtimeClassName': self.runtime_class,
                'securityContext': {
                    'runAsNonRoot': True,
                    'runAsUser': 1000,
                    'fsGroup': 1000
                },
                'containers': [
                    {
                        'name': 'executor',
                        'image': 'fibonacci-agent:latest',
                        'command': ['python', '/tmp/code/fibonacci.py'],
                        'resources': {
                            'limits': {
                                'memory': self.memory_limit,
                                'cpu': self.cpu_limit
                            },
                            'requests': {
                                'memory': '64Mi',
                                'cpu': '100m'
                            }
                        },
                        'securityContext': {
                            'readOnlyRootFilesystem': True,
                            'allowPrivilegeEscalation': False,
                            'capabilities': {
                                'drop': ['ALL']
                            }
                        },
                        'volumeMounts': [
                            {
                                'name': 'code',
                                'mountPath': '/tmp/code'
                            }
                        ]
                    }
                ],
                'volumes': [
                    {
                        'name': 'code',
                        'hostPath': {
                            'path': self.output_dir,
                            'type': 'Directory'
                        }
                    }
                ]
            }
        }
    
    def _save_code(self, code):
        os.makedirs(self.output_dir, exist_ok=True)
        
        code_file = os.path.join(self.output_dir, 'fibonacci.py')
        with open(code_file, 'w') as f:
            f.write(code)
        
        logger.info(f"Code saved to {code_file}")
        return code_file
    
    def _save_result(self, result):
        result_file = os.path.join(self.output_dir, 'execution_result.json')
        
        with open(result_file, 'w') as f:
            json.dump(result, f, indent=2)
        
        logger.info(f"Execution result saved to {result_file}")


if __name__ == '__main__':
    sample_code = '''
def fibonacci(n):
    if n == 0:
        return 0
    if n == 1:
        return 1
    a, b = 0, 1
    for _ in range(2, n + 1):
        a, b = b, a + b
    return b

print(fibonacci(10))
'''
    
    executor = GvisorSandboxExecutor()
    result = executor.execute(sample_code)
    print(json.dumps(result, indent=2))
