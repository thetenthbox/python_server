# Code Execution Issues - Deep Analysis (Part 2)

*Continued from CODE_EXECUTION_ISSUES_PART1.md*

---

## Issue 8: Code Spawns Too Many Threads/Processes

### Potential Reasons/Sources
1. **Uncontrolled parallelism** - `multiprocessing.Pool()` without limits
2. **Threading bugs** - Creating threads in loop without joining
3. **Recursive process spawning** - Fork bomb (`os.fork()` in loop)
4. **ML framework parallelism** - PyTorch/TensorFlow worker threads
5. **Concurrent requests** - Spawning thread per request
6. **No resource limits** - System allows unlimited processes
7. **Error handling loops** - Respawning failed processes indefinitely

### Consequences
- **System overload** - CPU thrashing, context switching overhead
- **Memory exhaustion** - Each thread/process uses memory
- **Process table full** - Cannot create new processes
- **Node becomes unresponsive** - System load >100
- **Other jobs starved** - No CPU time left
- **Manual intervention required** - Force reboot needed
- **Fork bomb** - Classic denial of service

### Potential Fixes

**Set Process/Thread Limits:**
```python
# In ssh_executor.py
command = (
    f"ulimit -u 128; "  # Max 128 processes per user
    f"ulimit -t {expected_time}; "  # CPU time limit
    f"nohup bash -c '{grading_command}' & "
    f"echo $!"
)
```

**Use cgroups:**
```bash
# Create cgroup for job
cgcreate -g pids,cpu:job_${JOB_ID}
cgset -r pids.max=100 job_${JOB_ID}
cgset -r cpu.cfs_quota_us=100000 job_${JOB_ID}  # 1 CPU

# Run job in cgroup
cgexec -g pids,cpu:job_${JOB_ID} python3 solution.py

# Cleanup
cgdelete -g pids,cpu:job_${JOB_ID}
```

**Monitor Process Count:**
```python
def monitor_process_count(self, job_id: str, user: str = 'gpuuser'):
    """Monitor number of processes created by job"""
    cmd = f"ps -u {user} --no-headers | wc -l"
    count = int(self.exec_command(cmd).strip())
    
    if count > 100:
        logging.error(f"Job {job_id} spawned {count} processes")
        # Kill all user processes
        self.exec_command(f"killall -u {user}")
        return False
    
    return True
```

**Code Static Analysis:**
```python
def check_process_spawning(code: str) -> list:
    """Detect unlimited process/thread spawning"""
    warnings = []
    tree = ast.parse(code)
    
    dangerous_calls = {
        'fork': 'os.fork()',
        'Process': 'multiprocessing.Process',
        'Pool': 'multiprocessing.Pool',
        'Thread': 'threading.Thread',
        'ThreadPoolExecutor': 'concurrent.futures.ThreadPoolExecutor'
    }
    
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            if isinstance(node.func, ast.Attribute):
                if node.func.attr in dangerous_calls:
                    warnings.append(f"Found {dangerous_calls[node.func.attr]}")
            elif isinstance(node.func, ast.Name):
                if node.func.id in dangerous_calls:
                    warnings.append(f"Found {dangerous_calls[node.func.id]}")
    
    return warnings
```

**Container with PID Limit:**
```bash
# Run with Docker
docker run --rm \
  --pids-limit=50 \
  --cpus=1.0 \
  --memory=2g \
  user_code_image python3 solution.py
```

**Whitelist Safe Parallelism:**
```python
# In grade_code.py, set environment variables to limit parallelism
import os

# Limit thread pools
os.environ['OMP_NUM_THREADS'] = '4'
os.environ['OPENBLAS_NUM_THREADS'] = '4'
os.environ['MKL_NUM_THREADS'] = '4'
os.environ['NUMEXPR_NUM_THREADS'] = '4'

# PyTorch
os.environ['TORCH_NUM_THREADS'] = '4'

# TensorFlow
os.environ['TF_NUM_INTRAOP_PARALLELISM_THREADS'] = '4'
os.environ['TF_NUM_INTEROP_PARALLELISM_THREADS'] = '4'
```

---

## Issue 9: Code Uses All Available RAM - OOM Killer Triggers

### Potential Reasons/Sources
1. **Memory leak** - Accumulating data in loop without cleanup
2. **Large datasets** - Loading entire dataset into memory
3. **Model size** - Large neural network models
4. **Recursive algorithms** - Deep recursion building stack
5. **String concatenation** - Building massive strings in loop
6. **No garbage collection** - Holding references preventing GC
7. **Memory-mapped files** - Mapping huge files
8. **Swap disabled** - No swap space available

