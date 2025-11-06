# Test Suite

## Overview

Comprehensive test suite for the GPU Job Queue Server covering functionality, security, and authorization.

## Test Files

### 1. `run_basic_tests.py`
Tests core job submission and execution functionality.

**Tests:**
- Job submission with valid code
- Syntax error handling
- Runtime error handling
- Job status retrieval
- Results retrieval

**Run:**
```bash
python3 run_basic_tests.py
```

### 2. `test_authorization.py`
Tests user isolation and admin privileges.

**Tests:**
- Users can only view their own jobs
- Admin can view all jobs
- Admin can cancel any job
- Job list filtering by user

**Run:**
```bash
python3 test_authorization.py
```

### 3. `test_cancel.py`
Tests job cancellation for running and queued jobs.

**Tests:**
- Cancel running job
- Cancel queued job
- Verify job status after cancellation

**Run:**
```bash
python3 test_cancel.py
```

### 4. `test_security.py`
Tests rate limiting, queue limits, and token-user binding.

**Tests:**
- Rate limiting (5 submissions/min)
- Queue limits (1 active job per user)
- Token-user binding validation
- Endpoint protection

**Run:**
```bash
python3 test_security.py
```

### 5. `test_token_management.py`
Tests token creation, validation, and expiration.

**Tests:**
- Token-user binding
- 30-day maximum expiry
- One active token per user
- Default 30-day expiry
- Expired token rejection

**Run:**
```bash
python3 test_token_management.py
```

### 6. `python_test_file.py`
Legacy test file with various Python code samples for testing execution.

## Running All Tests

### Quick Test
Run the most important tests:
```bash
# Basic functionality
python3 run_basic_tests.py

# Authorization
python3 test_authorization.py

# Security
python3 test_security.py
```

### Full Test Suite
Run all tests sequentially:
```bash
python3 run_basic_tests.py && \
python3 test_authorization.py && \
python3 test_cancel.py && \
python3 test_security.py && \
python3 test_token_management.py
```

### Run Individual Test Categories

**Functionality Tests:**
```bash
python3 run_basic_tests.py
```

**Authorization Tests:**
```bash
python3 test_authorization.py
```

**Security Tests:**
```bash
python3 test_security.py
python3 test_token_management.py
```

**Job Control Tests:**
```bash
python3 test_cancel.py
```

## Prerequisites

### Server Must Be Running
```bash
cd ..
python3 main.py
```

### Required Tokens
Most tests require tokens to be created:

```bash
cd ..
# Create regular user tokens
python3 token_manager.py create sarang test_token_regular
python3 token_manager.py create bob test_token_bob

# Create admin token
python3 token_manager.py create admin test_token_admin --admin
```

### Python Packages
```bash
pip3 install requests
```

## Test Results

### Expected Output

**Passing Tests:**
```
============================================================
Results: 4 passed, 0 failed
============================================================
```

**Failing Tests:**
```
✗ test_name FAILED
  Error message here
```

## Writing New Tests

### Test Structure
```python
#!/usr/bin/env python3
import requests
import sys

BASE_URL = "http://localhost:8001"
TOKEN = "test_token"

def test_feature():
    """Test description"""
    # Setup
    headers = {'Authorization': f'Bearer {TOKEN}'}
    
    # Execute
    response = requests.get(f"{BASE_URL}/api/endpoint", headers=headers)
    
    # Assert
    if response.status_code == 200:
        print("✓ Test passed")
        return True
    else:
        print("✗ Test failed")
        return False

def main():
    tests = [test_feature]
    passed = sum(1 for test in tests if test())
    failed = len(tests) - passed
    
    print(f"\nResults: {passed} passed, {failed} failed")
    return 0 if failed == 0 else 1

if __name__ == "__main__":
    sys.exit(main())
```

### Best Practices

1. **Use descriptive test names**
   ```python
   def test_user_cannot_view_other_users_jobs():
       """Test that regular users are restricted to their own jobs"""
   ```

2. **Test both success and failure cases**
   ```python
   # Test success
   response = requests.get(url, headers=valid_headers)
   assert response.status_code == 200
   
   # Test failure
   response = requests.get(url, headers=invalid_headers)
   assert response.status_code == 401
   ```

