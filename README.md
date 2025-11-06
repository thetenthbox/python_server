# GPU Job Queue Server

A production-ready API server for managing and executing Python jobs on a GPU cluster with built-in authentication, authorization, rate limiting, and queue management.

## 🚀 Quick Start

```bash
# 1. Install dependencies
pip3 install -r requirements.txt

# 2. Start server
python3 main.py

# 3. Create a token
python3 token_manager.py create myuser mytoken

# 4. Submit a job
curl -X POST http://localhost:8001/api/submit \
  -F "code=@solution.py" \
  -F 'config_file=@-;type=application/json' <<EOF
{
  "competition_id": "test-comp",
  "project_id": "test-proj",
  "user_id": "myuser",
  "expected_time": 60,
  "token": "mytoken"
}
EOF
```

📖 **Full guide:** [documentation/QUICK_START.md](documentation/QUICK_START.md)

## 📚 Documentation

All documentation is organized in the [`documentation/`](documentation/) folder:

### Start Here
- **[Documentation Index](documentation/INDEX.md)** - Complete documentation overview
- **[Quick Start Guide](documentation/QUICK_START.md)** - Get running in 5 minutes
- **[API Documentation](documentation/API_DOCUMENTATION.md)** - Complete API reference

### Essential Guides
- **[Access Control & User Privileges](documentation/ACCESS_CONTROL.md)** ⭐ **NEW**
  - Regular vs Admin users
  - Permissions matrix
  - Authorization flow
  - Common use cases
- **[Setup Guide](documentation/SETUP.md)** - Production deployment
- **[Token Management](documentation/TOKEN_IMPLEMENTATION_SUMMARY.md)** - Creating & managing tokens

### Reference
- [Authorization Implementation](documentation/AUTHORIZATION_SUMMARY.md)
- [Testing Plan](documentation/TESTING_PLAN.md)
- [Potential Issues](documentation/POTENTIAL_ISSUES.md)
- [Token Security Analysis](documentation/TOKEN_MANAGEMENT_ANALYSIS.md)

## 🔐 User Roles

### Regular User
- ✅ Submit and manage own jobs
- ✅ View own job status and results
- ❌ Cannot access other users' jobs

```bash
python3 token_manager.py create alice alice_token
```

### Admin User
- ✅ View and manage ALL jobs
- ✅ Cancel any user's job
- ✅ System-wide monitoring

```bash
python3 token_manager.py create admin admin_token --admin
```

📖 **Full details:** [documentation/ACCESS_CONTROL.md](documentation/ACCESS_CONTROL.md)

## 🏗️ Architecture

```
┌─────────────┐
│   Client    │
└──────┬──────┘
       │ HTTP POST /api/submit
       ▼
┌─────────────────────────────┐
│      FastAPI Server         │
│  - Authentication           │
│  - Rate Limiting            │
│  - Job Queue Management     │
└──────┬──────────────────────┘
       │
       ▼
┌─────────────────────────────┐
│    Worker Threads (8)       │
│  - Execute jobs via SSH     │
│  - Monitor completion       │
└──────┬──────────────────────┘
       │
       ▼
┌─────────────────────────────┐
│   GPU Cluster Nodes (8)     │
│  - Run Python code          │
│  - Return results           │
└─────────────────────────────┘
```

## ✨ Key Features

- **🔒 Secure Authentication** - Token-based auth with user isolation
- **👑 Admin Role** - Elevated privileges for system management
- **⚡ Rate Limiting** - 5 submissions/min per user
- **📊 Queue Management** - Intelligent load balancing across 8 GPU nodes
- **🔄 Job Control** - Submit, monitor, and cancel jobs
- **📝 Results Storage** - Automatic local storage with naming `{user}_{comp}_{time}.jsonl`
- **🛡️ Security** - Token expiration (30 days), one token per user

## 🧪 Testing

All tests are in the [`tests/`](tests/) folder:

```bash
cd tests

# Basic functionality
python3 run_basic_tests.py

# Authorization
python3 test_authorization.py

# Security
python3 test_security.py

# Token management
python3 test_token_management.py
```

📖 **Full guide:** [tests/README.md](tests/README.md)

## 📡 API Endpoints

| Endpoint | Method | Description | Auth |
|----------|--------|-------------|------|
| `/api/submit` | POST | Submit a job | Token in config |
| `/api/status/{job_id}` | GET | Get job status | Bearer token |
| `/api/results/{job_id}` | GET | Get job results | Bearer token |
| `/api/cancel/{job_id}` | POST | Cancel job | Bearer token |
| `/api/jobs` | GET | List jobs | Bearer token |
| `/api/nodes` | GET | Node statistics | Public |

📖 **Full reference:** [documentation/API_DOCUMENTATION.md](documentation/API_DOCUMENTATION.md)

## 🔧 Configuration

Edit `config.py` to customize:

```python
SERVER_HOST = "0.0.0.0"
SERVER_PORT = 8001
GPU_NODE_HOST = "your-gpu-node.com"
GPU_NODE_USER = "gpuuser"
NUM_GPU_NODES = 8
```

