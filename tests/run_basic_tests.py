#!/usr/bin/env python3
"""
GPU Job Queue Server - Test Suite
Phase 1: Basic Functionality Tests
"""

import requests
import time
import json
import sys
from typing import Dict, Any

BASE_URL = "http://localhost:8001"
PASS = "\033[92m✓\033[0m"
FAIL = "\033[91m✗\033[0m"
WARN = "\033[93m⚠\033[0m"

class TestResults:
    def __init__(self):
        self.total = 0
        self.passed = 0
        self.failed = 0
        self.errors = []
    
    def record_pass(self, test_name):
        self.total += 1
        self.passed += 1
        print(f"{PASS} {test_name}")
    
    def record_fail(self, test_name, reason):
        self.total += 1
        self.failed += 1
        self.errors.append((test_name, reason))
        print(f"{FAIL} {test_name}: {reason}")
    
    def summary(self):
        print("\n" + "=" * 60)
        print(f"Test Results: {self.passed}/{self.total} passed")
        if self.failed > 0:
            print(f"\nFailed Tests ({self.failed}):")
            for name, reason in self.errors:
                print(f"  - {name}: {reason}")
        print("=" * 60)
        return self.failed == 0

results = TestResults()

def submit_job(code: str, config: Dict[str, Any], timeout: int = 60) -> Dict:
    """Helper to submit a job"""
    files = {
        'code': ('test.py', code, 'text/x-python'),
        'config_file': ('config.yaml', format_yaml(config), 'text/yaml')
    }
    try:
        response = requests.post(f"{BASE_URL}/api/submit", files=files, timeout=timeout)
        return {
            'status_code': response.status_code,
            'data': response.json() if response.ok else None,
            'text': response.text
        }
    except Exception as e:
        return {'status_code': 0, 'error': str(e)}

def format_yaml(config: Dict[str, Any]) -> str:
    """Convert dict to YAML string"""
    lines = []
    for key, value in config.items():
        if isinstance(value, str):
            lines.append(f'{key}: "{value}"')
        else:
            lines.append(f'{key}: {value}')
    return '\n'.join(lines)

def get_status(job_id: str) -> Dict:
    """Get job status"""
    try:
        response = requests.get(f"{BASE_URL}/api/status/{job_id}")
        return {'status_code': response.status_code, 'data': response.json() if response.ok else None}
    except Exception as e:
        return {'status_code': 0, 'error': str(e)}

def get_results(job_id: str) -> Dict:
    """Get job results"""
    try:
        response = requests.get(f"{BASE_URL}/api/results/{job_id}")
        return {'status_code': response.status_code, 'data': response.json() if response.ok else None}
    except Exception as e:
        return {'status_code': 0, 'error': str(e)}

# ============================================================
# 1. AUTHENTICATION TESTS
# ============================================================

def test_1_1_valid_auth():
    """Test 1.1: Valid token authentication"""
    code = 'print("Hello GPU!")'
    config = {
        'user_id': 'sarang',
        'token': 'sarang',
        'competition_id': 'test',
        'project_id': 'test',
        'expected_time': 10
    }
    response = submit_job(code, config)
    
    if response['status_code'] == 200 and response['data']:
        results.record_pass("1.1 Valid Authentication")
    else:
        results.record_fail("1.1 Valid Authentication", f"Status {response['status_code']}")

def test_1_2_invalid_token():
    """Test 1.2: Invalid token should fail"""
    code = 'print("Hello")'
    config = {
        'user_id': 'sarang',
        'token': 'WRONG_TOKEN',
        'competition_id': 'test',
        'project_id': 'test',
        'expected_time': 10
    }
    response = submit_job(code, config, timeout=10)
    
    if response['status_code'] == 401:
        results.record_pass("1.2 Invalid Token Rejection")
    else:
        results.record_fail("1.2 Invalid Token Rejection", f"Expected 401, got {response['status_code']}")