3. **Clean up after tests**
   ```python
   # Cancel jobs created during testing
   requests.post(f"{BASE_URL}/api/cancel/{job_id}", headers=headers)
   ```

4. **Use appropriate timeouts**
   ```python
   response = requests.post(url, files=files, timeout=60)
   ```

5. **Check response content, not just status**
   ```python
   assert response.status_code == 200
   data = response.json()
   assert 'job_id' in data
   assert data['status'] == 'completed'
   ```

## Test Coverage

### Covered Areas
- ✅ Job submission
- ✅ Job status retrieval
- ✅ Job results retrieval
- ✅ Job cancellation
- ✅ User authorization
- ✅ Admin privileges
- ✅ Rate limiting
- ✅ Queue limits
- ✅ Token management
- ✅ Token expiration

### Not Yet Covered
- ⏳ Concurrent job submission
- ⏳ Network failure recovery
- ⏳ Database corruption handling
- ⏳ SSH connection failures
- ⏳ Worker thread crashes
- ⏳ Long-running job timeout

## Continuous Integration

### Automated Testing Script
```bash
#!/bin/bash
# test_all.sh

set -e

echo "Starting test suite..."

# Start server in background
cd /path/to/python_server
python3 main.py &
SERVER_PID=$!

# Wait for server to start
sleep 3

# Run tests
cd tests
python3 run_basic_tests.py
python3 test_authorization.py
python3 test_security.py
python3 test_token_management.py

# Cleanup
kill $SERVER_PID

echo "All tests passed!"
```

## Troubleshooting Tests

### Server Not Running
```
Error: Connection refused
```
**Solution:** Start the server first
```bash
cd ..
python3 main.py
```

### Tokens Not Found
```
Error: 401 Unauthorized
```
**Solution:** Create required tokens
```bash
python3 token_manager.py create sarang test_token_regular
python3 token_manager.py create admin test_token_admin --admin
```

### Port Already in Use
```
Error: Address already in use
```
**Solution:** Kill existing server
```bash
lsof -ti:8001 | xargs kill -9
```

### Tests Timing Out
```
Error: Request timeout
```
**Solution:** Increase timeout or check GPU node connectivity
```python
response = requests.post(url, files=files, timeout=300)  # 5 minutes
```

### Database Lock Errors
```
Error: database is locked
```
**Solution:** Restart server to release locks
```bash
lsof -ti:8001 | xargs kill -9
python3 main.py
```

## Test Development Workflow

1. **Write test**
   ```bash
   vim tests/test_new_feature.py
   ```

2. **Run test**
   ```bash
   python3 test_new_feature.py
   ```

3. **Debug failures**
   - Check server logs
   - Verify tokens exist
   - Test API manually with curl

4. **Add to test suite**
   - Update this README
   - Add to CI script

## Performance Testing

### Load Testing
```python
import concurrent.futures
import requests

def submit_job():
    # Submit job and measure time
    start = time.time()
    response = requests.post(url, files=files)
    return time.time() - start

# Test with 10 concurrent submissions
with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
    times = list(executor.map(lambda _: submit_job(), range(10)))

print(f"Average: {sum(times)/len(times):.2f}s")
```

### Stress Testing
```bash
# Rapid job submissions
for i in {1..100}; do
    curl -X POST http://localhost:8001/api/submit \
         -F "code=@test.py" \
         -F "config_file=@config.json" &
done
wait
```

## Test Maintenance

### Regular Tasks
- [ ] Run full test suite weekly
- [ ] Update tests when API changes
- [ ] Add tests for new features
- [ ] Review and update expected behaviors
- [ ] Clean up test database periodically

### When to Update Tests
- API endpoint changes
- New features added
- Security policies change
- Bug fixes that need regression tests
- Performance optimizations

## Contributing

When adding new tests:
1. Follow the test structure template
2. Add test to this README
3. Ensure test is idempotent
4. Add proper error handling
5. Document expected behavior

## Resources

- [Testing Plan](../documentation/TESTING_PLAN.md) - Overall testing strategy
- [API Documentation](../documentation/API_DOCUMENTATION.md) - API reference
- [Access Control](../documentation/ACCESS_CONTROL.md) - Authorization details

## Contact

For test-related issues or questions, see the main documentation in `../documentation/`.

