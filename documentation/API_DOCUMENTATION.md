# GPU Job Queue Server - API Documentation

**Base URL:** `http://localhost:8001`  
**Interactive Docs:** `http://localhost:8001/docs`

---

## 📋 Overview

This API allows you to submit Python solutions to be graded on a GPU cluster. Your code is executed on H100 GPUs and evaluated against competition datasets, returning detailed scoring results.

**How it works:**
1. Submit your solution file (Python code)
2. Server uploads it to GPU node and runs: `grade_code.py solution.py <competition_id> results.jsonl`
3. Results are returned in API response and saved locally as: `{user_id}_{competition_id}_{timestamp}.jsonl`

---

## 🔑 Authentication

All job submissions require:
- `user_id`: Your user identifier
- `token`: Authentication token (must match user_id)
- `competition_id`: The competition to grade against (e.g., "random-acts-of-pizza")

Default credentials:
- **user_id**: `sarang`
- **token**: `sarang`

---

## 📡 Endpoints

### 1. Submit Job (Synchronous)

**POST** `/api/submit`

Submit a solution for grading and wait for completion. Returns full grading results when job finishes.

**Request:**
```bash
curl -X POST http://localhost:8001/api/submit \
  -F "code=@your_solution.py" \
  -F "config_file=@config.yaml"
```

**Config File Format (YAML):**
```yaml
competition_id: "random-acts-of-pizza"  # Competition to grade against
project_id: "my_project"
user_id: "sarang"
expected_time: 60  # estimated seconds
token: "sarang"
```

**Response (on completion):**
```json
{
  "job_id": "uuid",
  "node_id": 0,
  "status": "completed",
  "stdout": "{\n  \"success\": true,\n  \"exit_code\": 0,\n  \"timed_out\": false,\n  \"exec_time\": 36.68,\n  \"valid_solution\": true,\n  \"test_fitness\": 0.49272,\n  \"grading_report\": {\n    \"competition_id\": \"random-acts-of-pizza\",\n    \"score\": 0.49272,\n    \"gold_threshold\": 0.97908,\n    \"silver_threshold\": 0.76482,\n    \"bronze_threshold\": 0.6921,\n    \"any_medal\": false,\n    \"gold_medal\": false,\n    \"silver_medal\": false,\n    \"bronze_medal\": false,\n    \"above_median\": false,\n    \"submission_exists\": true,\n    \"valid_submission\": true\n  }\n}",
  "stderr": "",
  "exit_code": 0,
  "started_at": "2025-11-06T15:42:50.997341",
  "completed_at": "2025-11-06T15:43:47.114873"
}
```

**Key Response Fields:**
- `stdout`: Contains the complete `results.jsonl` as a JSON string (parse it to get grading details)
- `test_fitness`: Your score on the test set
- `grading_report`: Medal thresholds and achievement status
- `exec_time`: Execution time in seconds

**Local File Storage:**
Results are automatically saved on the server at:
```
jobs/results/{user_id}_{competition_id}_{YYYYMMDD_HHMMSS}.jsonl
```
Example: `jobs/results/sarang_random-acts-of-pizza_20251106_154517.jsonl`

**Response (on timeout - 300s max):**
```json
{
  "job_id": "uuid",
  "node_id": 0,
  "status": "running",
  "message": "Timeout after 300s. Job still running. Use /api/results/{job_id} to check later."
}
```

