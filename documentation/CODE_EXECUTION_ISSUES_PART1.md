# Code Execution Issues - Deep Analysis

## Overview
This document analyzes potential code execution issues that can occur when running untrusted user code on GPU nodes, including root causes, consequences, and mitigation strategies.

---

## Issue 1: Infinite Loop - Job Hangs Forever Despite Timeout

### Potential Reasons/Sources
1. **CPU-bound infinite loop** - Code like `while True: pass` that never yields control
2. **Blocking I/O operations** - Waiting for network/file operations that never complete
3. **Deadlock conditions** - Multiple threads waiting on each other
4. **Signal blocking** - User code blocks SIGTERM/SIGKILL signals
5. **Process spawning in loop** - Creates new processes faster than they can be killed
6. **GPU kernel hang** - CUDA/PyTorch operation stuck waiting for GPU
7. **Timeout not enforced** - `expected_time` is advisory, not a hard limit

### Consequences
- **GPU node permanently occupied** - Other jobs cannot use the node
- **Resource waste** - CPU/GPU cycles used for nothing
- **System instability** - Eventually fills process table
- **Manual intervention required** - Admin must SSH and kill process
- **Queue backup** - Other jobs stuck waiting
- **Cost accumulation** - Cloud GPU time wasted

### Potential Fixes

**Short-term (Implemented):**
- ✅ Store remote PID for manual killing
- ✅ Cancel endpoint to mark job as cancelled
- ✅ Worker checks job status and kills process

**Medium-term (Recommended):**
```python
# Add hard timeout to job execution
import signal

class TimeoutError(Exception):
    pass

def timeout_handler(signum, frame):
    raise TimeoutError("Job exceeded timeout")

# In ssh_executor.py start_job():
command = (
    f"timeout --signal=KILL {expected_time + 60}s "  # Hard kill after timeout
    f"nohup bash -c '{grading_command}' > {remote_stdout} 2> {remote_stderr} & "
    f"echo $!"
)
```

**Long-term (Production):**
1. **Containerization with resource limits:**
   ```bash
   docker run --rm \
     --cpus=1.0 \
     --memory=2g \
     --pids-limit=100 \
     --timeout=${expected_time}s \
     --user=nobody \
     user_code.py
   ```

2. **cgroups enforcement:**
   ```bash
   cgcreate -g cpu,memory:userjob
   cgset -r cpu.cfs_quota_us=100000 userjob
   cgset -r memory.limit_in_bytes=2G userjob
   cgexec -g cpu,memory:userjob python3 solution.py
   ```

3. **Separate job timeout monitor:**
   ```python
   # In worker.py
   def monitor_job_timeout(job_id, expected_time):
       time.sleep(expected_time + grace_period)
       job = db.query(Job).filter(Job.job_id == job_id).first()
       if job.status == 'running':
           # Force kill
           executor.kill_process(job.remote_pid)
           job.status = 'timeout'
   ```

---

## Issue 2: Code Crashes Python Interpreter on GPU Node

### Potential Reasons/Sources
1. **Segmentation fault** - Accessing invalid memory (ctypes, C extensions)
2. **C extension bugs** - NumPy, PyTorch, CUDA libraries with native code
3. **Stack overflow** - Deep recursion exceeding stack limit
4. **Memory corruption** - Writing beyond array bounds
5. **GPU driver crash** - Invalid CUDA operations
6. **Signal handling issues** - User catches and mishandles signals
7. **Incompatible binary extensions** - Wrong Python/library version

### Consequences
- **Job fails silently** - No meaningful error message
- **Worker loses connection** - Cannot retrieve output
- **GPU node may need reboot** - If driver crashes
- **Subsequent jobs fail** - Environment is corrupted
- **Data loss** - Partial results not saved
- **Difficult to debug** - Core dumps on remote server

### Potential Fixes

