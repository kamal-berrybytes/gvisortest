import os
import logging
import json
import tempfile
from datetime import datetime

try:
    from langchain.chat_models import ChatOpenAI
    from langchain.schema import HumanMessage, SystemMessage
    from langchain.prompts import ChatPromptTemplate, HumanMessagePromptTemplate
    LANGCHAIN_AVAILABLE = True
except ImportError:
    LANGCHAIN_AVAILABLE = False

try:
    import dspy
    DSPY_AVAILABLE = True
except ImportError:
    DSPY_AVAILABLE = False

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


FIBONACCI_PROMPT = """Generate a Python function that calculates Fibonacci numbers.
The function should:
1. Take an integer n as input
2. Return the nth Fibonacci number
3. Include proper error handling for invalid inputs
4. Be efficient and well-documented

Also generate unit tests using pytest that verify:
- fibonacci(0) returns 0
- fibonacci(1) returns 1
- fibonacci(10) returns 55
- fibonacci(20) returns 6765
- Invalid inputs raise appropriate exceptions

Return ONLY valid Python code, no explanations."""


class CodeGenerationAgent:
    def __init__(self, provider=None):
        self.provider = provider or os.environ.get('AGENT_PROVIDER', 'langchain')
        self.model = os.environ.get('AGENT_MODEL', 'gpt-4')
        self.api_key = os.environ.get('OPENAI_API_KEY', '')
        
        if self.provider == 'dspyo' and DSPY_AVAILABLE:
            self._init_dspy()
        elif LANGCHAIN_AVAILABLE:
            self._init_langchain()
        else:
            logger.warning("No LLM provider available, using fallback generation")
            self.llm = None
    
    def _init_langchain(self):
        if not self.api_key:
            logger.warning("No OpenAI API key, using fallback generation")
            self.llm = None
            return
        
        try:
            self.llm = ChatOpenAI(
                model=self.model,
                api_key=self.api_key,
                temperature=0.2
            )
            logger.info(f"Initialized LangChain with model {self.model}")
        except Exception as e:
            logger.warning(f"Failed to initialize LangChain: {e}")
            self.llm = None
    
    def _init_dspy(self):
        if not self.api_key:
            logger.warning("No OpenAI API key for DSPy")
            self.llm = None
            return
        
        try:
            dspy.configure(lm=dspy.OpenAI(model=self.model, api_key=self.api_key))
            logger.info(f"Initialized DSPy with model {self.model}")
        except Exception as e:
            logger.warning(f"Failed to initialize DSPy: {e}")
            self.llm = None
    
    def generate_fibonacci_code(self):
        if self.llm:
            return self._generate_with_llm()
        return self._generate_fallback()
    
    def _generate_with_llm(self):
        try:
            if self.provider == 'dspyo' and DSPY_AVAILABLE:
                return self._generate_with_dspy()
            return self._generate_with_langchain()
        except Exception as e:
            logger.error(f"LLM generation failed: {e}")
            return self._generate_fallback()
    
    def _generate_with_langchain(self):
        messages = [
            SystemMessage(content="You are a code generation assistant. Generate only valid Python code."),
            HumanMessage(content=FIBONACCI_PROMPT)
        ]
        
        response = self.llm(messages)
        code = response.content
        
        return self._save_code(code)
    
    def _generate_with_dspy(self):
        class GenerateCode(dspy.Signature):
            """Generate Python code for Fibonacci calculation"""
            prompt = dspy.InputField(description="The code generation request")
            code = dspy.OutputField(description="Generated Python code")
        
        generate_code = dspy.Predict(GenerateCode)
        response = generate_code(prompt=FIBONACCI_PROMPT)
        
        return self._save_code(response.code)
    
    def _generate_fallback(self):
        code = '''"""Fibonacci implementation with unit tests"""
import pytest

def fibonacci(n: int) -> int:
    """Calculate the nth Fibonacci number.
    
    Args:
        n: The position in the Fibonacci sequence (0-indexed)
        
    Returns:
        The nth Fibonacci number
        
    Raises:
        ValueError: If n is negative
        TypeError: If n is not an integer
    """
    if not isinstance(n, int):
        raise TypeError(f"Expected int, got {type(n).__name__}")
    if n < 0:
        raise ValueError("n must be non-negative")
    if n == 0:
        return 0
    if n == 1:
        return 1
    
    a, b = 0, 1
    for _ in range(2, n + 1):
        a, b = b, a + b
    return b


class TestFibonacci:
    """Unit tests for Fibonacci function"""
    
    def test_fibonacci_0(self):
        assert fibonacci(0) == 0
    
    def test_fibonacci_1(self):
        assert fibonacci(1) == 1
    
    def test_fibonacci_10(self):
        assert fibonacci(10) == 55
    
    def test_fibonacci_20(self):
        assert fibonacci(20) == 6765
    
    def test_fibonacci_negative(self):
        with pytest.raises(ValueError):
            fibonacci(-1)
    
    def test_fibonacci_invalid_type(self):
        with pytest.raises(TypeError):
            fibonacci("5")
    
    def test_fibonacci_large(self):
        assert fibonacci(50) == 12586269025


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
'''
        return self._save_code(code)
    
    def _save_code(self, code):
        output_dir = os.environ.get('CODE_OUTPUT_DIR', '/tmp/generated')
        os.makedirs(output_dir, exist_ok=True)
        
        code_file = os.path.join(output_dir, 'fibonacci.py')
        with open(code_file, 'w') as f:
            f.write(code)
        
        logger.info(f"Code saved to {code_file}")
        
        metadata = {
            'timestamp': str(datetime.now()),
            'provider': self.provider,
            'model': self.model
        }
        metadata_file = os.path.join(output_dir, 'metadata.json')
        with open(metadata_file, 'w') as f:
            json.dump(metadata, f)
        
        return code


if __name__ == '__main__':
    agent = CodeGenerationAgent()
    code = agent.generate_fibonacci_code()
    print(code)
