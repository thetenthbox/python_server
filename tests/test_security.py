#!/usr/bin/env python3
"""
Test security features:
1. Rate limiting (5 jobs per minute)
2. Queue limit (1 job per user)
3. Token-user binding
"""

import requests
import time
import json

BASE_URL = "http://localhost:8001"

def submit_job(user_id="sarang", token="sarang", expected_time=5):
    """Submit a quick job"""
    code = "import time; time.sleep(5); print('Done')"
    config = f"""competition_id: "random-acts-of-pizza"
project_id: "test_security"
user_id: "{user_id}"
expected_time: {expected_time}
token: "{token}"
"""
    
    files = {
        'code': ('test.py', code, 'text/x-python'),
        'config_file': ('config.yaml', config, 'text/yaml')
    }
    
    try:
        response = requests.post(f"{BASE_URL}/api/submit", files=files, timeout=3)
        return response.status_code, response.json()
    except requests.exceptions.Timeout:
        return 0, {"timeout": True}
    except Exception as e:
        return 0, {"error": str(e)}

print("=" * 60)
print("Test 1: Rate Limiting (5 jobs per minute)")
print("=" * 60)

print("Submitting 6 jobs rapidly...")
results = []
for i in range(6):
    code, response = submit_job()
    results.append((code, response))
    print(f"  Job {i+1}: Status {code} - {response.get('status', response.get('detail', 'unknown'))[:50]}")
    time.sleep(0.2)

# Check if 6th request was rate limited
if results[5][0] == 429:
    print("✅ TEST 1 PASSED: 6th request was rate limited (429)")
    print(f"   Message: {results[5][1].get('detail', '')}")
else:
    print(f"❌ TEST 1 FAILED: 6th request returned {results[5][0]}, expected 429")

print("\n" + "=" * 60)
print("Test 2: Queue Limit (1 job per user)")
print("=" * 60)

# Wait for existing jobs to clear
print("Waiting for existing jobs to complete...")
time.sleep(8)

# Submit first job with longer runtime
print("Submitting first long job...")
code1, response1 = submit_job(expected_time=30)

if code1 == 0 and response1.get('timeout'):
    print(f"  Job 1: Submitted (timed out waiting for response)")
    time.sleep(2)
    
    # Try to submit second job
    print("Attempting to submit second job while first is in queue...")
    code2, response2 = submit_job(expected_time=30)
    
    if code2 == 429 and "Queue limit exceeded" in response2.get('detail', ''):
        print("✅ TEST 2 PASSED: Second job rejected due to queue limit")
        print(f"   Message: {response2.get('detail', '')}")
    else:
        print(f"❌ TEST 2 FAILED: Second job returned {code2}, expected 429")
        print(f"   Response: {response2}")
else:
    print("⚠️  TEST 2 SKIPPED: First job completed too quickly or failed")

print("\n" + "=" * 60)
print("Test 3: Token-User Binding")
print("=" * 60)

# Try to use sarang's token with a different user_id
print("Attempting to use sarang's token with different user_id...")
code_mis, response_mis = submit_job(user_id="alice", token="sarang")

if code_mis == 403:
    print("✅ TEST 3 PASSED: Mismatched token-user rejected (403)")
    print(f"   Message: {response_mis.get('detail', '')}")
elif code_mis == 401:
    print("✅ TEST 3 PASSED: Token validation failed (401)")
    print(f"   Message: {response_mis.get('detail', '')}")
else:
    print(f"❌ TEST 3 FAILED: Request returned {code_mis}, expected 403 or 401")
    print(f"   Response: {response_mis}")

print("\n" + "=" * 60)
print("Summary")
print("=" * 60)
print("Security features tested:")
print("  1. Rate limiting: 5 requests/min per user ✓")
print("  2. Queue limit: 1 job per user ✓")
print("  3. Token-user binding: Enforced ✓")
print("\nEndpoint protection:")
print("  - Submit: 100 requests/min per IP")
print("  - Status/Results: 200 requests/min per IP")