### Consequences
- **Job killed by OOM** - Linux kills process to free memory
- **Node instability** - System may freeze before OOM triggers
- **Other jobs killed** - OOM killer may target wrong process
- **No error message** - Process just disappears (exit code 137)
- **Data corruption** - Mid-write when killed
- **Cascading failures** - Multiple jobs affected
- **Swap thrashing** - If swap enabled, system becomes unusable

### Potential Fixes

**Memory Limits:**
```python
# In ssh_executor.py
command = (
    f"ulimit -v 2097152; "  # Limit virtual memory to 2GB (in KB)
    f"ulimit -m 2097152; "  # Limit physical memory to 2GB
    f"nohup bash -c '{grading_command}' & "
    f"echo $!"
)
```

**Container Memory Limits:**
```bash
docker run --rm \
  --memory=2g \
  --memory-swap=2g \
  --oom-kill-disable=false \
  user_code_image python3 solution.py
```

**Memory Monitoring:**
```python
def monitor_memory_usage(self, pid: int) -> dict:
    """Monitor memory usage of process"""
    cmd = f"ps -p {pid} -o rss,vsz,pmem --no-headers"
    output = self.exec_command(cmd).strip()
    
    if output:
        rss, vsz, pmem = output.split()
        return {
            'rss_mb': int(rss) / 1024,  # Resident set size
            'vsz_mb': int(vsz) / 1024,  # Virtual memory size
            'percent': float(pmem)
        }
    return {}

# In worker.py
while job.status == 'running':
    mem = executor.monitor_memory_usage(job.remote_pid)
    if mem.get('rss_mb', 0) > 1800:  # Approaching 2GB limit
        logging.warning(f"Job {job_id} using {mem['rss_mb']}MB")
        # Could kill proactively or just warn
    time.sleep(30)
```

**Python Memory Limits:**
```python
# In grade_code.py, add resource limits
import resource

# Limit to 2GB
max_memory = 2 * 1024 * 1024 * 1024  # 2GB in bytes
resource.setrlimit(resource.RLIMIT_AS, (max_memory, max_memory))

try:
    # Run user code
    exec(user_code)
except MemoryError:
    print("ERROR: Job exceeded memory limit", file=sys.stderr)
    sys.exit(1)
```

**Detect OOM Kill:**
```python
def check_oom_killed(self, pid: int) -> bool:
    """Check if process was killed by OOM"""
    # Check dmesg for OOM messages
    cmd = f"dmesg | grep -i 'killed process {pid}' | grep -i oom"
    output = self.exec_command(cmd)
    return bool(output.strip())

# In worker.py get_job_output
if job.exit_code == 137:  # SIGKILL
    if executor.check_oom_killed(job.remote_pid):
        job.stderr += "\n[SYSTEM ERROR] Process killed by OOM (out of memory)"
```

**Memory-Efficient Alternatives:**
```python
# Suggest in documentation
# BAD:
data = [x for x in range(1000000000)]  # Allocates huge list

# GOOD:
data = (x for x in range(1000000000))  # Generator, minimal memory

# BAD:
with open('huge.txt') as f:
    data = f.read()  # Loads entire file

# GOOD:
with open('huge.txt') as f:
    for line in f:  # Iterates line by line
        process(line)
```

---

## Issue 10: Code Creates Unkillable Processes

### Potential Reasons/Sources
1. **Ignoring signals** - Catching and ignoring SIGTERM/SIGKILL
2. **Uninterruptible sleep** - Waiting on I/O in D state
3. **Kernel deadlock** - Process stuck in kernel
4. **GPU driver issue** - CUDA kernel hung
5. **NFS hang** - Waiting on unresponsive network filesystem
6. **Zombie parent** - Process reparented to init but not reaped
7. **Container issues** - Process namespace problems

### Consequences
- **Cannot kill job** - `kill -9` doesn't work
- **Resource permanently locked** - GPU/memory unavailable
- **Node requires reboot** - Only way to clear
- **Production downtime** - Node offline during reboot
- **Manual intervention always required** - No automatic recovery
- **Queue blockage** - Jobs waiting for this node

### Potential Fixes

