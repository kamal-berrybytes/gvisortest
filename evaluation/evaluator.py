import os
import sys
import json
import logging
import subprocess

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


class CodeEvaluator:
    """Evaluates generated code against test cases"""
    
    def __init__(self):
        self.output_dir = os.environ.get('CODE_OUTPUT_DIR', '/tmp/generated')
        self.timeout = int(os.environ.get('EXECUTION_TIMEOUT', '30'))
        self.use_kubernetes = os.environ.get('KUBERNETES_MODE', 'false').lower() == 'true'
    
    def evaluate(self, code, execution_output):
        logger.info("Evaluating code")
        
        test_cases = self._get_test_cases()
        
        results = []
        all_passed = True
        
        for test_case in test_cases:
            result = self._run_test(code, test_case)
            results.append(result)
            if not result['passed']:
                all_passed = False
        
        evaluation = {
            'passed': all_passed,
            'total_tests': len(test_cases),
            'passed_tests': sum(1 for r in results if r['passed']),
            'failed_tests': sum(1 for r in results if not r['passed']),
            'test_results': results
        }
        
        self._save_evaluation(evaluation)
        
        logger.info(f"Evaluation complete. Passed: {evaluation['passed_tests']}/{evaluation['total_tests']}")
        
        return evaluation
    
    def _get_test_cases(self):
        return [
            {'name': 'test_fibonacci_0', 'input': 0, 'expected': 0},
            {'name': 'test_fibonacci_1', 'input': 1, 'expected': 1},
            {'name': 'test_fibonacci_10', 'input': 10, 'expected': 55},
            {'name': 'test_fibonacci_20', 'input': 20, 'expected': 6765},
            {'name': 'test_fibonacci_50', 'input': 50, 'expected': 12586269025},
        ]
    
    def _run_test(self, code, test_case):
        import io
        import traceback
        
        output = io.StringIO()
        error_output = io.StringIO()
        
        old_stdout = sys.stdout
        old_stderr = sys.stderr
        sys.stdout = output
        sys.stderr = error_output
        
        result = {
            'name': test_case['name'],
            'input': test_case['input'],
            'expected': test_case['expected'],
            'passed': False,
            'actual': None,
            'error': None
        }
        
        try:
            compiled = compile(code, '<fibonacci>', 'exec')
            namespace = {'__name__': '__fibonacci__'}
            exec(compiled, namespace)
            
            if 'fibonacci' in namespace:
                fib_func = namespace['fibonacci']
                actual = fib_func(test_case['input'])
                result['actual'] = actual
                result['passed'] = (actual == test_case['expected'])
            else:
                result['error'] = 'fibonacci function not found in code'
                
        except Exception as e:
            result['error'] = f"{type(e).__name__}: {str(e)}"
            result['passed'] = False
            
        finally:
            sys.stdout = old_stdout
            sys.stderr = old_stderr
        
        return result
    
    def _save_evaluation(self, evaluation):
        eval_file = os.path.join(self.output_dir, 'evaluation_result.json')
        
        with open(eval_file, 'w') as f:
            json.dump(evaluation, f, indent=2)
        
        logger.info(f"Evaluation result saved to {eval_file}")
    
    def _run_pytest(self, code_file):
        try:
            result = subprocess.run(
                ['pytest', code_file, '-v', '--tb=short'],
                capture_output=True,
                text=True,
                timeout=self.timeout
            )
            
            return {
                'passed': result.returncode == 0,
                'output': result.stdout,
                'error': result.stderr
            }
        except subprocess.TimeoutExpired:
            return {
                'passed': False,
                'output': '',
                'error': 'Test execution timeout'
            }
        except Exception as e:
            return {
                'passed': False,
                'output': '',
                'error': str(e)
            }


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
'''
    
    evaluator = CodeEvaluator()
    result = evaluator.evaluate(sample_code, '')
    print(json.dumps(result, indent=2))
