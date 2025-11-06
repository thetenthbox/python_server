# GPU Job Queue Server

A Python API server that manages and executes jobs across 8 H100 GPU nodes via SSH. Run the server on your local machine and submit GPU jobs remotely.

## Features

- 🚀 REST API for job submission and management
- 🎯 Intelligent load balancing across 8 GPU nodes
- 🔒 Token-based authentication
- 📊 Job queue with real-time status tracking
- ❌ Job cancellation (queued and running)
- 💾 SQLite persistence
- 🔀 Multi-threaded worker pool
- 🌐 SSH jump host support for remote access

## Architecture

```
[Users] → [Your Server] → [SSH Jump Host] → [8 GPU Nodes]
          (localhost:8000)  (ce084d48-001)    (10.221.102.x)
```

The server runs on your local machine and:
1. Receives API requests from users
2. Connects through SSH jump host to GPU nodes
3. Executes Python jobs remotely on GPUs
4. Returns results to users

## Quick Start

### Prerequisites

- Python 3.8+
- SSH access to jump host (`ce084d48-001.cloud.together.ai`)
- SSH key authentication setup

### 1. Setup SSH Access

Ensure passwordless SSH to jump host:

```bash
# Setup SSH key (if not done)
ssh-copy-id vishal@ce084d48-001.cloud.together.ai

# Test connection
ssh vishal@ce084d48-001.cloud.together.ai exit
```

### 2. Install Server

```bash
# Copy server files to your machine
scp -r vishal@ce084d48-001.cloud.together.ai:/home/vishal/python_server ~/

# Navigate to directory
cd ~/python_server

# Install dependencies
pip3 install -r requirements.txt
```

### 3. Configure

Edit `config.py` if needed:

```python
# Jump host credentials
JUMP_HOST = "ce084d48-001.cloud.together.ai"
JUMP_USER = "vishal"  # Your username
JUMP_SSH_KEY = None   # Or path to your SSH key

# Server settings
SERVER_HOST = "0.0.0.0"
SERVER_PORT = 8000
```

### 4. Create Authentication Token

```bash
python3 token_manager.py create myuser "my-secret-token" --days 30
```

### 5. Start Server

```bash
python3 main.py
```

Server starts on `http://localhost:8000`

## API Usage

### Submit Job

Create your Python script and config:

**my_script.py:**
```python
import time
print("Hello from GPU!")
time.sleep(5)
print("Job complete!")
```

**config.yaml:**
```yaml
competition_id: "comp123"
project_id: "proj456"
user_id: "myuser"
expected_time: 10  # seconds
token: "my-secret-token"
```

**Submit:**
```bash
curl -X POST http://localhost:8000/api/submit \
  -F "code=@my_script.py" \
  -F "config_file=@config.yaml"
```

**Response:**
```json
{
  "job_id": "abc-123-uuid",
  "node_id": 3,
  "status": "pending",
  "queue_position": 0
}
```

### Check Status

```bash
curl http://localhost:8000/api/status/abc-123-uuid
```

### Get Results

```bash
curl http://localhost:8000/api/results/abc-123-uuid
```

**Response:**
```json
{
  "job_id": "abc-123-uuid",
  "status": "completed",
  "stdout": "Hello from GPU!\nJob complete!\n",
  "stderr": "",
  "exit_code": 0
}
```

### Cancel Job

```bash
curl -X POST http://localhost:8000/api/cancel/abc-123-uuid \
  -H "Authorization: Bearer my-secret-token"
```

### View Node Statistics

```bash
curl http://localhost:8000/api/nodes
```

### List Jobs

```bash
# All jobs
curl http://localhost:8000/api/jobs

# Filter by user
curl http://localhost:8000/api/jobs?user_id=myuser

# Filter by status
curl http://localhost:8000/api/jobs?status=running
```

## API Documentation

Interactive Swagger docs available at: `http://localhost:8000/docs`

## Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/` | Service info |
| POST | `/api/submit` | Submit new job |
| GET | `/api/status/{job_id}` | Get job status |
| GET | `/api/results/{job_id}` | Get job results |
| POST | `/api/cancel/{job_id}` | Cancel job |
| GET | `/api/nodes` | Node statistics |
| GET | `/api/jobs` | List jobs |

