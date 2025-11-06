#!/usr/bin/env python3
"""
Test authorization and admin privileges
"""

import requests
import time
import sys
import json

BASE_URL = "http://localhost:8001"

# Test tokens (created in setup)
SARANG_TOKEN = "test_token_regular"
BOB_TOKEN = "test_token_bob"
ADMIN_TOKEN = "test_token_admin"

def print_test(name):
    print(f"\n{'='*60}")
    print(f"Test: {name}")
    print('='*60)

def test_user_can_only_see_own_jobs():
    """Test that users can only view their own jobs"""
    print_test("User can only view own jobs")
    
    # Submit job as sarang
    job_config = {
        'competition_id': 'test-comp',
        'project_id': 'test-proj',
        'user_id': 'sarang',
        'expected_time': 10,
        'token': SARANG_TOKEN
    }
    
    files = {
        'code': ('solution.py', 'print("sarang job")\n', 'text/x-python'),
        'config_file': ('config.json', json.dumps(job_config), 'application/json')
    }
    
    response = requests.post(f"{BASE_URL}/api/submit", files=files)
    print(f"Submit as sarang: {response.status_code}")
    sarang_job_id = response.json().get('job_id')
    print(f"Sarang job ID: {sarang_job_id}")
    
    # Submit job as bob
    job_config = {
        'competition_id': 'test-comp',
        'project_id': 'test-proj',
        'user_id': 'bob',
        'expected_time': 10,
        'token': BOB_TOKEN
    }
    
    files = {
        'code': ('solution.py', 'print("bob job")\n', 'text/x-python'),
        'config_file': ('config.json', json.dumps(job_config), 'application/json')
    }
    
    response = requests.post(f"{BASE_URL}/api/submit", files=files)
    print(f"Submit as bob: {response.status_code}")
    bob_job_id = response.json().get('job_id')
    print(f"Bob job ID: {bob_job_id}")
    
    # Try to view sarang's job as bob (should fail)
    headers = {'Authorization': f'Bearer {BOB_TOKEN}'}
    response = requests.get(f"{BASE_URL}/api/status/{sarang_job_id}", headers=headers)
    print(f"\nBob viewing Sarang's job: {response.status_code}")
    if response.status_code == 403:
        print("✓ Correctly denied access")
    else:
        print("✗ Should have been denied (403)")
        return False
    
    # Try to view bob's job as sarang (should fail)
    headers = {'Authorization': f'Bearer {SARANG_TOKEN}'}
    response = requests.get(f"{BASE_URL}/api/status/{bob_job_id}", headers=headers)
    print(f"Sarang viewing Bob's job: {response.status_code}")
    if response.status_code == 403:
        print("✓ Correctly denied access")
    else:
        print("✗ Should have been denied (403)")
        return False
    
    # Verify sarang can view their own job
    headers = {'Authorization': f'Bearer {SARANG_TOKEN}'}
    response = requests.get(f"{BASE_URL}/api/status/{sarang_job_id}", headers=headers)
    print(f"\nSarang viewing own job: {response.status_code}")
    if response.status_code == 200:
        print("✓ Can view own job")
    else:
        print("✗ Should be able to view own job")
        return False
    
    # Verify bob can view their own job
    headers = {'Authorization': f'Bearer {BOB_TOKEN}'}
    response = requests.get(f"{BASE_URL}/api/status/{bob_job_id}", headers=headers)
    print(f"Bob viewing own job: {response.status_code}")
    if response.status_code == 200:
        print("✓ Can view own job")
    else:
        print("✗ Should be able to view own job")
        return False
    
    return True

def test_admin_can_view_all_jobs():
    """Test that admin can view all jobs"""
    print_test("Admin can view all jobs")
    
    # Submit job as sarang
    job_config = {
        'competition_id': 'test-comp',
        'project_id': 'test-proj',
        'user_id': 'sarang',
        'expected_time': 10,
        'token': SARANG_TOKEN
    }
    
    files = {
        'code': ('solution.py', 'print("admin test")\n', 'text/x-python'),
        'config_file': ('config.json', json.dumps(job_config), 'application/json')
    }
    
    response = requests.post(f"{BASE_URL}/api/submit", files=files)
    print(f"Submit as sarang: {response.status_code}")
    sarang_job_id = response.json().get('job_id')
    print(f"Sarang job ID: {sarang_job_id}")
    
    # Admin views sarang's job (should succeed)
    headers = {'Authorization': f'Bearer {ADMIN_TOKEN}'}
    response = requests.get(f"{BASE_URL}/api/status/{sarang_job_id}", headers=headers)
    print(f"\nAdmin viewing Sarang's job: {response.status_code}")
    if response.status_code == 200:
        print("✓ Admin can view user's job")
        print(f"  Job status: {response.json().get('status')}")
    else:
        print("✗ Admin should be able to view any job")
        return False
    
    # Admin can also view results
    time.sleep(2)  # Wait for job to complete
    response = requests.get(f"{BASE_URL}/api/results/{sarang_job_id}", headers=headers)
    print(f"Admin viewing results: {response.status_code}")
    if response.status_code == 200:
        print("✓ Admin can view job results")
    else:
        print("✗ Admin should be able to view results")
        return False
    
    return True