**Detection:**
```python
def detect_unkillable_process(self, pid: int) -> dict:
    """Check if process is in unkillable state"""
    # Check process state
    cmd = f"ps -p {pid} -o state,wchan --no-headers"
    output = self.exec_command(cmd).strip()
    
    if not output:
        return {'exists': False}
    
    state, wchan = output.split(maxsplit=1)
    
    return {
        'exists': True,
        'state': state,
        'wchan': wchan,  # What it's waiting on
        'unkillable': state == 'D',  # Uninterruptible sleep
        'zombie': state == 'Z'
    }
```

**Force Kill Attempts:**
```python
def force_kill_process(self, pid: int, job_id: str) -> bool:
    """Try multiple methods to kill process"""
    kill_attempts = [
        # 1. Graceful termination
        (f"kill -TERM {pid}", 5),
        
        # 2. Force kill
        (f"kill -9 {pid}", 5),
        
        # 3. Kill process group
        (f"kill -9 -{pid}", 5),
        
        # 4. Kill all child processes first
        (f"pkill -9 -P {pid}", 2),
        (f"kill -9 {pid}", 5),
        
        # 5. Try to kill via /proc
        (f"echo -9 > /proc/{pid}/signal", 2),
    ]
    
    for cmd, wait in kill_attempts:
        self.exec_command(cmd)
        time.sleep(wait)
        
        # Check if process still exists
        check = self.exec_command(f"ps -p {pid} --no-headers")
        if not check.strip():
            logging.info(f"Successfully killed {pid} with: {cmd}")
            return True
    
    # Process is unkillable
    logging.error(f"Cannot kill process {pid}")
    return False
```

**GPU Reset:**
```python
def reset_gpu_if_hung(self, node_id: int):
    """Reset GPU if hung"""
    # Check if GPU is responsive
    cmd = "timeout 5 nvidia-smi"
    try:
        output = self.exec_command(cmd)
        if not output:
            raise Exception("GPU not responding")
    except:
        logging.error(f"GPU {node_id} appears hung, attempting reset")
        
        # Try soft reset
        self.exec_command("nvidia-smi --gpu-reset")
        time.sleep(5)
        
        # Check if reset worked
        try:
            self.exec_command("nvidia-smi")
            logging.info(f"GPU {node_id} reset successful")
        except:
            logging.error(f"GPU {node_id} reset failed, node needs reboot")
            # Mark node as offline
            self.mark_node_offline(node_id)
```

**Automatic Node Reboot:**
```python
def reboot_node_if_necessary(self, node_id: int) -> bool:
    """Reboot node if it has unkillable processes"""
    # Check for D state processes
    cmd = "ps aux | awk '$8==\"D\" {count++} END {print count}'"
    d_count = int(self.exec_command(cmd).strip() or 0)
    
    if d_count > 5:
        logging.critical(f"Node {node_id} has {d_count} unkillable processes")
        
        # Send alert
        self.send_admin_alert(
            f"Node {node_id} requires reboot (unkillable processes)"
        )
        
        # Schedule reboot (if authorized)
        if self.auto_reboot_enabled:
            self.exec_command("sudo reboot")
            return True
    
    return False
```

**Prevent Signal Blocking:**
```python
# In grade_code.py
import signal

# Ensure SIGTERM cannot be ignored
def handle_sigterm(signum, frame):
    sys.exit(143)  # 128 + 15

signal.signal(signal.SIGTERM, handle_sigterm)

# SIGKILL cannot be caught, but we can handle SIGINT
signal.signal(signal.SIGINT, handle_sigterm)

# Run user code in separate process that can be killed
def run_user_code():
    try:
        exec(user_code)
    except:
        sys.exit(1)

# Parent can kill child even if child tries to block signals
pid = os.fork()
if pid == 0:
    run_user_code()
else:
    os.waitpid(pid, 0)
```

---

## Issue 11: Code Has Race Conditions Only Appearing on GPU Hardware

### Potential Reasons/Sources
1. **GPU asynchronous execution** - Kernel launches don't block
2. **CUDA streams** - Multiple streams executing concurrently
3. **Memory transfers** - Data not fully copied before use
4. **Thread timing** - Different CPU speeds change race windows
5. **Uninitialized memory** - GPU memory not zeroed by default
6. **Floating point non-determinism** - GPU operations not bit-exact
7. **Tensor operations** - cuDNN/cuBLAS have internal parallelism
8. **Multi-GPU sync** - P2P transfers have timing issues

### Consequences
- **Non-deterministic results** - Same code gives different outputs
- **Intermittent failures** - Works locally, fails on GPU
- **Difficult to debug** - Cannot reproduce on development machine
- **Random crashes** - Occasionally segfaults or hangs
- **Silent corruption** - Wrong results without errors
- **Testing unreliable** - Tests pass/fail randomly
- **User frustration** - "Works on my machine"

