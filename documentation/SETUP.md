# GPU Job Queue Server - Setup Guide

## Running on Your MacBook

### 1. Copy Files to MacBook

```bash
# On your MacBook terminal
scp -r vishal@ce084d48-001.cloud.together.ai:/home/vishal/python_server ~/
cd ~/python_server
```

### 2. Setup SSH Access

The server uses SSH jump host to connect to GPU nodes. Setup passwordless SSH:

```bash
# Setup SSH key (if you don't have one)
ssh-keygen -t rsa -b 4096

# Copy key to jump host
ssh-copy-id vishal@ce084d48-001.cloud.together.ai

# Test (should work without password)
ssh vishal@ce084d48-001.cloud.together.ai exit
```

### 3. Install Dependencies

```bash
cd ~/python_server
pip3 install -r requirements.txt
```

### 4. Create Authentication Token

```bash
python3 token_manager.py create myuser "my-secret-token" --days 30
```

### 5. Start Server

```bash
python3 main.py
```

Server runs on: `http://localhost:8000`

### 6. Test It

**Open another terminal:**

```bash
# Test server is running
curl http://localhost:8000/

# Create test job
cat > test.py << 'EOF'
import socket
print(f"Running on: {socket.gethostname()}")
print("Hello from GPU!")
EOF

cat > config.yaml << 'EOF'
competition_id: "test"
project_id: "test"
user_id: "myuser"
expected_time: 5
token: "my-secret-token"
EOF

# Submit job
curl -X POST http://localhost:8000/api/submit \
  -F "code=@test.py" \
  -F "config_file=@config.yaml"

# You'll get a job_id in response
# Check status: curl http://localhost:8000/api/status/<job_id>
```

## Share with Other Users

### Option 1: Local Network (Same WiFi)

Find your MacBook's IP:
```bash
ifconfig | grep "inet " | grep -v 127.0.0.1
```

Share with users: `http://<your-ip>:8000`

### Option 2: Public URL (ngrok)

```bash
# Install ngrok
brew install ngrok

# Terminal 1: Run server
python3 main.py

# Terminal 2: Expose publicly  
ngrok http 8000
```

Share the ngrok URL with users.

## Configuration

Edit `config.py` if needed:

```python
# Jump host (change if using different username)
JUMP_USER = "vishal"  # Your username for jump host

# Server port (change if 8000 is taken)
SERVER_PORT = 8000
```

## Troubleshooting

**SSH Connection Fails:**
```bash
# Test jump host
ssh vishal@ce084d48-001.cloud.together.ai

# Test GPU node via jump
ssh -J vishal@ce084d48-001.cloud.together.ai gpuuser@10.221.102.181
```

**Port Already in Use:**
Edit `config.py` and change `SERVER_PORT = 8080`

**Dependencies Error:**
```bash
python3 -m pip install --upgrade pip
python3 -m pip install -r requirements.txt
```

## Token Management

```bash
# Create token
python3 token_manager.py create <user_id> "<token>" --days 30

# List tokens
python3 token_manager.py list

# Revoke token
python3 token_manager.py revoke "<token>"
```

## Running in Background

```bash
# Start in background
nohup python3 main.py > server.log 2>&1 &

# Check logs
tail -f server.log

# Stop server
pkill -f "python3 main.py"
```

## Complete Documentation

- `README.md` - Full API documentation
- `example_job.py` - Example job script
- `example_config.yaml` - Example config file

## API Docs

Once server is running, visit: `http://localhost:8000/docs`

