"""
Code Scanner using OpenRouter API
Validates user code for security and ML relevance before execution
"""

import os
import json
import requests
from typing import Dict, List, Optional
import ast


class CodeScanner:
    """Scan Python code for security issues and ML relevance using LLM"""
    
    def __init__(self, api_key: Optional[str] = None):
        """
        Initialize code scanner with OpenRouter API key
        
        Args:
            api_key: OpenRouter API key (or set OPENROUTER_API_KEY env var)
        """
        self.api_key = api_key or os.environ.get('OPENROUTER_API_KEY')
        self.api_url = "https://openrouter.ai/api/v1/chat/completions"
        
        if not self.api_key:
            raise ValueError("OpenRouter API key required (set OPENROUTER_API_KEY env var)")
    
    def scan_code(self, code: str, competition_id: str) -> Dict:
        """
        Scan code for security issues and ML relevance
        
        Args:
            code: Python code to scan
            competition_id: Competition this code is for
            
        Returns:
            {
                'safe': bool,
                'relevant': bool,
                'issues': List[str],
                'confidence': float,
                'explanation': str
            }
        """
        # First do quick static checks
        static_issues = self._static_analysis(code)
        
        # If obvious issues found, don't call API
        if static_issues.get('critical'):
            return {
                'safe': False,
                'relevant': True,  # Assume relevant for now
                'issues': static_issues['critical'],
                'confidence': 1.0,
                'explanation': 'Static analysis detected critical security issues'
            }
        
        # Call LLM for deep analysis
        llm_result = self._llm_analysis(code, competition_id)
        
        # Combine results
        all_issues = static_issues.get('warnings', []) + llm_result.get('issues', [])
        
        return {
            'safe': llm_result.get('safe', False) and not static_issues.get('critical'),
            'relevant': llm_result.get('relevant', True),
            'issues': all_issues,
            'confidence': llm_result.get('confidence', 0.5),
            'explanation': llm_result.get('explanation', '')
        }
    
    def _static_analysis(self, code: str) -> Dict:
        """
        Quick static analysis for obvious issues
        
        Returns:
            {
                'critical': List[str],  # Immediate fails
                'warnings': List[str]   # Suspicious but not blocking
            }
        """
        critical = []
        warnings = []
        
        try:
            tree = ast.parse(code)
        except SyntaxError as e:
            return {'critical': [f'Syntax error: {e}']}
        
        # Check for dangerous imports/calls
        dangerous_imports = {
            'os.system': 'System command execution',
            'subprocess': 'Subprocess execution',
            'eval': 'Dynamic code evaluation',
            'exec': 'Dynamic code execution',
            '__import__': 'Dynamic imports',
            'compile': 'Code compilation',
            'open': 'File operations',  # Warning only
            'socket': 'Network access',
            'urllib': 'Network access',
            'requests': 'Network access',
            'paramiko': 'SSH access',
            'ftplib': 'FTP access',
        }
        
        for node in ast.walk(tree):
            # Check function calls
            if isinstance(node, ast.Call):
                if isinstance(node.func, ast.Name):
                    func_name = node.func.id
                    if func_name in ['eval', 'exec', 'compile', '__import__']:
                        critical.append(f"Dangerous function: {func_name}()")
                    elif func_name == 'open':
                        warnings.append("File operations detected - ensure using provided paths")
                
                elif isinstance(node.func, ast.Attribute):
                    if node.func.attr == 'system':
                        critical.append("System command execution detected")
            
            # Check imports
            elif isinstance(node, ast.Import):
                for alias in node.names:
                    if alias.name in ['os', 'subprocess', 'socket', 'paramiko']:
                        warnings.append(f"Import of '{alias.name}' - will be reviewed")
            
            elif isinstance(node, ast.ImportFrom):
                if node.module in ['os', 'subprocess', 'socket']:
                    for alias in node.names:
                        if alias.name in ['system', 'popen', 'Popen', 'socket']:
                            critical.append(f"Import of dangerous function: {node.module}.{alias.name}")
        
        return {
            'critical': critical,
            'warnings': warnings
        }
    
    def _llm_analysis(self, code: str, competition_id: str) -> Dict:
        """
        Use LLM to analyze code for security and relevance
        
        Returns:
            {
                'safe': bool,
                'relevant': bool,
                'issues': List[str],
                'confidence': float,
                'explanation': str
            }
        """
        prompt = self._build_prompt(code, competition_id)
        
        try:
            response = requests.post(
                self.api_url,
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json"
                },
                json={
                    "model": "anthropic/claude-3.5-sonnet",  # Or another model
                    "messages": [
                        {
                            "role": "system",
                            "content": "You are a security expert analyzing Python code for ML competitions."
                        },
                        {
                            "role": "user",
                            "content": prompt
                        }
                    ],
                    "temperature": 0.1,  # Low temperature for consistent analysis
                    "max_tokens": 1000
                },
                timeout=30
            )
            
            response.raise_for_status()
            result = response.json()
            
            # Parse LLM response
            content = result['choices'][0]['message']['content']
            return self._parse_llm_response(content)
            
        except requests.exceptions.RequestException as e:
            # If API fails, err on side of caution
            return {
                'safe': False,
                'relevant': True,
                'issues': [f'Unable to complete security scan: {str(e)}'],
                'confidence': 0.0,
                'explanation': 'Security scan failed - manual review required'
            }
    
    def _build_prompt(self, code: str, competition_id: str) -> str:
        """Build prompt for LLM analysis"""
        return f"""Analyze the following Python code submission for a machine learning competition.

Competition ID: {competition_id}

Code to analyze:
```python
{code}
```

Please analyze for:
1. SECURITY: Any malicious code, system access, network calls, file operations outside /tmp
2. RELEVANCE: Is this legitimate ML/data science code for a competition?
3. RESOURCE ABUSE: Infinite loops, excessive memory allocation, fork bombs

Respond in JSON format:
{{
    "safe": true/false,
    "relevant": true/false,
    "issues": ["list of specific issues found"],
    "confidence": 0.0-1.0,
    "explanation": "brief explanation of your assessment"
}}

Only mark as safe=true if code:
- Contains no system/network access
- Has no malicious intent
- Follows ML competition patterns
- Won't abuse resources

Only mark as relevant=true if code:
- Appears to be legitimate ML/data science
- Fits pattern of competition submission
- Not random/test code"""
    
    def _parse_llm_response(self, content: str) -> Dict:
        """Parse LLM response into structured format"""
        try:
            # Try to extract JSON from response
            # LLM might wrap in markdown code blocks
            if '```json' in content:
                json_str = content.split('```json')[1].split('```')[0].strip()
            elif '```' in content:
                json_str = content.split('```')[1].split('```')[0].strip()
            else:
                json_str = content.strip()
            
            result = json.loads(json_str)
            
            # Validate required fields
            return {
                'safe': result.get('safe', False),
                'relevant': result.get('relevant', False),
                'issues': result.get('issues', []),
                'confidence': float(result.get('confidence', 0.5)),
                'explanation': result.get('explanation', '')
            }
        
        except (json.JSONDecodeError, KeyError, ValueError) as e:
            # If parsing fails, err on side of caution
            return {
                'safe': False,
                'relevant': True,
                'issues': ['Unable to parse security analysis'],
                'confidence': 0.0,
                'explanation': f'Analysis parsing failed: {str(e)}'
            }
    
    def quick_check(self, code: str) -> Dict:
        """
        Fast check using only static analysis (no API call)
        Use for rate-limited scenarios
        """
        static_result = self._static_analysis(code)
        
        has_critical = bool(static_result.get('critical'))
        
        return {
            'safe': not has_critical,
            'relevant': True,  # Cannot determine without LLM
            'issues': static_result.get('critical', []) + static_result.get('warnings', []),
            'confidence': 0.7 if not has_critical else 1.0,
            'explanation': 'Static analysis only (LLM check skipped)'
        }


# Convenience function for use in API
def scan_code(code: str, competition_id: str, quick: bool = False) -> Dict:
    """
    Scan code for security issues
    
    Args:
        code: Python code to scan
        competition_id: Competition ID
        quick: If True, use only static analysis (no API call)
        
    Returns:
        Scan results dictionary
    """
    scanner = CodeScanner()
    
    if quick:
        return scanner.quick_check(code)
    else:
        return scanner.scan_code(code, competition_id)


if __name__ == "__main__":
    # Test the scanner
    import sys
    
    if len(sys.argv) < 2:
        print("Usage: python3 code_scanner.py <code_file>")
        sys.exit(1)
    
    with open(sys.argv[1]) as f:
        code = f.read()
    
    print("Scanning code...")
    result = scan_code(code, "test-competition")
    
    print(json.dumps(result, indent=2))
    
    if not result['safe']:
        print("\n⚠️  CODE REJECTED")
        sys.exit(1)
    else:
        print("\n✓ CODE APPROVED")