### Potential Fixes

**GPU Synchronization:**
```python
# In grade_code.py, ensure synchronization
import torch

# Add synchronization points
torch.cuda.synchronize()  # Wait for all kernels to finish

# Use deterministic algorithms
torch.use_deterministic_algorithms(True)

# Set random seeds for reproducibility
torch.manual_seed(42)
torch.cuda.manual_seed(42)
torch.backends.cudnn.deterministic = True
torch.backends.cudnn.benchmark = False
```

**Environment Consistency:**
```python
# Set environment variables for reproducibility
import os

os.environ['CUBLAS_WORKSPACE_CONFIG'] = ':4096:8'
os.environ['PYTHONHASHSEED'] = '0'
os.environ['CUDA_LAUNCH_BLOCKING'] = '1'  # Serialize kernel launches

# Disable JIT optimizations that may introduce non-determinism
os.environ['TF_CUDNN_DETERMINISTIC'] = '1'  # TensorFlow
```

**Detection:**
```python
def test_determinism(code: str, num_runs: int = 5) -> bool:
    """Test if code produces deterministic results"""
    results = []
    
    for i in range(num_runs):
        # Run code multiple times
        result = execute_code(code)
        results.append(result)
    
    # Check if all results are identical
    first_result = results[0]
    for result in results[1:]:
        if result != first_result:
            logging.warning(f"Non-deterministic behavior detected")
            return False
    
    return True
```

**Documentation:**
```python
# In API_DOCUMENTATION.md, add note
"""
## GPU Code Best Practices

To ensure reproducible results on GPU hardware:

1. **Synchronize GPU operations:**
   ```python
   import torch
   torch.cuda.synchronize()
   ```

2. **Use deterministic algorithms:**
   ```python
   torch.use_deterministic_algorithms(True)
   torch.backends.cudnn.deterministic = True
   ```

3. **Set all random seeds:**
   ```python
   import random, numpy as np
   random.seed(42)
   np.random.seed(42)
   torch.manual_seed(42)
   ```

4. **Avoid race conditions:**
   - Don't rely on undefined operation order
   - Use proper synchronization primitives
   - Test with CUDA_LAUNCH_BLOCKING=1
"""
```

---

## Issue 12: Solution Works Locally But Fails on GPU

### Potential Reasons/Sources
1. **Different Python version** - 3.8 vs 3.9 syntax/behavior
2. **Missing dependencies** - Package not installed on GPU node
3. **Different package versions** - API changes between versions
4. **Path issues** - Relative imports don't work
5. **Environment differences** - ENV vars, working directory
6. **Hardware differences** - GPU vs CPU, memory limits
7. **File system differences** - Case sensitivity, permissions
8. **Network access** - User's code requires internet
9. **System libraries** - CUDA, cuDNN version mismatch

### Consequences
- **High failure rate** - Most submissions fail
- **User frustration** - "But it works locally!"
- **Support burden** - Many tickets/questions
- **Wasted GPU time** - Jobs fail immediately
- **Debugging difficulty** - Users can't reproduce remotely
- **Poor user experience** - System seems broken

### Potential Fixes

**Environment Documentation:**
```markdown
# ENVIRONMENT.md

## GPU Node Environment

### Python
- Version: 3.9.7
- Location: `/home/gpuuser/miniforge3/envs/aira-dojo/bin/python`

### Installed Packages
```bash
pip list
# numpy==1.24.0
# torch==2.0.1+cu118
# pandas==2.0.0
# ...
```

### CUDA
- Version: 11.8
- cuDNN: 8.7.0

### System
- OS: Ubuntu 22.04
- Kernel: 5.15.0
- GPU: NVIDIA A100 (40GB)

### Environment Variables
```bash
CUDA_HOME=/usr/local/cuda-11.8
LD_LIBRARY_PATH=/usr/local/cuda-11.8/lib64
```

### Working Directory
- Jobs execute in: `/home/gpuuser/work/`
- Temp space: `/tmp/` (10GB limit)
- No network access
- No sudo access
```

**Pre-flight Validation:**
```python
def validate_environment(code: str) -> list:
    """Check if code will work in GPU environment"""
    issues = []
    tree = ast.parse(code)
    
    # Check for disallowed imports
    disallowed = ['requests', 'urllib', 'socket']  # No network
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name in disallowed:
                    issues.append(f"Import '{alias.name}' not available (no network access)")
    
    # Check for file operations
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            if isinstance(node.func, ast.Name):
                if node.func.id == 'open':
                    issues.append("File operations may fail - use provided paths only")
    
    return issues
```

