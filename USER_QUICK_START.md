# User Quick Start Guide

**Submit ML jobs to the GPU cluster via terminal commands.**

---

## 1. Get Your Credentials

**Contact your administrator for:**

- **Server URL:** `https://ceriferous-hoelike-jeffie.ngrok-free.dev`
- **User ID:** `your_username`
- **Token:** `your_secret_token_xyz`

**⚠️ Keep your token secret!**

---

## 2. Prepare Your Files

### Required Files

```
my-submission/
├── solution.py          # Your Python code
└── config.yaml          # Job configuration
```

### Your Code (`solution.py`)

Your ML script must:
- Read data from `/root/data/` (read-only)
- Save output to `./submission.csv`

```python
import pandas as pd

train = pd.read_csv('/root/data/train.csv')
# Your ML code...
submission.to_csv('./submission.csv', index=False)
```

### Configuration (`config.yaml`)

```yaml
competition_id: "random-acts-of-pizza"
project_id: "my-project"
user_id: "your_username"
expected_time: 300
token: "your_secret_token_xyz"
```

**Parameters:**
- `competition_id`: Competition name (from admin)
- `project_id`: Your project name
- `user_id`: Your username
- `expected_time`: Estimated runtime (seconds)
- `token`: Your secret token

---

## 3. Submit Your Job

### For Quick Jobs (< 4 hours) - Sync Mode

```bash
curl -X POST "https://ceriferous-hoelike-jeffie.ngrok-free.dev/api/submit?wait=true" \
  -F "code=@solution.py" \
  -F "config_file=@config.yaml"
```

### For Long Training Jobs (hours to days) - Async Mode

```bash
# Submit without waiting
curl -X POST "https://ceriferous-hoelike-jeffie.ngrok-free.dev/api/submit?wait=false" \
  -F "code=@solution.py" \
  -F "config_file=@config.yaml"
```

**Response (async mode) includes:**
```json
{
  "job_id": "550e8400-e29b-41d4-a716-446655440000",
  "node_id": 3,
  "status": "pending",
  "message": "Job submitted successfully. Use /api/status/{job_id} to check progress."
}
```

**Response (sync mode) includes:**
```json
{
  "job_id": "550e8400-e29b-41d4-a716-446655440000",
  "node_id": 3,
  "status": "completed",
  "stdout": "{...actual results.jsonl content...}",
  "exit_code": 0
}
```

**💡 Save the `job_id` from the response - you'll need it to check results!**

**Which mode to use?**
- **Sync (`wait=true`)**: Waits up to 4 hours, returns results automatically. Use for most jobs.
- **Async (`wait=false`)**: Returns immediately, check later. Use for multi-day training jobs.

**Note:** Jobs continue running even if connection drops - protected by `setsid nohup` on server.

### Save Job ID for Later

```bash
# Submit and save job ID
curl -X POST https://ceriferous-hoelike-jeffie.ngrok-free.dev/api/submit \
  -F "code=@solution.py" \
  -F "config_file=@config.yaml" > response.json

# Extract job ID
cat response.json | jq -r '.job_id'
# Copy this ID for next steps
```

---

## 4. Check Your Job Status

```bash
# Set your variables
export TOKEN="your_secret_token_xyz"
export JOB_ID="550e8400-e29b-41d4-a716-446655440000"

# Check status
curl -H "Authorization: Bearer $TOKEN" \
  "https://ceriferous-hoelike-jeffie.ngrok-free.dev/api/status/$JOB_ID"
```

**Response:**
```json
{
  "job_id": "550e8400-e29b-41d4-a716-446655440000",
  "status": "completed",
  "node_id": 3,
  "queue_position": null,
  "created_at": "2025-11-07T10:00:00",
  "exit_code": 0
}
```

**Status values:**
- `pending`: Waiting in queue (check `queue_position`)
- `running`: Currently executing on GPU
- `completed`: Finished successfully ✓
- `failed`: Error occurred ✗
- `cancelled`: Job was cancelled