def test_1_3_missing_token():
    """Test 1.3: Missing token field"""
    code = 'print("Hello")'
    config = {
        'user_id': 'sarang',
        'competition_id': 'test',
        'project_id': 'test',
        'expected_time': 10
    }
    response = submit_job(code, config, timeout=10)
    
    if response['status_code'] == 400:
        results.record_pass("1.3 Missing Token Detection")
    else:
        results.record_fail("1.3 Missing Token Detection", f"Expected 400, got {response['status_code']}")

# ============================================================
# 2. JOB SUBMISSION TESTS
# ============================================================

def test_2_1_valid_job():
    """Test 2.1: Valid job execution"""
    code = 'print("Test passed")'
    config = {
        'user_id': 'sarang',
        'token': 'sarang',
        'competition_id': 'test',
        'project_id': 'test',
        'expected_time': 10
    }
    response = submit_job(code, config)
    
    if response['status_code'] == 200:
        data = response['data']
        if data.get('status') == 'completed' and 'Test passed' in data.get('stdout', ''):
            results.record_pass("2.1 Valid Job Execution")
        else:
            results.record_fail("2.1 Valid Job Execution", f"Job status: {data.get('status')}")
    else:
        results.record_fail("2.1 Valid Job Execution", f"Status {response['status_code']}")

def test_2_2_syntax_error():
    """Test 2.2: Python syntax error handling"""
    code = 'print("Missing quote'
    config = {
        'user_id': 'sarang',
        'token': 'sarang',
        'competition_id': 'test',
        'project_id': 'test',
        'expected_time': 10
    }
    response = submit_job(code, config)
    
    if response['status_code'] == 200:
        data = response['data']
        # Should complete with non-zero exit code and error in stderr
        if data.get('status') == 'completed' and data.get('exit_code', 0) != 0:
            results.record_pass("2.2 Syntax Error Captured")
        else:
            results.record_fail("2.2 Syntax Error Captured", f"Exit code: {data.get('exit_code')}, Status: {data.get('status')}")
    else:
        results.record_fail("2.2 Syntax Error Captured", f"Status {response['status_code']}")

def test_2_3_runtime_error():
    """Test 2.3: Runtime error handling"""
    code = '''
x = 1 / 0
print("Should not reach here")
'''
    config = {
        'user_id': 'sarang',
        'token': 'sarang',
        'competition_id': 'test',
        'project_id': 'test',
        'expected_time': 10
    }
    response = submit_job(code, config)
    
    if response['status_code'] == 200:
        data = response['data']
        # Should complete with non-zero exit code
        if data.get('status') == 'completed' and data.get('exit_code', 0) != 0:
            results.record_pass("2.3 Runtime Error Captured")
        else:
            results.record_fail("2.3 Runtime Error Captured", f"Exit code: {data.get('exit_code')}, Status: {data.get('status')}")
    else:
        results.record_fail("2.3 Runtime Error Captured", f"Status {response['status_code']}")

def test_2_4_empty_script():
    """Test 2.4: Empty script handling"""
    code = '# Empty script\npass'
    config = {
        'user_id': 'sarang',
        'token': 'sarang',
        'competition_id': 'test',
        'project_id': 'test',
        'expected_time': 10
    }
    response = submit_job(code, config)
    
    if response['status_code'] == 200:
        data = response['data']
        if data.get('status') == 'completed' and data.get('exit_code') == 0:
            results.record_pass("2.4 Empty Script Handling")
        else:
            results.record_fail("2.4 Empty Script Handling", f"Status: {data.get('status')}")
    else:
        results.record_fail("2.4 Empty Script Handling", f"Status {response['status_code']}")

# ============================================================
# 3. API ENDPOINT TESTS
# ============================================================

def test_3_1_status_nonexistent():
    """Test 3.1: Status of non-existent job"""
    response = get_status("00000000-0000-0000-0000-000000000000")
    
    if response['status_code'] == 404:
        results.record_pass("3.1 Non-existent Job 404")
    else:
        results.record_fail("3.1 Non-existent Job 404", f"Expected 404, got {response['status_code']}")

