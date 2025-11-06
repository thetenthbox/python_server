#!/usr/bin/env python3
"""
Test job cancellation:
1. Cancel a running job
2. Cancel a queued job
"""

import requests
import time
import json

BASE_URL = "http://localhost:8001"

def submit_job(code, sleep_time=60):
    """Submit a job that sleeps for specified time"""
    config = f"""competition_id: "random-acts-of-pizza"
project_id: "test_cancel"
user_id: "sarang"
expected_time: {sleep_time + 10}
token: "sarang"
"""
    
    files = {
        'code': ('test.py', code, 'text/x-python'),
        'config_file': ('config.yaml', config, 'text/yaml')
    }
    
    response = requests.post(f"{BASE_URL}/api/submit", files=files, timeout=5)
    return response.json()

def cancel_job(job_id):
    """Cancel a job"""
    headers = {"Authorization": "Bearer sarang"}
    response = requests.post(f"{BASE_URL}/api/cancel/{job_id}", headers=headers)
    return response.json()

def get_status(job_id):
    """Get job status"""
    response = requests.get(f"{BASE_URL}/api/status/{job_id}")
    return response.json()

print("=" * 60)
print("Test 1: Cancel a Running Job")
print("=" * 60)

# Submit long-running job
long_code = """
import time
print("Starting long job...")
for i in range(60):
    print(f"Running... {i}")
    time.sleep(1)
print("Finished!")
"""

print("Submitting long-running job...")
try:
    # Use very short timeout to avoid waiting for completion
    response = requests.post(
        f"{BASE_URL}/api/submit",
        files={
            'code': ('test.py', long_code, 'text/x-python'),
            'config_file': ('config.yaml', """competition_id: "random-acts-of-pizza"
project_id: "test_cancel"
user_id: "sarang"
expected_time: 70
token: "sarang"
""", 'text/yaml')
        },
        timeout=3  # Will timeout, but job will be submitted
    )
    job1 = response.json()
except requests.exceptions.Timeout:
    # Get job ID from /api/jobs
    time.sleep(1)
    jobs_response = requests.get(f"{BASE_URL}/api/jobs?limit=1")
    jobs = jobs_response.json()
    job1 = {'job_id': jobs['jobs'][0]['job_id']}
    print(f"Job submitted (timeout expected): {job1['job_id']}")

# Wait for job to start running
print("Waiting for job to start running...")
for i in range(10):
    status = get_status(job1['job_id'])
    print(f"  Status: {status['status']}")
    if status['status'] == 'running':
        break
    time.sleep(1)

if status['status'] == 'running':
    print(f"\n✓ Job {job1['job_id']} is RUNNING")
    print("Cancelling running job...")
    cancel_result = cancel_job(job1['job_id'])
    print(f"Cancel response: {cancel_result}")
    
    time.sleep(2)
    final_status = get_status(job1['job_id'])
    print(f"Final status: {final_status['status']}")
    
    if final_status['status'] == 'cancelled':
        print("✅ TEST 1 PASSED: Successfully cancelled running job")
    else:
        print(f"❌ TEST 1 FAILED: Job status is {final_status['status']}, expected 'cancelled'")
else:
    print(f"⚠️  TEST 1 SKIPPED: Job never started running (status: {status['status']})")

print("\n" + "=" * 60)
print("Test 2: Cancel a Queued Job")
print("=" * 60)

# Submit 3 jobs quickly
print("Submitting 3 jobs rapidly...")
job_ids = []

quick_code = """
import time
print("Quick job starting...")
time.sleep(30)
print("Quick job done!")
"""

for i in range(3):
    try:
        response = requests.post(
            f"{BASE_URL}/api/submit",
            files={
                'code': ('test.py', quick_code, 'text/x-python'),
                'config_file': ('config.yaml', f"""competition_id: "random-acts-of-pizza"
project_id: "test_cancel_{i}"
user_id: "sarang"
expected_time: 40
token: "sarang"
""", 'text/yaml')
            },
            timeout=2
        )
        job = response.json()
    except requests.exceptions.Timeout:
        # Job submitted but response timed out
        time.sleep(0.5)
        jobs_response = requests.get(f"{BASE_URL}/api/jobs?limit=1")
        job = {'job_id': jobs_response.json()['jobs'][0]['job_id']}
    
    job_ids.append(job['job_id'])
    print(f"  Job {i+1} submitted: {job['job_id'][:8]}...")
    time.sleep(0.5)  # Small delay between submissions

# Check statuses
print("\nChecking job statuses...")
time.sleep(2)
for i, job_id in enumerate(job_ids):
    status = get_status(job_id)
    print(f"  Job {i+1}: {status['status']}")

# Cancel the third job
print(f"\nCancelling job 3: {job_ids[2][:8]}...")
cancel_result = cancel_job(job_ids[2])
print(f"Cancel response: {cancel_result}")

time.sleep(1)
final_status = get_status(job_ids[2])
print(f"Job 3 final status: {final_status['status']}")

if final_status['status'] == 'cancelled':
    print("✅ TEST 2 PASSED: Successfully cancelled queued job")
else:
    print(f"❌ TEST 2 FAILED: Job status is {final_status['status']}, expected 'cancelled'")

# Show queue status
print("\n" + "=" * 60)
print("Final Queue Status")
print("=" * 60)
nodes = requests.get(f"{BASE_URL}/api/nodes").json()
for node in nodes['nodes'][:3]:  # Show first 3 nodes
    print(f"Node {node['node_id']}: Queue length = {node['queue_length']}, Total wait = {node['total_wait_time']}s")

print("\n" + "=" * 60)
print("Test Summary")
print("=" * 60)
print("Note: Some jobs may still be running. Check with:")
print(f"  curl {BASE_URL}/api/jobs | python3 -m json.tool")