---

## 5. Get Your Results

```bash
curl -H "Authorization: Bearer $TOKEN" \
  "https://ceriferous-hoelike-jeffie.ngrok-free.dev/api/results/$JOB_ID"
```

**Response:**
```json
{
  "job_id": "550e8400-e29b-41d4-a716-446655440000",
  "status": "completed",
  "stdout": "{\"id\":1,\"prediction\":0.95}\n{\"id\":2,\"prediction\":0.87}\n...",
  "stderr": "",
  "exit_code": 0
}
```

### Understanding the Results

**⚠️ IMPORTANT:** The `stdout` field contains the **actual results.jsonl file content**, NOT console output!

- `stdout`: **The actual results.jsonl from `/home/gpuuser/work/results.jsonl`** (your predictions)
- `stderr`: Error messages if job failed
- `exit_code`: 0 = success, non-zero = error

**What you see in `stdout`:**
- Lines of JSON (JSONL format)
- Each line is one prediction/result
- This is what gets graded/evaluated

**What you DON'T see:**
- Console print statements
- Debugging output
- Training logs

### Save Results to File

```bash
# Get results and save stdout to file
curl -s -H "Authorization: Bearer $TOKEN" \
  "https://ceriferous-hoelike-jeffie.ngrok-free.dev/api/results/$JOB_ID" | \
  jq -r '.stdout' > my_results.jsonl

# View your results
head my_results.jsonl
```

---

## 6. View All Your Jobs

```bash
# List all your jobs
curl -H "Authorization: Bearer $TOKEN" \
  "https://ceriferous-hoelike-jeffie.ngrok-free.dev/api/jobs"

# Format with jq
curl -s -H "Authorization: Bearer $TOKEN" \
  "https://ceriferous-hoelike-jeffie.ngrok-free.dev/api/jobs" | \
  jq '.jobs[] | {job_id, status, created_at}'

# See only your latest job
curl -s -H "Authorization: Bearer $TOKEN" \
  "https://ceriferous-hoelike-jeffie.ngrok-free.dev/api/jobs" | \
  jq '.jobs[0]'
```

---

## 7. Cancel a Job

```bash
curl -X POST -H "Authorization: Bearer $TOKEN" \
  "https://ceriferous-hoelike-jeffie.ngrok-free.dev/api/cancel/$JOB_ID"
```

**Response:**
```json
{
  "message": "Job cancelled successfully",
  "status": "cancelled"
}
```

---

## 8. View Node Status

```bash
# See which nodes are busy
curl "https://ceriferous-hoelike-jeffie.ngrok-free.dev/api/nodes"

# Format with jq
curl -s "https://ceriferous-hoelike-jeffie.ngrok-free.dev/api/nodes" | \
  jq '.nodes[] | select(.queue_length > 0)'
```

---

## Common Questions

### How many jobs can I submit?

- **Rate limit:** 5 submissions per minute
- **Queue limit:** 1 active job at a time

**💡 Wait for your current job to complete before submitting another.**

### How long will my job take?

```bash
# Check node queue status
curl "https://ceriferous-hoelike-jeffie.ngrok-free.dev/api/nodes" | jq '.nodes'
```

Your job is assigned to the node with the shortest queue.

### Where are my results stored?

**Two locations:**

1. **In the database** - Retrieved via API in the `stdout` field
   - Contains the **actual results.jsonl file** from `/home/gpuuser/work/results.jsonl`
   - This is your model's predictions/output in JSONL format

2. **On the server** - Saved as `{user}_{competition}_{timestamp}.jsonl` in `jobs/results/`
   - Example: `alice_random-acts-of-pizza_20251107_213621.jsonl`

**To get your results:**
```bash
curl -s -H "Authorization: Bearer $TOKEN" \
  "https://ceriferous-hoelike-jeffie.ngrok-free.dev/api/results/$JOB_ID" | \
  jq -r '.stdout' > my_results.jsonl
```