**Notes:**
- Waits up to 5 minutes (300s) for job completion
- Returns immediately with results when job finishes
- Solution file is uploaded to GPU node as `solution.py`
- Grading command executed: `cd /home/gpuuser/aira-dojo && python src/dojo/grade_code.py solution.py {competition_id} results.jsonl`
- Parse the `stdout` field (it's a JSON string) to access grading details

---

### 2. Get Job Status

**GET** `/api/status/{job_id}`

Check the current status of a submitted job.

**Request:**
```bash
curl http://localhost:8001/api/status/YOUR_JOB_ID
```

**Response:**
```json
{
  "job_id": "uuid",
  "status": "completed",
  "node_id": 0,
  "queue_position": null,
  "created_at": "2025-11-06T15:04:11.101052",
  "started_at": "2025-11-06T15:04:11.585444",
  "completed_at": "2025-11-06T15:04:16.046562",
  "exit_code": 0
}
```

**Status Values:**
- `pending`: Waiting in queue
- `running`: Currently executing
- `completed`: Finished successfully
- `failed`: Execution failed
- `cancelled`: Job was cancelled

---

### 3. Get Job Results

**GET** `/api/results/{job_id}`

Retrieve the grading results of a completed job.

**Request:**
```bash
curl http://localhost:8001/api/results/YOUR_JOB_ID
```

**Response:**
```json
{
  "job_id": "uuid",
  "status": "completed",
  "stdout": "{\"success\": true, \"test_fitness\": 0.49272, \"grading_report\": {...}}",
  "stderr": "",
  "exit_code": 0,
  "started_at": "2025-11-06T15:04:11.585444",
  "completed_at": "2025-11-06T15:04:16.046562"
}
```

**Note:** The `stdout` field contains the grading results as a JSON string. Parse it to access:
- `test_fitness`: Your score
- `grading_report`: Detailed grading metrics, medal thresholds
- `exec_time`: How long your solution took to run
- `valid_solution`: Whether your solution produced valid output

---

### 4. Cancel Job

**POST** `/api/cancel/{job_id}`

Cancel a pending or running job.

**Request:**
```bash
curl -X POST http://localhost:8001/api/cancel/YOUR_JOB_ID \
  -H "Authorization: Bearer YOUR_TOKEN"
```

**Response:**
```json
{
  "message": "Job cancelled successfully",
  "status": "cancelled"
}
```

**Notes:**
- Requires `Authorization` header with your token
- Only the job owner can cancel their jobs
- Cannot cancel completed/failed jobs

---

### 5. List GPU Nodes

**GET** `/api/nodes`

Get statistics for all GPU nodes in the cluster.

**Request:**
```bash
curl http://localhost:8001/api/nodes
```

**Response:**
```json
{
  "nodes": [
    {
      "node_id": 0,
      "ip": "10.221.102.181",
      "queue_length": 2,
      "total_wait_time": 120,
      "status": "active"
    },
    ...
  ]
}
```

---

### 6. List Jobs

**GET** `/api/jobs`

List recent jobs with optional filtering.

**Request:**
```bash
# All jobs
curl http://localhost:8001/api/jobs

# Filter by user
curl http://localhost:8001/api/jobs?user_id=sarang

# Filter by status
curl http://localhost:8001/api/jobs?status=completed

# Limit results
curl http://localhost:8001/api/jobs?limit=10
```

**Response:**
```json
{
  "jobs": [
    {
      "job_id": "uuid",
      "user_id": "sarang",
      "status": "completed",
      "node_id": 0,
      "created_at": "2025-11-06T15:04:11.101052",
      "completed_at": "2025-11-06T15:04:16.046562"
    },
    ...
  ]
}
```

---

## 💡 Quick Examples

### Example 1: Submit and Grade a Solution

```bash
# Create your solution
cat > my_solution.py << 'EOF'
import pandas as pd
# ... your ML code here ...
submission.to_csv('./submission.csv', index=False)
EOF

# Create config
cat > config.yaml << 'EOF'
competition_id: "random-acts-of-pizza"
project_id: "my_project"
user_id: "sarang"
expected_time: 60
token: "sarang"
EOF

# Submit and get grading results
response=$(curl -s -X POST http://localhost:8001/api/submit \
  -F "code=@my_solution.py" \
  -F "config_file=@config.yaml")

# Parse results
echo "$response" | python3 -c "
import sys, json
data = json.load(sys.stdin)
results = json.loads(data['stdout'])
print(f\"Score: {results['test_fitness']}\")
print(f\"Execution time: {results['exec_time']}s\")
print(f\"Gold medal: {results['grading_report']['gold_medal']}\")
"
```

### Example 2: Check GPU Availability

```bash
# Check which nodes are available
curl http://localhost:8001/api/nodes | python3 -m json.tool
```

---

## 🔧 Python Client Example

```python
import requests
import json

def submit_solution(solution_path, competition_id, user_id="sarang", token="sarang"):
    """Submit a solution for grading"""
    url = "http://localhost:8001/api/submit"
    
    # Create config
    config = f"""competition_id: "{competition_id}"
project_id: "my_project"
user_id: "{user_id}"
expected_time: 60
token: "{token}"
"""
    
    # Submit
    with open(solution_path, 'rb') as code_file:
        files = {
            'code': code_file,
            'config_file': ('config.yaml', config, 'text/yaml')
        }
        response = requests.post(url, files=files)
    
    return response.json()

# Submit solution
result = submit_solution('my_solution.py', 'random-acts-of-pizza')

# Parse grading results
if result['status'] == 'completed':
    grading = json.loads(result['stdout'])
    
    print(f"Score: {grading['test_fitness']}")
    print(f"Execution time: {grading['exec_time']}s")
    print(f"Valid solution: {grading['valid_solution']}")
    
    report = grading['grading_report']
    print(f"\nMedal Status:")
    print(f"  Gold: {report['gold_medal']} (threshold: {report['gold_threshold']})")
    print(f"  Silver: {report['silver_medal']} (threshold: {report['silver_threshold']})")
    print(f"  Bronze: {report['bronze_medal']} (threshold: {report['bronze_threshold']})")
    print(f"  Above median: {report['above_median']}")
    
    # Results also saved locally on server as:
    # jobs/results/{user_id}_{competition_id}_{timestamp}.jsonl
else:
    print(f"Job {result['status']}: {result.get('message', 'Check later')}")
```

---

## ⚠️ Important Notes

1. **Timeout**: Submit endpoint waits max 300 seconds (5 minutes). For longer jobs, use status/results endpoints.
2. **GPU Access**: Solutions run on H100 GPUs with CUDA 12.4 in sandboxed Apptainer environment.
3. **Grading Environment**: Your code runs in `/home/gpuuser/aira-dojo` with access to competition datasets.
4. **Competition ID**: Must be a valid competition identifier (e.g., "random-acts-of-pizza").
5. **Output Format**: Your solution must generate a `submission.csv` file - this is what gets graded.
6. **Results Storage**: All grading results are saved as `{user_id}_{competition_id}_{timestamp}.jsonl` on the server.
7. **Parsing Results**: The `stdout` field contains a JSON string - parse it with `json.loads()` to access grading details.
8. **Authentication**: Keep your token secure; anyone with it can submit jobs under your user_id.
9. **Queue**: Jobs are assigned to nodes with shortest queue automatically.
10. **Execution**: The grading system runs your code, evaluates output, and returns detailed metrics.

---

## 🌐 Interactive Documentation

Visit `http://localhost:8001/docs` for:
- Interactive API testing
- Detailed schema documentation
- Try-it-now functionality
- Request/response examples

---

## 📞 Support

For issues or questions:
1. Check job stderr for error messages
2. Verify your token is valid
3. Ensure Python script is syntactically correct
4. Check GPU node availability with `/api/nodes`

