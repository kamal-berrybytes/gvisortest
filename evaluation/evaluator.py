import os
import sys
import json
import logging
import subprocess
import re
import inspect

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


class CodeEvaluator:
    """Evaluates generated code against test cases"""
    
    def __init__(self):
        self.output_dir = os.environ.get('CODE_OUTPUT_DIR', '/tmp/generated')
        self.timeout = int(os.environ.get('EXECUTION_TIMEOUT', '30'))
        self.use_kubernetes = os.environ.get('KUBERNETES_MODE', 'true').lower() == 'true'
    
    def evaluate(self, code, execution_output=None, test_cases=None):
        logger.info("Evaluating code")
        
        if test_cases is None:
            test_cases = self._auto_generate_tests(code)
        
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
    
    def _auto_generate_tests(self, code):
        test_cases = []
        
        function_names = self._extract_functions(code)
        
        for func_name in function_names:
            test_cases.extend(self._generate_tests_for_function(code, func_name))
        
        if not test_cases:
            test_cases = [
                {'name': 'test_execution', 'input': None, 'expected': None, 'check': 'runs'}
            ]
        
        return test_cases
    
    def _extract_functions(self, code):
        functions = []
        
        pattern = r'def\s+([a-zA-Z_][a-zA-Z0-9_]*)\s*\('
        matches = re.findall(pattern, code)
        functions.extend(matches)
        
        class_pattern = r'class\s+([a-zA-Z_][a-zA-Z0-9_]*)\s*[:\(]'
        classes = re.findall(class_pattern, code)
        
        return functions
    
    def _generate_tests_for_function(self, code, func_name):
        tests = []
        
        if 'fibonacci' in func_name.lower():
            tests = [
                {'name': f'{func_name}_0', 'input': 0, 'expected': 0},
                {'name': f'{func_name}_1', 'input': 1, 'expected': 1},
                {'name': f'{func_name}_10', 'input': 10, 'expected': 55},
                {'name': f'{func_name}_20', 'input': 20, 'expected': 6765},
            ]
        elif 'reverse' in func_name.lower() and 'string' in code.lower():
            tests = [
                {'name': f'{func_name}_abc', 'input': 'abc', 'expected': 'cba'},
                {'name': f'{func_name}_empty', 'input': '', 'expected': ''},
                {'name': f'{func_name}_single', 'input': 'a', 'expected': 'a'},
            ]
        elif 'sort' in func_name.lower():
            tests = [
                {'name': f'{func_name}_unsorted', 'input': [3, 1, 2], 'expected': [1, 2, 3]},
                {'name': f'{func_name}_empty', 'input': [], 'expected': []},
                {'name': f'{func_name}_single', 'input': [1], 'expected': [1]},
            ]
        elif 'factorial' in func_name.lower():
            tests = [
                {'name': f'{func_name}_0', 'input': 0, 'expected': 1},
                {'name': f'{func_name}_1', 'input': 1, 'expected': 1},
                {'name': f'{func_name}_5', 'input': 5, 'expected': 120},
            ]
        elif 'prime' in func_name.lower():
            tests = [
                {'name': f'{func_name}_2', 'input': 2, 'expected': True},
                {'name': f'{func_name}_3', 'input': 3, 'expected': True},
                {'name': f'{func_name}_4', 'input': 4, 'expected': False},
                {'name': f'{func_name}_17', 'input': 17, 'expected': True},
            ]
        else:
            tests = [
                {'name': f'{func_name}_basic', 'input': None, 'expected': None, 'check': 'runs'}
            ]
        
        return tests
    
    def evaluate_with_custom_tests(self, code, custom_tests):
        return self.evaluate(code, test_cases=custom_tests)
    
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
            'name': test_case.get('name', 'test'),
            'input': test_case.get('input'),
            'expected': test_case.get('expected'),
            'passed': False,
            'actual': None,
            'error': None
        }
        
        try:
            compiled = compile(code, '<generated>', 'exec')
            namespace = {'__name__': '__test__'}
            exec(compiled, namespace)
            
            if test_case.get('check') == 'runs':
                result['passed'] = True
                result['actual'] = 'executed successfully'
            else:
                func_name = test_case['name'].split('_')[0]
                if len(test_case['name'].split('_')) > 1:
                    func_name = test_case['name'].rsplit('_', 1)[0].rsplit('_', 1)[0]
                
                for name in namespace:
                    if not name.startswith('_') and callable(namespace[name]):
                        func = namespace[name]
                        if callable(func):
                            try:
                                input_val = test_case['input']
                                actual = func(input_val)
                                result['actual'] = actual
                                
                                if test_case.get('expected') is not None:
                                    result['passed'] = (actual == test_case['expected'])
                                else:
                                    result['passed'] = True
                                break
                            except Exception:
                                continue
                else:
                    result['error'] = 'No callable function found'
                    
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
    result = evaluator.evaluate(sample_code)
    print(json.dumps(result, indent=2))