### What if my job fails?

**Check the error:**
```bash
curl -s -H "Authorization: Bearer $TOKEN" \
  "https://ceriferous-hoelike-jeffie.ngrok-free.dev/api/results/$JOB_ID" | \
  jq -r '.stderr'
```

**Common issues:**
- Missing `./submission.csv` output file
- Code syntax errors
- Job timeout (ran longer than expected_time × 2)
- Invalid competition_id

**Fix your code and resubmit!**

---

## Complete Workflow Example

**Full end-to-end submission:**

```bash
# 1. Set your credentials
export SERVER_URL="https://ceriferous-hoelike-jeffie.ngrok-free.dev"
export TOKEN="your_secret_token_xyz"

# 2. Submit job and capture job ID
JOB_ID=$(curl -s -X POST $SERVER_URL/api/submit \
  -F "code=@solution.py" \
  -F "config_file=@config.yaml" | jq -r '.job_id')

echo "Job ID: $JOB_ID"

# 3. Monitor status
while true; do
  STATUS=$(curl -s -H "Authorization: Bearer $TOKEN" \
    "$SERVER_URL/api/status/$JOB_ID" | jq -r '.status')
  echo "Status: $STATUS"
  
  if [[ "$STATUS" == "completed" || "$STATUS" == "failed" ]]; then
    break
  fi
  
  sleep 10
done

# 4. Get results
curl -s -H "Authorization: Bearer $TOKEN" \
  "$SERVER_URL/api/results/$JOB_ID" | \
  jq -r '.stdout' > results.jsonl

echo "✓ Results saved to results.jsonl"
cat results.jsonl | head -5
```

---

## Quick Reference

| Task | Command |
|------|---------|
| Submit job | `curl -X POST -F "code=@solution.py" -F "config_file=@config.yaml" $SERVER_URL/api/submit` |
| Get job ID | `curl ... \| jq -r '.job_id'` |
| Check status | `curl -H "Authorization: Bearer $TOKEN" $SERVER_URL/api/status/$JOB_ID` |
| Get results.jsonl | `curl -s -H "Authorization: Bearer $TOKEN" $SERVER_URL/api/results/$JOB_ID \| jq -r '.stdout' > results.jsonl` |
| List your jobs | `curl -H "Authorization: Bearer $TOKEN" $SERVER_URL/api/jobs` |
| Cancel job | `curl -X POST -H "Authorization: Bearer $TOKEN" $SERVER_URL/api/cancel/$JOB_ID` |
| View nodes | `curl $SERVER_URL/api/nodes` |

### Set Variables Once

```bash
export SERVER_URL="https://ceriferous-hoelike-jeffie.ngrok-free.dev"
export TOKEN="your_secret_token_xyz"
export JOB_ID="your-job-id-here"
```

Then use `$SERVER_URL`, `$TOKEN`, `$JOB_ID` in commands above.

---

## Important Notes

### What is results.jsonl?

The `stdout` field in `/api/results/{job_id}` contains the **actual results.jsonl file** created by the grading system, NOT your console output.

**This file contains:**
- Your model's predictions in JSONL format
- Competition grading information
- Scores and metrics

**This file does NOT contain:**
- Your print() statements
- Training logs
- Debug output

### Getting Your Job ID

Always shown in submit response:
```bash
curl -X POST ... > response.json
cat response.json | jq -r '.job_id'
```

Or list your recent jobs:
```bash
curl -s -H "Authorization: Bearer $TOKEN" \
  "$SERVER_URL/api/jobs" | jq -r '.jobs[0].job_id'
```

---

## Need Help?

- **Admin Contact:** Contact your administrator for token issues or competition IDs
- **API Docs:** `https://ceriferous-hoelike-jeffie.ngrok-free.dev/docs` for interactive documentation
- **Full Guide:** See `USER_GUIDE.md` for complete details

---

**Happy coding! 🚀**