## 🎯 Example Usage

### Regular User
```python
import requests
import json

BASE_URL = "http://localhost:8001"
TOKEN = "alice_token"

# Submit job
code = open("solution.py").read()
config = {
    'competition_id': 'comp-001',
    'project_id': 'proj-001',
    'user_id': 'alice',
    'expected_time': 60,
    'token': TOKEN
}

files = {
    'code': ('solution.py', code, 'text/x-python'),
    'config_file': ('config.json', json.dumps(config), 'application/json')
}

response = requests.post(f"{BASE_URL}/api/submit", files=files)
print(f"Job ID: {response.json()['job_id']}")
print(f"Status: {response.json()['status']}")
```

### Admin User
```python
import requests

BASE_URL = "http://localhost:8001"
ADMIN_TOKEN = "admin_token"
headers = {'Authorization': f'Bearer {ADMIN_TOKEN}'}

# View all jobs
response = requests.get(f"{BASE_URL}/api/jobs", headers=headers)
all_jobs = response.json()['jobs']
print(f"Total jobs: {len(all_jobs)}")

# Cancel any job
response = requests.post(
    f"{BASE_URL}/api/cancel/some-job-id",
    headers=headers
)
print(f"Cancelled: {response.status_code == 200}")
```

## 🛠️ Token Management

```bash
# Create regular user token
python3 token_manager.py create alice alice_secret_token

# Create admin token (elevated privileges)
python3 token_manager.py create admin admin_secret_token --admin

# Create token with custom expiry (max 30 days)
python3 token_manager.py create bob bob_token --days 15

# List all tokens
python3 token_manager.py list

# Revoke token
python3 token_manager.py revoke alice_secret_token
```

## 📊 Monitoring

### Check Node Status
```bash
curl http://localhost:8001/api/nodes
```

### View Jobs (as admin)
```bash
curl -H "Authorization: Bearer admin_token" \
     http://localhost:8001/api/jobs
```

## 🔒 Security Features

1. **Token-User Binding** - Tokens permanently tied to user_id
2. **User Isolation** - Users can only access their own jobs
3. **Admin Privileges** - Separate admin role for system management
4. **Rate Limiting** - Prevents API abuse
5. **Queue Limits** - 1 active job per user
6. **Token Expiration** - 30-day maximum lifetime
7. **One Token Per User** - Automatic revocation of old tokens

## 🐛 Troubleshooting

### Server won't start
```bash
# Kill existing process
lsof -ti:8001 | xargs kill -9

# Restart
python3 main.py
```

### Token issues
```bash
# Recreate token
python3 token_manager.py create myuser mytoken

# Check tokens
python3 token_manager.py list
```

### Database issues
```bash
# Backup and reset
cp database.db database.db.backup
rm database.db
python3 main.py  # Recreates database
```

## 📁 Project Structure

```
python_server/
├── main.py                  # Server entry point
├── api.py                   # FastAPI endpoints
├── auth.py                  # Authentication logic
├── models.py                # Database models
├── queue_manager.py         # Job queue management
├── worker.py                # Worker threads
├── ssh_executor.py          # SSH execution
├── rate_limiter.py          # Rate limiting
├── token_manager.py         # Token CLI tool
├── config.py                # Configuration
│
├── documentation/           # All documentation ⭐
│   ├── INDEX.md            # Documentation index
│   ├── ACCESS_CONTROL.md   # User roles & permissions
│   ├── API_DOCUMENTATION.md
│   ├── QUICK_START.md
│   └── ...
│
├── tests/                   # All tests ⭐
│   ├── README.md           # Test guide
│   ├── run_basic_tests.py
│   ├── test_authorization.py
│   └── ...
│
├── jobs/                    # Job files (auto-generated)
│   └── results/            # Results storage
│
└── database.db             # SQLite database
```

## 🚀 Production Deployment

1. **Configure SSH keys** for passwordless access to GPU nodes
2. **Set up database backups** (SQLite at `database.db`)
3. **Configure firewall** to allow only authorized IPs
4. **Enable HTTPS** with reverse proxy (nginx/caddy)
5. **Set up monitoring** (Prometheus/Grafana)
6. **Create admin tokens** for system management

📖 **Full guide:** [documentation/SETUP.md](documentation/SETUP.md)

## 📝 License

[Add your license here]

## 🤝 Contributing

1. Read the [Testing Plan](documentation/TESTING_PLAN.md)
2. Write tests for new features
3. Update documentation
4. Submit pull request

## 📧 Support

- **Documentation:** [documentation/INDEX.md](documentation/INDEX.md)
- **API Reference:** [documentation/API_DOCUMENTATION.md](documentation/API_DOCUMENTATION.md)
- **Issues:** [documentation/POTENTIAL_ISSUES.md](documentation/POTENTIAL_ISSUES.md)

---

**Version:** 2.0 (with access control)  
**Last Updated:** 2025-11-06

