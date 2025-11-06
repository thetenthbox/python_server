# GPU Job Queue Server - Administrator Guide

Complete guide for system administrators managing the GPU job queue server.

## Table of Contents

- [System Overview](#system-overview)
- [Installation & Setup](#installation--setup)
- [Token Management](#token-management)
- [User Management](#user-management)
- [Monitoring & Dashboard](#monitoring--dashboard)
- [Advanced Features](#advanced-features)
- [Troubleshooting](#troubleshooting)
- [Security](#security)

## System Overview

### Architecture

```
┌─────────────┐     SSH      ┌──────────────┐     SSH      ┌──────────────┐
│   Client    │────────────▶│  Jump Host   │────────────▶│  GPU Nodes   │
│  (FastAPI)  │              │              │              │   (LXC)      │
└─────────────┘              └──────────────┘              └──────────────┘
       │
       ▼
┌─────────────┐
│  SQLite DB  │
└─────────────┘
```

**Components:**
- **FastAPI Server**: REST API for job submission and management
- **SQLite Database**: Job metadata, tokens, and user information
- **SSH Executor**: Manages SSH connections to GPU nodes via jump host
- **Queue Manager**: Load balances jobs across 8 GPU nodes
- **Worker Threads**: Execute jobs on GPU nodes

### Key Features

- ✅ Token-based authentication (user & admin roles)
- ✅ Rate limiting (5 submissions/min per user)
- ✅ Queue management (1 active job per user)
- ✅ SSH resilience (auto-reconnect, keep-alive)
- ✅ Code scanning (OpenRouter API integration)
- ✅ LXC container restart support
- ✅ Comprehensive dashboard API
- ✅ Authorization & access control

## Installation & Setup

### Prerequisites

```bash
# Python 3.9+
python3 --version

# SSH access to GPU cluster
ssh-keygen -t rsa  # Generate SSH keys
```

### Installation

```bash
# 1. Clone repository
git clone https://github.com/thetenthbox/python_server.git
cd python_server

# 2. Install dependencies
pip3 install -r requirements.txt

# 3. Configure SSH access
# Add your SSH key to jump host and GPU nodes

# 4. Update configuration
vim config.py
```

### Configuration (`config.py`)

```python
# SSH Configuration
JUMP_HOST = "your-jump-host.com"
JUMP_PORT = 22
JUMP_USER = "your-username"
GPU_NODE_PREFIX = "gpu-node-"
GPU_NODE_PORT = 22
GPU_USER = "gpuuser"

# Server Configuration
SERVER_HOST = "0.0.0.0"
SERVER_PORT = 8001

# Security
RATE_LIMIT_PER_MINUTE = 5
MAX_ACTIVE_JOBS_PER_USER = 1

# LXC Configuration
LXC_RESTART_BETWEEN_JOBS = False
LXC_CONTAINER_PREFIX = "gpu-node"

# Code Scanner
CODE_SCANNER_ENABLED = True
OPENROUTER_API_KEY = "your-api-key"  # Set via env var
```

### Starting the Server

```bash
# Start server
python3 main.py

# Or run in background
nohup python3 main.py > server.log 2>&1 &

# Check logs
tail -f server.log
```

### Stopping the Server

```bash
# Find process
lsof -ti:8001

# Kill process
kill $(lsof -ti:8001)

# Or force kill
lsof -ti:8001 | xargs kill -9
```

## Token Management

### Creating Tokens

**Regular User Token:**
```bash
python3 token_manager.py create john_doe johns_secure_token --days 30
```

**Admin Token:**
```bash
python3 token_manager.py create admin_user admin_secure_token --days 30 --admin
```

**Token Features:**
- Maximum validity: 30 days
- One active token per user (creating new token revokes old one)
- Cryptographically hashed in database
- Tied to specific user_id

### Listing Tokens

```bash
python3 token_manager.py list

# Output:
# ╔══════════════════════════════════════════════════════════════╗
# ║                     ACTIVE TOKENS                             ║
# ╚══════════════════════════════════════════════════════════════╝
#
# User: john_doe
#   Admin: No
#   Created: 2025-11-06 10:30:00 UTC
#   Expires: 2025-12-06 10:30:00 UTC
#   Days until expiry: 30
```

### Revoking Tokens

```bash
python3 token_manager.py revoke johns_secure_token

# Or revoke by user
python3 token_manager.py revoke-user john_doe
```

### Token Security

- Tokens are hashed using SHA-256
- Only hash is stored in database
- Tokens expire after 30 days
- Automatic revocation on new token creation

## User Management

### User Roles

**Regular Users:**
- Submit jobs
- View own jobs only
- Cancel own jobs only
- Limited to 5 submissions/min
- Maximum 1 active job

**Admin Users:**
- All regular user permissions
- View all jobs from all users
- Cancel any job
- Access dashboard with full statistics
- No rate limits (optional)

### Creating Users

1. Create token for user:
```bash
python3 token_manager.py create username user_token_123 --days 30
```

2. Provide to user:
   - Server URL
   - User ID (username)
   - Token
   - USER_GUIDE.md

### Monitoring User Activity

```bash
# View all jobs
curl -H "Authorization: Bearer ADMIN_TOKEN" \
  "http://localhost:8001/api/jobs?user_id=admin_user"

# Filter by user
curl -H "Authorization: Bearer ADMIN_TOKEN" \
  "http://localhost:8001/api/jobs?user_id=admin_user" | \
  jq '.[] | select(.user_id == "john_doe")'

# View dashboard (admin only)
curl -H "Authorization: Bearer ADMIN_TOKEN" \
  "http://localhost:8001/api/dashboard?user_id=admin_user"
```

## Monitoring & Dashboard

### Dashboard API

**Admin-only endpoint providing comprehensive system metrics:**

```bash
curl -H "Authorization: Bearer ADMIN_TOKEN" \
  "http://localhost:8001/api/dashboard?user_id=admin_user"
```

**Response includes:**
```json
{
  "timestamp": "2025-11-06T21:30:00",
  "user_id": "admin_user",
  "is_admin": true,
  "job_statistics": {
    "total": 150,
    "pending": 5,
    "running": 3,
    "completed": 140,
    "failed": 2,
    "cancelled": 0
  },
  "user_statistics": {
    "john_doe": {
      "total": 20,
      "pending": 1,
      "running": 0,
      "completed": 19,
      "failed": 0
    }
  },
  "node_statistics": [...],
  "queue_information": [
    {
      "node_id": 0,
      "queue_size": 2,
      "queue_time_seconds": 300,
      "is_busy": true,
      "current_job": {
        "job_id": "abc123",
        "user_id": "john_doe",
        "competition_id": "cifar10"
      }
    }
  ],
  "active_jobs": [...],
  "recent_jobs": [...],
  "health_metrics": {
    "node_utilization_percent": 37.5,
    "average_queue_time_seconds": 150.5,
    "total_active_jobs": 8,
    "success_rate_percent": 98.5,
    "jobs_last_24h": 45
  }
}
```

### Python Dashboard Client

```python
import requests
import time

SERVER_URL = "http://localhost:8001"
ADMIN_TOKEN = "your-admin-token"

def get_dashboard():
    response = requests.get(
        f"{SERVER_URL}/api/dashboard?user_id=admin_user",
        headers={'Authorization': f'Bearer {ADMIN_TOKEN}'}
    )
    return response.json()

# Live monitoring
while True:
    data = get_dashboard()
    
    print(f"\n{'='*60}")
    print(f"System Status - {data['timestamp']}")
    print(f"{'='*60}")
    
    stats = data['job_statistics']
    print(f"Total Jobs: {stats['total']}")
    print(f"  Running: {stats['running']}")
    print(f"  Pending: {stats['pending']}")
    print(f"  Completed: {stats['completed']}")
    
    health = data['health_metrics']
    print(f"\nNode Utilization: {health['node_utilization_percent']}%")
    print(f"Success Rate: {health['success_rate_percent']}%")
    
    time.sleep(30)  # Update every 30 seconds
```

See `dashboard_example.py` for complete implementation.

### Node Status

```bash
# Check node availability
curl "http://localhost:8001/api/nodes"

# Response:
# [
#   {"node_id": 0, "queue_length": 2, "total_wait_time": 300},
#   {"node_id": 1, "queue_length": 0, "total_wait_time": 0},
#   ...
# ]
```

### Viewing Logs

```bash
# Server logs
tail -f server.log

# Filter for errors
tail -f server.log | grep ERROR

# Filter for specific user
tail -f server.log | grep "user_id=john_doe"

# Job submission logs
grep "Job.*submitted" server.log

# Job completion logs
grep "Job.*finished" server.log
```

## Advanced Features

### Code Scanning (OpenRouter API)

Scans submitted code for malicious content and ML relevance.

**Setup:**
```bash
# Set API key
export OPENROUTER_API_KEY="your-key"

# Enable in config.py
CODE_SCANNER_ENABLED = True
CODE_SCANNER_QUICK_MODE = False  # False = full scan with LLM
```

**Features:**
- Static analysis for dangerous patterns
- LLM-based code analysis (optional)
- Automatic rejection of malicious code
- Warnings for non-ML code

### LXC Container Restart

Restart GPU node containers between jobs for clean environment.

**Configuration:**
```python
# config.py
LXC_RESTART_BETWEEN_JOBS = True
LXC_CONTAINER_PREFIX = "gpu-node"
LXC_RESTART_WAIT_TIME = 30
```

**Manual Restart:**
```python
from ssh_executor import SSHExecutor

executor = SSHExecutor(node_id=0)
executor.connect()
executor.restart_node_lxc("gpu-node-0")
```

### SSH Resilience

Built-in SSH connection management:
- Keep-alive (60s intervals)
- Auto-reconnect on disconnect
- Retry with exponential backoff
- Connection health checks

**Features:**
- Jobs continue even if SSH drops
- Transparent reconnection
- No manual intervention needed

### Rate Limiting Configuration

**Per-User Limits:**
```python
# config.py
RATE_LIMIT_PER_MINUTE = 5  # Max submissions per minute
MAX_ACTIVE_JOBS_PER_USER = 1  # Max concurrent jobs
```

**IP-Based Limits:**
```python
# rate_limiter.py
ENDPOINT_LIMITS = {
    'submit': 5,  # 5 requests per minute
    'status': 60,
    'results': 60,
    'cancel': 10,
    'jobs': 30
}
```

### Database Management

**Backup:**
```bash
# Backup database
cp database.db database.backup.$(date +%Y%m%d).db

# Scheduled backup (cron)
0 2 * * * cp /path/to/database.db /path/to/backups/database.$(date +\%Y\%m\%d).db
```

**Clean Old Jobs:**
```bash
sqlite3 database.db "DELETE FROM jobs WHERE created_at < datetime('now', '-30 days');"
```

**View Database:**
```bash
sqlite3 database.db

# View all jobs
SELECT job_id, user_id, status, created_at FROM jobs ORDER BY created_at DESC LIMIT 10;

# View active tokens
SELECT user_id, is_admin, expires_at FROM tokens WHERE is_active = 1;

# User statistics
SELECT user_id, COUNT(*) as total_jobs FROM jobs GROUP BY user_id;
```

## API Reference (Admin)

### All Endpoints

#### POST `/api/submit`
Submit new job (any user)

#### GET `/api/status/{job_id}`
Get job status (owner or admin)

#### GET `/api/results/{job_id}`
Get job results (owner or admin)

#### POST `/api/cancel/{job_id}`
Cancel job (owner or admin)

#### GET `/api/jobs`
List jobs (filtered by user unless admin)

#### GET `/api/nodes`
Get node statistics (any user)

#### GET `/api/dashboard`
**Admin only** - Comprehensive system metrics

### Admin-Specific Operations

**View Any User's Jobs:**
```bash
curl -H "Authorization: Bearer ADMIN_TOKEN" \
  "http://localhost:8001/api/jobs?user_id=admin_user"
```

**Cancel Any Job:**
```bash
curl -X POST \
  -H "Authorization: Bearer ADMIN_TOKEN" \
  "http://localhost:8001/api/cancel/JOB_ID?user_id=admin_user"
```

**Access Dashboard:**
```bash
curl -H "Authorization: Bearer ADMIN_TOKEN" \
  "http://localhost:8001/api/dashboard?user_id=admin_user"
```

## Testing

### Running Tests

```bash
# Run comprehensive test suite
python3 tests/super_test.py

# Run specific tests
python3 tests/test_authorization.py
python3 tests/test_security.py
python3 tests/test_ssh_resilience.py
```

### Test Coverage

- Server health & connectivity
- Job submission & execution
- Authorization & access control
- Admin privileges
- Rate limiting
- SSH resilience
- Token management

## Troubleshooting

### Server Won't Start

```bash
# Check if port is in use
lsof -ti:8001

# Kill existing process
lsof -ti:8001 | xargs kill -9

# Check logs
tail -50 server.log

# Verify SSH configuration
ssh -v JUMP_USER@JUMP_HOST
```

### SSH Connection Issues

```bash
# Test SSH connection
ssh JUMP_USER@JUMP_HOST

# Test GPU node access (from jump host)
ssh GPU_USER@gpu-node-0

# Check SSH keys
ls -la ~/.ssh/

# Verify SSH agent
eval $(ssh-agent)
ssh-add ~/.ssh/id_rsa
```

### Jobs Stuck in Pending

```bash
# Check node status
curl "http://localhost:8001/api/nodes"

# Check worker threads
tail -f server.log | grep "Worker"

# Restart server
lsof -ti:8001 | xargs kill -9
python3 main.py
```

### Database Issues

```bash
# Verify database
sqlite3 database.db "SELECT COUNT(*) FROM jobs;"

# Check for corruption
sqlite3 database.db "PRAGMA integrity_check;"

# Reset database (WARNING: deletes all data)
rm database.db
python3 main.py  # Recreates database
```

### High Memory Usage

```bash
# Check memory
top -pid $(lsof -ti:8001)

# Clean old jobs
sqlite3 database.db "DELETE FROM jobs WHERE status = 'completed' AND created_at < datetime('now', '-7 days');"

# Clear result files
find jobs/results -name "*.jsonl" -mtime +7 -delete
```

## Security

### Best Practices

1. **SSH Keys**
   - Use key-based authentication only
   - Protect private keys with passphrase
   - Rotate keys regularly

2. **Tokens**
   - Generate cryptographically secure tokens
   - Enforce 30-day expiry
   - Revoke compromised tokens immediately

3. **Network**
   - Run behind firewall
   - Use HTTPS in production (add reverse proxy)
   - Restrict access by IP if possible

4. **Code Scanning**
   - Enable OpenRouter API scanning
   - Review flagged submissions manually
   - Whitelist trusted users if needed

5. **Monitoring**
   - Check dashboard regularly
   - Monitor for unusual activity
   - Set up alerts for failures

### Security Checklist

- [ ] SSH keys configured and protected
- [ ] All admin tokens unique and secure
- [ ] Code scanner enabled
- [ ] Rate limiting configured
- [ ] Database backups scheduled
- [ ] Logs monitored
- [ ] Network access restricted
- [ ] HTTPS enabled (production)

## Maintenance

### Daily Tasks

- Check dashboard for anomalies
- Review failed jobs
- Monitor disk space

### Weekly Tasks

- Review user activity
- Backup database
- Clean old results files
- Check SSH connections

### Monthly Tasks

- Rotate admin tokens
- Review and update documentation
- Test disaster recovery
- Update dependencies

## Documentation Index

- **USER_GUIDE.md**: For end users
- **ADMIN_GUIDE.md**: This file (for administrators)
- **documentation/API_DOCUMENTATION.md**: Complete API reference
- **documentation/ACCESS_CONTROL.md**: Authorization details
- **documentation/CODE_SCANNING.md**: Code scanner setup
- **documentation/DASHBOARD_API.md**: Dashboard endpoint docs
- **documentation/SSH_CONNECTION_ISSUES.md**: SSH troubleshooting
- **tests/README.md**: Testing guide

---

## Quick Reference

```bash
# Start server
python3 main.py

# Create user token
python3 token_manager.py create username token_value --days 30

# Create admin token
python3 token_manager.py create admin admin_token --days 30 --admin

# List tokens
python3 token_manager.py list

# View dashboard
curl -H "Authorization: Bearer ADMIN_TOKEN" \
  "http://localhost:8001/api/dashboard?user_id=admin_user"

# Run tests
python3 tests/super_test.py

# Backup database
cp database.db database.backup.$(date +%Y%m%d).db
```

---

**For questions or issues, refer to the documentation directory or contact the development team.**

