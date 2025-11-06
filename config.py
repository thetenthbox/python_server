"""
Configuration for GPU Job Queue Server
"""

# GPU Node Configuration
GPU_NODES = [
    {"id": 0, "ip": "10.221.102.181"},
    {"id": 1, "ip": "10.221.102.97"},
    {"id": 2, "ip": "10.221.102.26"},
    {"id": 3, "ip": "10.221.102.202"},
    {"id": 4, "ip": "10.221.102.173"},
    {"id": 5, "ip": "10.221.102.174"},
    {"id": 6, "ip": "10.221.102.153"},
    {"id": 7, "ip": "10.221.102.177"},
]

# Jump Host Configuration
# Server connects to GPU nodes through this SSH jump host
JUMP_HOST = "ce084d48-001.cloud.together.ai"
JUMP_USER = "vishal"
JUMP_SSH_KEY = None  # Path to SSH key, or None to use default ~/.ssh/id_rsa

# GPU Node SSH Configuration
SSH_USERNAME = "gpuuser"
SSH_PASSWORD = "h100node"
SSH_PORT = 22
SSH_TIMEOUT = 30

# Server Configuration
SERVER_HOST = "0.0.0.0"
SERVER_PORT = 8001
DATABASE_URL = "sqlite:///./database.db"
JOBS_DIR = "./jobs"

# Job Configuration
MAX_JOB_TIMEOUT_MULTIPLIER = 2  # Kill job if it runs 2x expected_time
WORKER_POLL_INTERVAL = 1  # seconds
SSH_RETRY_ATTEMPTS = 3

# LXC Configuration
LXC_RESTART_BETWEEN_JOBS = False  # Set to True to restart containers between jobs
LXC_CONTAINER_PREFIX = "gpu-node"  # Container naming: gpu-node-0, gpu-node-1, etc.
LXC_RESTART_WAIT_TIME = 30  # Seconds to wait after restart

# Code Scanner Configuration
CODE_SCANNER_ENABLED = False  # Disabled for testing (enable when API key is set)
CODE_SCANNER_QUICK_MODE = False  # Use only static analysis (faster, less thorough)
OPENROUTER_API_KEY = None  # Set via environment variable OPENROUTER_API_KEY