**Detection:**
```python
# In ssh_executor.py get_job_output():
exit_code = self.get_exit_code(remote_pid)

if exit_code == -11:  # SIGSEGV
    stderr += "\n[SYSTEM ERROR] Process crashed with segmentation fault"
elif exit_code == -6:  # SIGABRT
    stderr += "\n[SYSTEM ERROR] Process aborted (assertion failed)"
elif exit_code == -9:  # SIGKILL
    stderr += "\n[SYSTEM ERROR] Process killed (likely OOM or timeout)"
elif exit_code < 0:
    stderr += f"\n[SYSTEM ERROR] Process terminated by signal {-exit_code}"
```

**Prevention:**
1. **Run in separate container per job:**
   - Isolates crashes from other jobs
   - Easy to restart clean environment

2. **Validate code before execution:**
   ```python
   # Basic syntax check
   try:
       ast.parse(user_code)
   except SyntaxError as e:
       return {'error': f'Syntax error: {e}'}
   
   # Check for dangerous imports
   dangerous = ['ctypes', 'subprocess', 'os.system']
   tree = ast.parse(user_code)
   for node in ast.walk(tree):
       if isinstance(node, ast.Import):
           for alias in node.names:
               if alias.name in dangerous:
                   return {'error': f'Import {alias.name} not allowed'}
   ```

3. **Core dump collection:**
   ```bash
   # On GPU node
   ulimit -c unlimited
   echo "/var/coredumps/core.%e.%p" > /proc/sys/kernel/core_pattern
   ```

4. **Automatic restart on crash:**
   ```python
   # In worker.py
   try:
       result = executor.get_job_output(job_id)
   except SSHException:
       # Reconnect and retry
       executor.disconnect()
       executor.connect()
       result = executor.get_job_output(job_id)
   ```

---

## Issue 3: Code Corrupts Apptainer/Container Environment

### Potential Reasons/Sources
1. **Writing to mounted volumes** - Modifying shared filesystems
2. **Environment variable pollution** - Setting permanent env vars
3. **Installing packages globally** - `pip install --user` persists
4. **Modifying system files** - If running with elevated privileges
5. **Creating files in shared locations** - `/tmp`, `/home/gpuuser`
6. **Database corruption** - SQLite files left locked
7. **Cache pollution** - Filling `.cache` directories

### Consequences
- **Environment drift** - Subsequent jobs behave differently
- **Dependency conflicts** - Incompatible package versions
- **Disk space exhaustion** - Accumulated garbage
- **Permission errors** - Files owned by wrong user
- **Non-deterministic results** - Same code produces different outputs
- **Manual cleanup required** - Admin must restore environment

### Potential Fixes

**Container Isolation:**
```bash
# Use read-only root filesystem
apptainer run --contain --no-home --scratch /tmp user_code.sif

# Or with Docker
docker run --read-only --tmpfs /tmp:rw,noexec,nosuid image
```

**Cleanup After Each Job:**
```python
# In ssh_executor.py cleanup_job_files():
def cleanup_job_files(self, job_id: str) -> bool:
    """Clean up all job-related files and temporary data"""
    cleanup_commands = [
        # Remove job files
        f"rm -f /home/gpuuser/work/solution.py",
        f"rm -f /home/gpuuser/work/results.jsonl",
        f"rm -f /home/gpuuser/work/job_{job_id}.*",
        
        # Clean temp files
        f"find /tmp -user gpuuser -name '*{job_id}*' -delete",
        
        # Clear Python cache
        f"rm -rf /home/gpuuser/.cache/pip/*",
        f"rm -rf /home/gpuuser/__pycache__",
        
        # Reset permissions
        f"chmod -R u+w /home/gpuuser/work || true"
    ]
    
    for cmd in cleanup_commands:
        self.exec_command(cmd)
```

**Workspace Isolation:**
```python
# Create unique workspace per job
job_workspace = f"/scratch/job_{job_id}"
command = (
    f"mkdir -p {job_workspace} && "
    f"cd {job_workspace} && "
    f"cp /home/gpuuser/work/solution.py . && "
    f"python3 solution.py && "
    f"rm -rf {job_workspace}"
)
```