def test_3_2_list_jobs():
    """Test 3.2: List jobs endpoint"""
    try:
        response = requests.get(f"{BASE_URL}/api/jobs?limit=5")
        if response.status_code == 200:
            data = response.json()
            if 'jobs' in data:
                results.record_pass("3.2 List Jobs")
            else:
                results.record_fail("3.2 List Jobs", "Missing 'jobs' key")
        else:
            results.record_fail("3.2 List Jobs", f"Status {response.status_code}")
    except Exception as e:
        results.record_fail("3.2 List Jobs", str(e))

def test_3_3_node_stats():
    """Test 3.3: Node statistics endpoint"""
    try:
        response = requests.get(f"{BASE_URL}/api/nodes")
        if response.status_code == 200:
            data = response.json()
            if 'nodes' in data and len(data['nodes']) > 0:
                results.record_pass("3.3 Node Statistics")
            else:
                results.record_fail("3.3 Node Statistics", "Missing nodes data")
        else:
            results.record_fail("3.3 Node Statistics", f"Status {response.status_code}")
    except Exception as e:
        results.record_fail("3.3 Node Statistics", str(e))

def test_3_4_root_endpoint():
    """Test 3.4: Root endpoint documentation"""
    try:
        response = requests.get(f"{BASE_URL}/")
        if response.status_code == 200:
            data = response.json()
            if 'service' in data and 'endpoints' in data:
                results.record_pass("3.4 Root Endpoint")
            else:
                results.record_fail("3.4 Root Endpoint", "Missing service info")
        else:
            results.record_fail("3.4 Root Endpoint", f"Status {response.status_code}")
    except Exception as e:
        results.record_fail("3.4 Root Endpoint", str(e))

# ============================================================
# 4. GPU FUNCTIONALITY TESTS
# ============================================================

def test_4_1_gpu_access():
    """Test 4.1: GPU access via nvidia-smi"""
    code = '''
import subprocess
result = subprocess.run(['nvidia-smi'], capture_output=True, text=True)
print(result.stdout)
'''
    config = {
        'user_id': 'sarang',
        'token': 'sarang',
        'competition_id': 'test',
        'project_id': 'test',
        'expected_time': 10
    }
    response = submit_job(code, config)
    
    if response['status_code'] == 200:
        data = response['data']
        if 'H100' in data.get('stdout', '') or 'NVIDIA' in data.get('stdout', ''):
            results.record_pass("4.1 GPU Access")
        else:
            results.record_fail("4.1 GPU Access", "No GPU info in output")
    else:
        results.record_fail("4.1 GPU Access", f"Status {response['status_code']}")

# ============================================================
# MAIN TEST RUNNER
# ============================================================

def main():
    print("=" * 60)
    print("GPU Job Queue Server - Test Suite")
    print("Phase 1: Basic Functionality Tests")
    print("=" * 60)
    print(f"Server: {BASE_URL}")
    print()
    
    # Check server is running
    try:
        response = requests.get(f"{BASE_URL}/", timeout=2)
        if response.status_code != 200:
            print(f"{FAIL} Server not responding at {BASE_URL}")
            sys.exit(1)
    except Exception as e:
        print(f"{FAIL} Cannot connect to server: {e}")
        sys.exit(1)
    
    print(f"{PASS} Server is running\n")
    
    # Run test groups
    print("=" * 60)
    print("1. AUTHENTICATION TESTS")
    print("=" * 60)
    test_1_1_valid_auth()
    test_1_2_invalid_token()
    test_1_3_missing_token()
    
    print("\n" + "=" * 60)
    print("2. JOB SUBMISSION TESTS")
    print("=" * 60)
    test_2_1_valid_job()
    test_2_2_syntax_error()
    test_2_3_runtime_error()
    test_2_4_empty_script()
    
    print("\n" + "=" * 60)
    print("3. API ENDPOINT TESTS")
    print("=" * 60)
    test_3_1_status_nonexistent()
    test_3_2_list_jobs()
    test_3_3_node_stats()
    test_3_4_root_endpoint()
    
    print("\n" + "=" * 60)
    print("4. GPU FUNCTIONALITY TESTS")
    print("=" * 60)
    test_4_1_gpu_access()
    
    # Summary
    success = results.summary()
    sys.exit(0 if success else 1)

if __name__ == "__main__":
    main()