## Sharing with Other Users

### Local Network (Same WiFi)

Find your IP address:
```bash
# macOS/Linux
ifconfig | grep "inet " | grep -v 127.0.0.1

# Or
ipconfig getifaddr en0  # macOS
```

Users can access: `http://<your-ip>:8000`

### Public Access (ngrok)

```bash
# Install ngrok
brew install ngrok  # macOS
# or download from https://ngrok.com

# Expose server publicly
ngrok http 8000
```

Share the ngrok URL (e.g., `https://abc123.ngrok.io`) with users.

### User Setup

Each user needs:
1. **Server URL** - Your IP or ngrok URL
2. **Authentication token** - Created via token_manager.py
3. **Job files** - Python script + config.yaml

## Token Management

```bash
# Create token
python3 token_manager.py create <user_id> "<token>" --days 30

# List all tokens
python3 token_manager.py list

# Revoke token
python3 token_manager.py revoke "<token>"
```

## Job Lifecycle

```
Pending → Running → Completed
   ↓         ↓           ↓
Cancelled  Cancelled  Failed
```

- **Pending** - Waiting in queue
- **Running** - Executing on GPU
- **Completed** - Finished successfully
- **Failed** - Error or timeout
- **Cancelled** - User cancelled

## Load Balancing

Jobs are automatically assigned to the GPU node with the lowest total queue time, ensuring even distribution across all 8 nodes.

## Configuration

### config.py

```python
# GPU nodes (8 H100 GPUs)
GPU_NODES = [
    {"id": 0, "ip": "10.221.102.181"},
    # ... 7 more nodes
]

# Jump host
JUMP_HOST = "ce084d48-001.cloud.together.ai"
JUMP_USER = "vishal"

# GPU node credentials
SSH_USERNAME = "gpuuser"
SSH_PASSWORD = "h100node"

# Server settings
SERVER_PORT = 8000
MAX_JOB_TIMEOUT_MULTIPLIER = 2  # Kill if 2x expected_time
```

## Troubleshooting

### SSH Connection Failed

Test jump host:
```bash
ssh vishal@ce084d48-001.cloud.together.ai
```

Test GPU node via jump:
```bash
ssh -J vishal@ce084d48-001.cloud.together.ai gpuuser@10.221.102.181
```

### Port Already in Use

Change port in `config.py`:
```python
SERVER_PORT = 8080
```

### Dependencies Error

```bash
python3 -m pip install --upgrade pip
python3 -m pip install -r requirements.txt
```

### Job Stuck in Pending

- Check worker threads are running (look at server logs)
- Verify SSH connectivity to GPU nodes
- Check database connectivity

## Production Deployment

### Run as Background Service

```bash
# Start in background
nohup python3 main.py > server.log 2>&1 &

# Check logs
tail -f server.log

# Stop
pkill -f "python3 main.py"
```

### macOS: Keep Computer Awake

```bash
caffeinate -s python3 main.py
```

## Files

- `main.py` - Server entry point
- `api.py` - FastAPI endpoints
- `models.py` - Database models (SQLAlchemy)
- `queue_manager.py` - Job queue logic
- `worker.py` - Worker threads (8 workers, 1 per node)
- `ssh_executor.py` - SSH job execution via jump host
- `auth.py` - Token authentication
- `config.py` - Configuration
- `token_manager.py` - Token management CLI

## Database

SQLite database: `./database.db`

**Tables:**
- `jobs` - All job records
- `node_state` - GPU node status
- `tokens` - Authentication tokens

## Security Notes

- Use strong, unique tokens for each user
- Set token expiration dates
- Keep jump host SSH keys secure
- Consider HTTPS for production (use reverse proxy)
- Don't commit credentials to git

## Support

For issues or questions, check the server logs and verify:
1. SSH access to jump host works
2. GPU nodes are accessible via jump host
3. Port 8000 is available
4. All dependencies are installed

## License

This server is for internal use with the GPU cluster.