**Monitoring:**
```python
# Check environment health before job
def check_environment_health(self) -> dict:
    """Verify environment is clean and ready"""
    checks = {
        'disk_space': "df -h /home/gpuuser | tail -1",
        'temp_files': "find /tmp -user gpuuser | wc -l",
        'processes': "ps aux | grep gpuuser | wc -l",
        'open_files': "lsof -u gpuuser | wc -l"
    }
    
    results = {}
    for name, cmd in checks.items():
        output = self.exec_command(cmd)
        results[name] = output.strip()
    
    return results
```

---

## Issue 4: Code Leaves Zombie Processes

### Potential Reasons/Sources
1. **Subprocess not waited on** - `subprocess.Popen()` without `.wait()`
2. **Parent dies before child** - Child becomes orphan/zombie
3. **Signal handling issues** - SIGCHLD not handled properly
4. **Multiprocessing bugs** - Pool workers not cleaned up
5. **Shell script spawning** - `bash -c` creates child processes
6. **Background processes** - Using `&` in subprocess calls
7. **Exception during cleanup** - `.wait()` never called

### Consequences
- **Process table full** - Cannot spawn new processes (EAGAIN error)
- **System instability** - Node becomes unusable
- **Resource leaks** - Memory not freed (minimal but adds up)
- **Monitoring confusion** - `ps` shows many defunct processes
- **Manual cleanup required** - Reboot may be needed

### Potential Fixes

**Detection:**
```python
# In worker.py monitor zombie processes
def count_zombie_processes(self) -> int:
    """Count zombie processes on GPU node"""
    output = self.executor.exec_command("ps aux | grep '<defunct>' | wc -l")
    return int(output.strip())

# Alert if too many
if count_zombie_processes() > 100:
    logging.error(f"Node {node_id} has excessive zombie processes")
```

**Prevention in User Code Execution:**
```python
# In ssh_executor.py - ensure proper process cleanup
command = (
    f"nohup bash -c '"
    f"trap \"kill 0\" EXIT; "  # Kill all child processes on exit
    f"{grading_command}"
    f"' > {remote_stdout} 2> {remote_stderr} & "
    f"echo $!"
)
```

**Force Reap Zombies:**
```python
# In ssh_executor.py cleanup
def cleanup_zombies(self):
    """Reap zombie processes"""
    commands = [
        # Find and kill parent processes with zombie children
        "ps -A -ostat,ppid | grep -e '[zZ]' | awk '{print $2}' | xargs kill -9 2>/dev/null",
        
        # Wait for init to reap orphans
        "sleep 1"
    ]
    
    for cmd in commands:
        self.exec_command(cmd)
```

**Proper Subprocess Handling:**
```python
# Ensure grade_code.py handles subprocesses correctly
import subprocess
import signal
import sys

def cleanup_handler(signum, frame):
    """Clean up all child processes on exit"""
    # Kill process group
    os.killpg(0, signal.SIGTERM)
    sys.exit(1)

signal.signal(signal.SIGTERM, cleanup_handler)
signal.signal(signal.SIGINT, cleanup_handler)

# Use context manager for subprocesses
with subprocess.Popen(cmd, ...) as proc:
    proc.wait(timeout=timeout)
```

---

## Issue 5: Malicious Packages Persist After Job

### Potential Reasons/Sources
1. **`pip install` in user code** - Packages installed to user site-packages
2. **Shared Python environment** - All jobs use same Python installation
3. **`--user` flag** - Installs to `~/.local/lib/python3.x/site-packages`
4. **No isolation** - Jobs run in same environment
5. **Cached wheels** - Malicious packages cached for reuse
6. **Site-packages writable** - User can modify system packages
7. **PYTHONPATH manipulation** - User adds malicious directories

### Consequences
- **Code injection** - Malicious code runs in subsequent jobs
- **Data exfiltration** - Steal other users' code/data
- **Privilege escalation** - Exploit vulnerabilities
- **Cryptocurrency mining** - Use GPU for mining
- **Supply chain attack** - Compromise other users' results
- **Difficult to detect** - Malicious code hides in dependencies

### Potential Fixes