**Environment Test Script:**
```python
# test_environment.py - Users can submit this to check environment
import sys
import os
import platform

print("=== Environment Info ===")
print(f"Python: {sys.version}")
print(f"Platform: {platform.platform()}")
print(f"Working Dir: {os.getcwd()}")
print(f"PATH: {os.environ.get('PATH', '')}")

print("\n=== Installed Packages ===")
import pkg_resources
for pkg in pkg_resources.working_set:
    print(f"{pkg.key}=={pkg.version}")

print("\n=== GPU Info ===")
try:
    import torch
    print(f"PyTorch: {torch.__version__}")
    print(f"CUDA Available: {torch.cuda.is_available()}")
    if torch.cuda.is_available():
        print(f"CUDA Version: {torch.version.cuda}")
        print(f"GPU Count: {torch.cuda.device_count()}")
        print(f"GPU Name: {torch.cuda.get_device_name(0)}")
except ImportError:
    print("PyTorch not installed")

print("\n=== Network Access ===")
try:
    import urllib.request
    urllib.request.urlopen('http://google.com', timeout=1)
    print("Network: AVAILABLE")
except:
    print("Network: BLOCKED")
```

**Requirements Validation:**
```python
# In api.py, accept optional requirements.txt
@app.post("/api/validate")
async def validate_submission(
    code: UploadFile = File(...),
    requirements: UploadFile = File(None)
):
    """Validate code before submission"""
    issues = []
    
    if requirements:
        req_text = (await requirements.read()).decode()
        for line in req_text.split('\n'):
            line = line.strip()
            if line and not line.startswith('#'):
                pkg = line.split('==')[0]
                version = line.split('==')[1] if '==' in line else None
                
                # Check if package is available
                if not check_package_available(pkg, version):
                    issues.append(f"Package {pkg} not available in GPU environment")
    
    return {
        'valid': len(issues) == 0,
        'issues': issues
    }
```

---

## Summary & Priority Matrix

| Issue | Severity | Likelihood | Priority | Effort |
|-------|----------|------------|----------|--------|
| Infinite loop | High | High | 🔴 P0 | Low |
| Interpreter crash | High | Medium | 🔴 P0 | Medium |
| Environment corruption | Medium | High | 🟡 P1 | Medium |
| Zombie processes | Low | Medium | 🟢 P2 | Low |
| Malicious packages | High | Low | 🟡 P1 | High |
| Disk space exhaustion | Medium | High | 🟡 P1 | Low |
| Too many FDs | Low | Low | 🟢 P3 | Low |
| Too many processes | Medium | Medium | 🟡 P1 | Low |
| OOM | High | High | 🔴 P0 | Low |
| Unkillable process | High | Low | 🟡 P1 | High |
| GPU race conditions | Medium | Medium | 🟢 P2 | Medium |
| Environment mismatch | Medium | High | 🟡 P1 | Medium |

## Recommended Implementation Order

### Phase 1: Critical Protections (Immediate)
1. Hard timeout enforcement (Issue 1)
2. Memory limits (Issue 9)
3. Basic resource cleanup (Issues 4, 6)

### Phase 2: Resource Isolation (Short-term)
1. Container-based isolation (Issues 3, 5)
2. Process/thread limits (Issue 8)
3. Disk quotas (Issue 6)

### Phase 3: Monitoring & Detection (Medium-term)
1. Resource monitoring (Issues 7, 8, 9)
2. Anomaly detection (Issue 10)
3. Environment validation (Issue 12)

### Phase 4: Advanced Features (Long-term)
1. GPU synchronization (Issue 11)
2. Automated recovery (Issue 10)
3. Predictive failure analysis

## Quick Win Implementations

These can be added immediately with minimal changes:

```python
# In ssh_executor.py start_job():
command = (
    # Add resource limits
    f"ulimit -v 2097152; "     # 2GB memory
    f"ulimit -u 128; "          # 128 processes max
    f"ulimit -n 1024; "         # 1024 file descriptors
    f"ulimit -t {expected_time + 60}; "  # CPU time limit
    
    # Add hard timeout
    f"timeout --signal=KILL {expected_time + 60}s "
    
    # Run with monitoring
    f"nohup bash -c '{grading_command}' > {remote_stdout} 2> {remote_stderr} & "
    f"echo $!"
)
```

This single change addresses issues 1, 6, 7, 8, and partially 9.