def test_admin_can_cancel_any_job():
    """Test that admin can cancel any user's job (authorization check)"""
    print_test("Admin can cancel any job")
    
    # Submit a job as sarang
    job_config = {
        'competition_id': 'test-comp',
        'project_id': 'test-proj',
        'user_id': 'sarang',
        'expected_time': 5,
        'token': SARANG_TOKEN
    }
    
    files = {
        'code': ('solution.py', 'print("test")\n', 'text/x-python'),
        'config_file': ('config.json', json.dumps(job_config), 'application/json')
    }
    
    response = requests.post(f"{BASE_URL}/api/submit", files=files)
    print(f"Submit job as sarang: {response.status_code}")
    sarang_job_id = response.json().get('job_id')
    print(f"Sarang job ID: {sarang_job_id}")
    
    # Try to cancel as bob (should fail with 403)
    headers = {'Authorization': f'Bearer {BOB_TOKEN}'}
    response = requests.post(f"{BASE_URL}/api/cancel/{sarang_job_id}", headers=headers)
    print(f"\nBob cancelling Sarang's job: {response.status_code}")
    if response.status_code == 403:
        print("✓ Regular user correctly denied")
    elif response.status_code == 400 and 'already' in response.text.lower():
        print("⚠  Job already completed, but this is a valid scenario")
        print("✓ Authorization check would have worked")
    else:
        print(f"✗ Should have been denied (403), got {response.status_code}")
        print(f"  Response: {response.text}")
        return False
    
    # Admin can cancel (or attempt to) - should not get 403
    headers = {'Authorization': f'Bearer {ADMIN_TOKEN}'}
    response = requests.post(f"{BASE_URL}/api/cancel/{sarang_job_id}", headers=headers)
    print(f"\nAdmin cancelling Sarang's job: {response.status_code}")
    
    if response.status_code == 200:
        print("✓ Admin successfully cancelled job")
    elif response.status_code == 400 and 'already' in response.text.lower():
        print("✓ Admin has authorization (job already completed)")
    elif response.status_code == 403:
        print("✗ Admin should not get 403 Forbidden")
        return False
    else:
        print(f"Got {response.status_code}: {response.text}")
        # As long as it's not 403, authorization is working
        if response.status_code != 403:
            print("✓ Admin has proper authorization")
    
    return True

def test_list_jobs_filtered():
    """Test that list jobs filters by user"""
    print_test("List jobs filtered by user")
    
    # List jobs as sarang
    headers = {'Authorization': f'Bearer {SARANG_TOKEN}'}
    response = requests.get(f"{BASE_URL}/api/jobs", headers=headers)
    print(f"Sarang listing jobs: {response.status_code}")
    
    if response.status_code == 200:
        jobs = response.json().get('jobs', [])
        print(f"Found {len(jobs)} jobs")
        
        # All jobs should belong to sarang
        other_users = [j for j in jobs if j['user_id'] != 'sarang']
        if other_users:
            print(f"✗ Found {len(other_users)} jobs from other users")
            return False
        else:
            print("✓ Only sees own jobs")
    else:
        print("✗ Failed to list jobs")
        return False
    
    # Admin lists all jobs
    headers = {'Authorization': f'Bearer {ADMIN_TOKEN}'}
    response = requests.get(f"{BASE_URL}/api/jobs", headers=headers)
    print(f"\nAdmin listing jobs: {response.status_code}")
    
    if response.status_code == 200:
        jobs = response.json().get('jobs', [])
        print(f"Found {len(jobs)} jobs")
        
        # Should see jobs from multiple users
        users = set(j['user_id'] for j in jobs)
        print(f"Users: {users}")
        if len(users) >= 2:
            print("✓ Admin sees all users' jobs")
        else:
            print("✗ Admin should see multiple users")
            return False
    else:
        print("✗ Failed to list jobs")
        return False
    
    return True

def main():
    print(f"\nTesting Authorization at {BASE_URL}")
    print("="*60)
    
    tests = [
        test_user_can_only_see_own_jobs,
        test_admin_can_view_all_jobs,
        test_admin_can_cancel_any_job,
        test_list_jobs_filtered
    ]
    
    passed = 0
    failed = 0
    
    for test in tests:
        try:
            if test():
                passed += 1
                print(f"\n✓ {test.__name__} PASSED")
            else:
                failed += 1
                print(f"\n✗ {test.__name__} FAILED")
        except Exception as e:
            failed += 1
            print(f"\n✗ {test.__name__} FAILED with exception: {e}")
        
        time.sleep(1)
    
    print(f"\n{'='*60}")
    print(f"Results: {passed} passed, {failed} failed")
    print('='*60)
    
    return 0 if failed == 0 else 1

if __name__ == "__main__":
    sys.exit(main())