**Prevent Installation:**
```python
# Restrict pip in user code
# Add to container/environment
export PIP_USER=false
export PIP_ROOT_USER_ACTION=ignore
unset PYTHONUSERBASE

# Or create read-only environment
chmod -R a-w /usr/local/lib/python3.9/site-packages
```

**Code Analysis:**
```python
# In api.py before accepting job
import ast

def check_dangerous_operations(code: str) -> list:
    """Detect potentially dangerous operations"""
    dangerous = []
    tree = ast.parse(code)
    
    for node in ast.walk(tree):
        # Check for subprocess/os calls
        if isinstance(node, ast.Call):
            if isinstance(node.func, ast.Attribute):
                if node.func.attr in ['system', 'popen', 'spawn']:
                    dangerous.append(f"Dangerous call: {node.func.attr}")
        
        # Check for pip install
        if isinstance(node, ast.Expr):
            if isinstance(node.value, ast.Str):
                if 'pip install' in node.value.s:
                    dangerous.append("pip install detected")
    
    return dangerous
```

**Container Isolation (Best Solution):**
```python
# Each job gets fresh container
def start_job(self, job_id, script_path, competition_id):
    """Start job in isolated container"""
    container_name = f"job_{job_id}"
    
    command = (
        f"docker run --rm --name {container_name} "
        f"--network none "  # No network access
        f"--read-only "  # Read-only filesystem
        f"--tmpfs /tmp:rw,noexec "  # Temp space, no exec
        f"--user nobody "  # Non-privileged user
        f"--cpus=1 --memory=2g "  # Resource limits
        f"-v /home/gpuuser/work/solution.py:/solution.py:ro "
        f"python:3.9-slim "
        f"python /solution.py"
    )
    
    return self.exec_command(command)
```

**Virtual Environment Per Job:**
```bash
# Create and destroy venv per job
python3 -m venv /tmp/job_${JOB_ID}_venv
source /tmp/job_${JOB_ID}_venv/bin/activate
pip install -r requirements.txt
python3 solution.py
deactivate
rm -rf /tmp/job_${JOB_ID}_venv
```

---

## Issue 6: Code Fills /tmp with Large Files

### Potential Reasons/Sources
1. **Creating large datasets** - User generates GB of test data
2. **Model checkpoints** - Saving model weights to temp
3. **Logging verbosity** - Writing massive log files
4. **Memory dumps** - Core dumps or debug files
5. **Cache accumulation** - ML frameworks caching data
6. **No cleanup** - User doesn't delete temporary files
7. **Compression/decompression** - Extracting large archives

