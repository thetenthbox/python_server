# GPU Job Queue Server - User Guide

Welcome! This guide will help you submit and manage your GPU jobs.

## Prerequisites

Your administrator will provide you with:
- **Server URL**: The address of the GPU job queue server
- **Authentication Token**: Your personal access token
- **User ID**: Your unique user identifier

**Keep your token secure!** It's like a password for accessing the GPU cluster.

## Quick Start

### 1. Prepare Your Files

You need two files to submit a job:

**`solution.py`** - Your Python code:
```python
# Your machine learning code here
import torch
import pandas as pd

# Example: Simple training script
print("Training model...")
# Your code runs on GPU automatically
```

**`config.yaml`** - Job configuration:
```yaml
competition_id: "my-competition"
project_id: "my-project"
user_id: "your_user_id"
expected_time: 300  # Expected runtime in seconds
token: "your-secret-token-here"
```

### 2. Submit a Job

```bash
curl -X POST "http://SERVER_URL/api/submit" \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -F "code=@solution.py" \
  -F "config_file=@config.yaml"
```

**Response:**
```json
{
  "job_id": "abc123-def456",
  "status": "completed",
  "stdout": "{ ... results ... }",
  "stderr": "",
  "exit_code": 0
}
```

The API waits for your job to complete and returns the results directly!

## Common Operations

### Check Job Status

```bash
curl -H "Authorization: Bearer YOUR_TOKEN" \
  "http://SERVER_URL/api/status/JOB_ID?user_id=YOUR_USER_ID"
```

**Response:**
```json
{
  "job_id": "abc123-def456",
  "status": "completed",
  "node_id": 0,
  "created_at": "2025-11-06T10:30:00",
  "started_at": "2025-11-06T10:30:05",
  "completed_at": "2025-11-06T10:35:20"
}
```

### Get Job Results

```bash
curl -H "Authorization: Bearer YOUR_TOKEN" \
  "http://SERVER_URL/api/results/JOB_ID?user_id=YOUR_USER_ID"
```

**Response:**
```json
{
  "job_id": "abc123-def456",
  "status": "completed",
  "stdout": "{ ... your results ... }",
  "stderr": "",
  "exit_code": 0
}
```

### List Your Jobs

```bash
curl -H "Authorization: Bearer YOUR_TOKEN" \
  "http://SERVER_URL/api/jobs?user_id=YOUR_USER_ID"
```

**Response:**
```json
[
  {
    "job_id": "abc123",
    "status": "completed",
    "competition_id": "my-competition",
    "created_at": "2025-11-06T10:30:00"
  },
  {
    "job_id": "def456",
    "status": "running",
    "competition_id": "my-competition",
    "created_at": "2025-11-06T11:00:00"
  }
]
```

### Cancel a Job

```bash
curl -X POST \
  -H "Authorization: Bearer YOUR_TOKEN" \
  "http://SERVER_URL/api/cancel/JOB_ID?user_id=YOUR_USER_ID"
```

## Job Status Meanings

- **`pending`**: Job is waiting in queue
- **`running`**: Job is currently executing on GPU
- **`completed`**: Job finished successfully
- **`failed`**: Job encountered an error
- **`cancelled`**: Job was cancelled by user

## Understanding Results

Your job results are returned in the `stdout` field. The format depends on your code, but typically it's a JSON file with your model's output.

Results are also saved on the server with this naming pattern:
```
{user_id}_{competition_id}_{timestamp}.jsonl
```

## Python Example

Here's a complete Python example to submit a job:

```python
import requests

SERVER_URL = "http://your-server:8001"
TOKEN = "your-token-here"
USER_ID = "your-user-id"

# Prepare files
code = """
print('Hello from GPU!')
import torch
print(f'CUDA available: {torch.cuda.is_available()}')
"""

config = {
    "user_id": USER_ID,
    "competition_id": "test",
    "project_id": "demo",
    "expected_time": 60,
    "token": TOKEN
}

# Submit job
files = {
    'code': ('solution.py', code, 'text/x-python'),
    'config_file': ('config.yaml', str(config), 'application/x-yaml')
}

headers = {'Authorization': f'Bearer {TOKEN}'}

response = requests.post(
    f"{SERVER_URL}/api/submit",
    files=files,
    headers=headers,
    timeout=300
)

result = response.json()
print(f"Job ID: {result['job_id']}")
print(f"Status: {result['status']}")
print(f"Results: {result['stdout']}")
```

## Best Practices

### 1. Set Accurate Expected Time
```yaml
expected_time: 300  # Be realistic about your job's runtime
```

### 2. Handle Errors Gracefully
Check the `stderr` field for error messages if your job fails.

### 3. Test Locally First
Test your code on a small dataset locally before submitting to the GPU cluster.

### 4. Monitor Your Jobs
Use the `/api/jobs` endpoint to track all your submissions.

### 5. Use Meaningful IDs
```yaml
competition_id: "cifar10-classification"  # Clear and descriptive
project_id: "resnet50-baseline"
```

## Rate Limits

To ensure fair access for all users:
- **Maximum 5 submissions per minute**
- **Maximum 1 active job at a time** (pending or running)

If you exceed these limits, you'll receive a `429 Too Many Requests` error.

## Troubleshooting

### Error: "Invalid or expired token"
- Check that your token is correct
- Contact your administrator for a new token

### Error: "Token does not belong to specified user_id"
- Make sure the `user_id` in your config matches your token
- Contact your administrator if unsure

### Job Status: "failed"
- Check the `stderr` field for error messages
- Common issues: syntax errors, missing imports, out of memory

### Error: "429 Too Many Requests"
- You've exceeded rate limits
- Wait 1 minute before submitting again

### Job Stuck in "pending"
- All GPU nodes are busy
- Your job will start when a node becomes available
- Check queue status with `/api/jobs`

## Privacy & Security

- **You can only see your own jobs** - Other users cannot access your submissions
- **Keep your token secret** - Never share it or commit it to version control
- **Your code is isolated** - Each job runs in a secure container

## Getting Help

If you encounter issues:
1. Check the error messages in `stderr`
2. Review this guide's troubleshooting section
3. Contact your system administrator

## Example Workflow

```bash
# 1. Submit your job
curl -X POST "http://SERVER_URL/api/submit" \
  -H "Authorization: Bearer TOKEN" \
  -F "code=@solution.py" \
  -F "config_file=@config.yaml"

# Response includes job_id: "abc123"

# 2. Check status (if needed)
curl -H "Authorization: Bearer TOKEN" \
  "http://SERVER_URL/api/status/abc123?user_id=USER_ID"

# 3. Get results (already included in submit response)
curl -H "Authorization: Bearer TOKEN" \
  "http://SERVER_URL/api/results/abc123?user_id=USER_ID"
```

---

**Happy Computing! 🚀**

For advanced features and administration, contact your system administrator.

