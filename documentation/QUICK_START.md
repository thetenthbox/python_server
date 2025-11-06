# GPU Job Queue Server - Quick Start Guide

## 🚀 What This Does

Submit Python ML solutions → Run on H100 GPU → Get grading results + scores

## 📍 Server Info

- **URL**: `http://localhost:8001`
- **Docs**: `http://localhost:8001/docs`
- **User**: `sarang`
- **Token**: `sarang`

## 🎯 Basic Usage

### 1. Create Your Solution

```python
# my_solution.py
import pandas as pd
from sklearn.ensemble import RandomForestClassifier

# Load data from ./data/
train = pd.read_csv('./data/train.csv')
test = pd.read_csv('./data/test.csv')

# Your ML magic here
model = RandomForestClassifier()
# ... train model ...

# Generate submission
submission = pd.DataFrame({
    'id': test['id'],
    'prediction': predictions
})
submission.to_csv('./submission.csv', index=False)
```

### 2. Create Config

```yaml
# config.yaml
competition_id: "random-acts-of-pizza"
project_id: "my_project"
user_id: "sarang"
expected_time: 60
token: "sarang"
```

### 3. Submit & Get Results

```bash
curl -X POST http://localhost:8001/api/submit \
  -F "code=@my_solution.py" \
  -F "config_file=@config.yaml" \
  > results.json

# Extract score
cat results.json | python3 -c "
import sys, json
data = json.load(sys.stdin)
results = json.loads(data['stdout'])
print(f\"Score: {results['test_fitness']}\")
print(f\"Time: {results['exec_time']}s\")
"
```

## 📊 Understanding Results

The API returns:

```json
{
  "status": "completed",
  "stdout": "{...}",  // ← Parse this JSON for grading details
  "stderr": "",
  "exit_code": 0
}
```

**Parse the `stdout` field:**

```python
import json

results = json.loads(response['stdout'])

print(results['test_fitness'])        # Your score (e.g., 0.49272)
print(results['exec_time'])           # Execution time in seconds
print(results['valid_solution'])      # True if valid submission

# Medal thresholds
report = results['grading_report']
print(report['gold_threshold'])       # Score needed for gold
print(report['silver_threshold'])     # Score needed for silver
print(report['gold_medal'])           # True if you got gold
```

## 💾 Where Results Are Saved

Results automatically saved on server:
```
jobs/results/sarang_random-acts-of-pizza_20251106_154517.jsonl
                │           │                    │
              user_id  competition_id      timestamp
```

## ⚡ Quick Test

```bash
# 1. Start server
cd python_server_test/python_server
python3 main.py

# 2. Submit test job
curl -X POST http://localhost:8001/api/submit \
  -F "code=@python_test_file.py" \
  -F "config_file=@test_config.yaml"

# 3. Check results directory
ls -lht jobs/results/
```

## 🎓 What Competitions?

Common competition IDs:
- `random-acts-of-pizza`
- (Add more as available)

Ask your admin for the list of available competitions.

## 🔍 Monitoring

```bash
# Check GPU nodes status
curl http://localhost:8001/api/nodes | python3 -m json.tool

# List recent jobs
curl http://localhost:8001/api/jobs?limit=10 | python3 -m json.tool

# Get specific job
curl http://localhost:8001/api/results/JOB_ID | python3 -m json.tool
```

## ❌ Common Issues

**"Invalid or expired token"**
- Check `user_id` and `token` match in config

**"Job timed out"**
- Increase `expected_time` in config
- Use `/api/results/{job_id}` to check later

**"Invalid submission"**
- Ensure you create `submission.csv` in correct format
- Check competition requirements

**Score is 0**
- Your solution may have errors
- Check `stderr` field for error messages

## 📚 Full Documentation

See `API_DOCUMENTATION.md` for:
- All endpoints
- Detailed examples
- Python client code
- Error handling

## 🧪 Testing

Run basic tests:
```bash
cd tests
python3 run_basic_tests.py
```

## 🆘 Support

1. Check `stderr` in response for error messages
2. Verify competition ID is valid
3. Ensure submission.csv format matches requirements
4. Check server logs for detailed errors