### Consequences
- **Disk full** - Node cannot write any files
- **Jobs fail** - "No space left on device" errors
- **System instability** - Services crash (can't write logs)
- **Other users affected** - Shared /tmp space
- **Manual cleanup required** - Admin must clear /tmp
- **Delayed failure** - Issue appears later, not during culprit job

### Potential Fixes

**Quota Enforcement:**
```python
# Set disk quota before job
def set_disk_quota(self, job_id: str, limit_mb: int = 1024):
    """Set disk quota for job workspace"""
    workspace = f"/scratch/job_{job_id}"
    
    commands = [
        f"mkdir -p {workspace}",
        f"mount -t tmpfs -o size={limit_mb}M tmpfs {workspace}",
        f"chmod 777 {workspace}"
    ]
    
    for cmd in commands:
        self.exec_command(cmd)
    
    return workspace
```

**Monitor Disk Usage:**
```python
# In worker.py monitor during execution
def monitor_disk_usage(self, job_id: str):
    """Monitor and enforce disk limits"""
    while job.status == 'running':
        usage = self.executor.exec_command(
            f"du -sm /scratch/job_{job_id} | cut -f1"
        )
        
        if int(usage) > 1000:  # 1GB limit
            self.executor.kill_process(job.remote_pid)
            job.status = 'failed'
            job.stderr = "Job exceeded disk usage limit (1GB)"
            break
        
        time.sleep(10)
```

**Cleanup Temp Files:**
```python
# In ssh_executor.py
def cleanup_temp_files(self, job_id: str):
    """Aggressively clean temporary files"""
    cleanup_commands = [
        # Remove job-specific temp files
        f"find /tmp -name '*{job_id}*' -delete",
        
        # Clean old temp files (>1 hour)
        "find /tmp -type f -mmin +60 -user gpuuser -delete",
        
        # Clear Python cache
        "rm -rf /tmp/__pycache__",
        "rm -rf /tmp/pip-*",
        
        # Unmount temp workspace
        f"umount /scratch/job_{job_id} 2>/dev/null || true",
        f"rm -rf /scratch/job_{job_id}"
    ]
    
    for cmd in cleanup_commands:
        try:
            self.exec_command(cmd)
        except:
            logging.warning(f"Cleanup command failed: {cmd}")
```

**Warn Users:**
```python
# Check output size before returning
def get_job_output(self, job_id: str):
    # ... existing code ...
    
    # Check if results are too large
    size_mb = len(results_jsonl.encode()) / (1024 * 1024)
    if size_mb > 10:
        results_jsonl = (
            f"[WARNING] Results truncated (original size: {size_mb:.1f}MB)\n"
            + results_jsonl[:1024*1024]  # Only keep first 1MB
        )
    
    return results_jsonl, stdout, stderr
```

---

## Issue 7: Code Opens Too Many File Descriptors

### Potential Reasons/Sources
1. **File leak in loop** - Opening files without closing
2. **Network connections** - Opening sockets without cleanup
3. **Subprocess pipes** - Creating processes without cleanup
4. **Database connections** - Connection pool exhaustion
5. **Memory-mapped files** - Creating many mmaps
6. **Inotify watches** - File system monitoring
7. **Unix sockets** - IPC mechanisms

### Consequences
- **"Too many open files" error** - Cannot open new files
- **Job crashes** - FileNotFoundError or OSError
- **Resource exhaustion** - System-wide file descriptor limit
- **Cascading failures** - Other jobs affected
- **Node requires restart** - Only way to clear
- **Hidden bug** - Only appears after many iterations

### Potential Fixes

**Set Limits:**
```python
# In ssh_executor.py before running job
command = (
    f"ulimit -n 1024; "  # Limit to 1024 file descriptors
    f"ulimit -u 512; "   # Limit to 512 processes
    f"nohup bash -c '{grading_command}' & "
    f"echo $!"
)
```

**Monitor FD Usage:**
```python
def check_file_descriptors(self, pid: int) -> int:
    """Count open file descriptors for process"""
    output = self.exec_command(f"ls /proc/{pid}/fd 2>/dev/null | wc -l")
    return int(output.strip()) if output else 0

# In worker.py
while job.status == 'running':
    fd_count = executor.check_file_descriptors(job.remote_pid)
    if fd_count > 900:  # Approaching limit
        logging.warning(f"Job {job_id} has {fd_count} open FDs")
        # Could kill job or just log
    time.sleep(30)
```

**Code Validation:**
```python
def check_resource_leaks(code: str) -> list:
    """Detect potential resource leaks"""
    issues = []
    tree = ast.parse(code)
    
    # Check for open() without 'with' statement
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            if isinstance(node.func, ast.Name):
                if node.func.id == 'open':
                    # Check if it's in a 'with' statement
                    # (simplified check)
                    issues.append("open() call without 'with' statement")
    
    return issues
```

**Cleanup Script:**
```python
# Run after each job
def cleanup_orphan_fds(self):
    """Close orphaned file descriptors"""
    commands = [
        # List processes with many FDs
        "lsof -u gpuuser | awk '{print $2}' | sort | uniq -c | sort -rn | head -5",
        
        # Kill processes with excessive FDs
        "for pid in $(lsof -u gpuuser | awk '{print $2}' | sort | uniq -c | awk '$1>500{print $2}'); do kill -9 $pid; done"
    ]
    
    for cmd in commands:
        self.exec_command(cmd)
```

---

*[Continuing in next file due to length...]

Would you like me to continue with the remaining issues (8-12)?*

