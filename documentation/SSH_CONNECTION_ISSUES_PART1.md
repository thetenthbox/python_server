# SSH Connection Issues - Deep Analysis

## Overview
Analysis of SSH connection problems that can occur when managing remote GPU nodes through a jump host, including root causes, consequences, and mitigation strategies.

---

## Issue 1: SSH Connection Drops Mid-Job - Job Orphaned

### Potential Reasons/Sources
1. **Network instability** - Packet loss, intermittent connectivity
2. **TCP timeout** - Idle connection timeout on firewall/router
3. **SSH daemon restart** - System updates or crashes
4. **Resource exhaustion** - Out of file descriptors or memory
5. **Keep-alive not configured** - No traffic, connection dropped
6. **Network path change** - Routing update breaks connection
7. **Jump host overload** - Too many connections, drops some
8. **Client-side issues** - Server machine network problems
9. **NAT timeout** - NAT gateway drops idle connections
10. **SSH process killed** - OOM killer or admin intervention

### Consequences
- **Job continues running** - But server can't monitor it
- **Cannot retrieve results** - SSH connection gone
- **Job marked as failed** - Even though it completed
- **Resource leak** - Process keeps running, using GPU
- **Worker thread hangs** - Waiting for SSH that never returns
- **Manual cleanup required** - SSH back in to kill process
- **Lost results** - Results.jsonl generated but not retrieved
- **Database inconsistency** - Job status doesn't match reality

### Potential Fixes

**1. SSH Keep-Alive Configuration**
```python
# In ssh_executor.py
def connect(self) -> bool:
    """Establish SSH connection with keep-alive"""
    try:
        self.client = paramiko.SSHClient()
        self.client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        
        # Keep-alive configuration
        self.client.connect(
            hostname=self.jump_host,
            username=self.jump_user,
            timeout=30,
            banner_timeout=30,
            auth_timeout=30
        )
        
        # Enable keep-alive (send packet every 60s, 3 attempts)
        transport = self.client.get_transport()
        transport.set_keepalive(60)
        
        # TCP keep-alive at OS level
        sock = transport.sock
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_KEEPALIVE, 1)
        sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_KEEPIDLE, 60)
        sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_KEEPINTVL, 10)
        sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_KEEPCNT, 3)
        
        return True
    except Exception as e:
        logging.error(f"Connection failed: {e}")
        return False
```

**2. Connection Health Check**
```python
def check_connection_alive(self) -> bool:
    """Check if SSH connection is still alive"""
    if not self.client:
        return False
    
    try:
        # Send lightweight command
        transport = self.client.get_transport()
        if not transport or not transport.is_active():
            return False
        
        # Try simple command
        stdin, stdout, stderr = self.client.exec_command('echo alive', timeout=5)
        result = stdout.read().decode().strip()
        return result == 'alive'
    except:
        return False

def ensure_connected(self):
    """Ensure connection is alive, reconnect if needed"""
    if not self.check_connection_alive():
        logging.warning(f"Connection lost to node {self.node_id}, reconnecting...")
        self.disconnect()
        return self.connect()
    return True
```

**3. Job Process Monitoring**
```python
# In worker.py - monitor job even if SSH drops
def monitor_job_via_database(self, job_id: str):
    """Monitor job status when SSH is unreliable"""
    job = db.query(Job).filter(Job.job_id == job_id).first()
    
    # Try to reconnect periodically
    reconnect_attempts = 0
    max_attempts = 5
    
    while job.status == 'running':
        try:
            # Check if process still exists
            if executor.ensure_connected():
                pid_check = executor.exec_command(f"ps -p {job.remote_pid}")
                if not pid_check:
                    # Process finished
                    break
            else:
                reconnect_attempts += 1
                if reconnect_attempts >= max_attempts:
                    # Mark as unknown, manual intervention needed
                    job.status = 'connection_lost'
                    db.commit()
                    break
        except:
            pass
        
        time.sleep(30)
```

**4. Result Retrieval Retry**
```python
def get_job_output_with_retry(self, job_id: str, max_retries=5) -> tuple:
    """Try multiple times to retrieve job output"""
    for attempt in range(max_retries):
        try:
            # Ensure connected
            if not self.ensure_connected():
                logging.warning(f"Attempt {attempt+1}/{max_retries}: Reconnecting...")
                time.sleep(5 * (attempt + 1))  # Exponential backoff
                continue
            
            # Try to get output
            results, stdout, stderr = self.get_job_output(job_id)
            return results, stdout, stderr
            
        except Exception as e:
            logging.error(f"Attempt {attempt+1}/{max_retries} failed: {e}")
            if attempt < max_retries - 1:
                time.sleep(5 * (attempt + 1))
            else:
                raise
```

**5. Persistent Job Tracking**
```python
# Store job PIDs in database for recovery
# Even if SSH drops, we can reconnect and find the process

def recover_orphaned_jobs(self):
    """Find and recover jobs that lost SSH connection"""
    orphaned = db.query(Job).filter(
        Job.status == 'running',
        Job.remote_pid != None
    ).all()
    
    for job in orphaned:
        try:
            executor = SSHExecutor(job.node_id)
            if executor.connect():
                # Check if process still exists
                check = executor.exec_command(f"ps -p {job.remote_pid}")
                if check:
                    # Process still running, try to get results
                    try:
                        results, stdout, stderr = executor.get_job_output(job.job_id)
                        # Update job with results
                        job.stdout = results
                        job.stderr = stderr
                        job.status = 'completed'
                        job.completed_at = datetime.utcnow()
                        db.commit()
                    except:
                        pass
                else:
                    # Process finished but we lost connection
                    # Try to retrieve results anyway
                    pass
        except:
            continue
```

---

## Issue 2: Jump Host Goes Down - Can't Reach Any GPU Nodes

### Potential Reasons/Sources
1. **Hardware failure** - Server crash, power loss
2. **Network outage** - Internet connection lost
3. **Scheduled maintenance** - Planned downtime
4. **OS crash/kernel panic** - System-level failure
5. **Resource exhaustion** - CPU/memory/disk full
6. **Security incident** - DDoS attack, breach response
7. **Configuration error** - Bad update, firewall misconfiguration
8. **Cloud provider issue** - AWS/GCP outage
9. **SSH daemon crash** - Service stopped
10. **IP address change** - DHCP lease expired

### Consequences
- **Complete system outage** - No GPU nodes accessible
- **All jobs stuck** - Cannot start new jobs
- **Running jobs orphaned** - Cannot monitor or retrieve results
- **Queue backs up** - Jobs accumulate in database
- **Manual intervention required** - Cannot auto-recover
- **Data loss risk** - Results generated but unretrievable
- **Service downtime** - System appears completely broken
- **User frustration** - All submissions fail

### Potential Fixes

**1. Multiple Jump Host Configuration**
```python
# In config.py
JUMP_HOSTS = [
    {
        "host": "ce084d48-001.cloud.together.ai",
        "user": "vishal",
        "priority": 1
    },
    {
        "host": "backup-jump-host.example.com",
        "user": "vishal",
        "priority": 2
    }
]

# In ssh_executor.py
def connect_with_failover(self) -> bool:
    """Try multiple jump hosts"""
    for jump_host in sorted(JUMP_HOSTS, key=lambda x: x['priority']):
        try:
            self.client.connect(
                hostname=jump_host['host'],
                username=jump_host['user'],
                timeout=10
            )
            logging.info(f"Connected via {jump_host['host']}")
            return True
        except Exception as e:
            logging.warning(f"Jump host {jump_host['host']} failed: {e}")
            continue
    
    return False
```

**2. Direct Connection Fallback**
```python
# If jump host fails, try direct connection to GPU nodes
def connect_direct(self, node_ip: str) -> bool:
    """Try direct connection to GPU node (if firewall allows)"""
    try:
        self.client.connect(
            hostname=node_ip,
            username=SSH_USERNAME,
            password=SSH_PASSWORD,
            timeout=10
        )
        logging.info(f"Direct connection to {node_ip} successful")
        return True
    except:
        return False

def connect(self) -> bool:
    """Try jump host first, then direct"""
    # Try jump host
    if self.connect_via_jump():
        return True
    
    # Fallback to direct
    logging.warning("Jump host unavailable, trying direct connection")
    return self.connect_direct(self.node_ip)
```

**3. Health Monitoring**
```python
def monitor_jump_host_health():
    """Continuously monitor jump host availability"""
    while True:
        try:
            # Try to connect
            client = paramiko.SSHClient()
            client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
            client.connect(JUMP_HOST, username=JUMP_USER, timeout=10)
            client.close()
            
            # Update health status
            jump_host_available = True
            
        except Exception as e:
            logging.error(f"Jump host health check failed: {e}")
            jump_host_available = False
            
            # Send alert
            send_alert("Jump host down!", severity="critical")
        
        time.sleep(60)  # Check every minute
```

**4. Graceful Degradation**
```python
# In api.py
@app.post("/api/submit")
async def submit_job(...):
    # Check if jump host is available
    if not jump_host_available:
        raise HTTPException(
            status_code=503,
            detail="GPU cluster temporarily unavailable. Please try again later."
        )
```

**5. Queue Persistence**
```python
# Jobs stay in database queue even if jump host is down
# When it comes back up, workers automatically resume

def auto_resume_on_recovery():
    """When jump host recovers, resume job processing"""
    global jump_host_available
    
    while True:
        if jump_host_available and not workers_running:
            logging.info("Jump host recovered, resuming workers")
            start_workers()
        
        time.sleep(30)
```

---

## Issue 3: SSH Key Authentication Fails Randomly

### Potential Reasons/Sources
1. **File permissions changed** - ~/.ssh/id_rsa not 600
2. **Key file corrupted** - Disk error, partial write
3. **Multiple keys confusion** - SSH trying wrong key first
4. **Agent forwarding issues** - SSH agent not running
5. **Home directory mounted differently** - NFS timing issues
6. **SELinux/AppArmor** - Security policy blocking key access
7. **Key format incompatibility** - Old vs new OpenSSH format
8. **Clock skew** - Timestamp-based auth failing
9. **Memory/disk full** - Cannot read key file
10. **Race condition** - Multiple processes accessing key

### Consequences
- **Intermittent failures** - Works sometimes, fails others
- **Hard to debug** - Non-deterministic behavior
- **Fallback to password** - May work but insecure
- **Job submission failures** - Random connection errors
- **Worker thread hangs** - Waiting for auth that never comes
- **User confusion** - "It worked yesterday"

### Potential Fixes

**1. Use Password Auth as Fallback**
```python
def connect(self) -> bool:
    """Try key auth first, password as fallback"""
    try:
        # Try key authentication
        self.client.connect(
            hostname=self.jump_host,
            username=self.jump_user,
            key_filename=SSH_KEY_PATH,
            timeout=30,
            look_for_keys=True
        )
        return True
    except paramiko.AuthenticationException:
        logging.warning("Key auth failed, trying password")
        try:
            # Fallback to password
            self.client.connect(
                hostname=self.jump_host,
                username=self.jump_user,
                password=SSH_PASSWORD,
                timeout=30
            )
            return True
        except:
            return False
    except Exception as e:
        logging.error(f"Connection failed: {e}")
        return False
```

**2. Validate Key File on Startup**
```python
def validate_ssh_key():
    """Validate SSH key file on server startup"""
    if not SSH_KEY_PATH:
        logging.warning("No SSH key configured, using password auth")
        return True
    
    # Check file exists
    if not os.path.exists(SSH_KEY_PATH):
        logging.error(f"SSH key not found: {SSH_KEY_PATH}")
        return False
    
    # Check permissions
    stat_info = os.stat(SSH_KEY_PATH)
    mode = stat_info.st_mode & 0o777
    if mode != 0o600:
        logging.error(f"SSH key has wrong permissions: {oct(mode)}, should be 0600")
        try:
            os.chmod(SSH_KEY_PATH, 0o600)
            logging.info("Fixed SSH key permissions")
        except:
            return False
    
    # Try to load key
    try:
        paramiko.RSAKey.from_private_key_file(SSH_KEY_PATH)
        logging.info("SSH key validated successfully")
        return True
    except Exception as e:
        logging.error(f"Invalid SSH key: {e}")
        return False

# In main.py
if not validate_ssh_key():
    sys.exit(1)
```

**3. Connection Retry with Exponential Backoff**
```python
def connect_with_retry(self, max_attempts=3) -> bool:
    """Retry connection with exponential backoff"""
    for attempt in range(max_attempts):
        try:
            self.client.connect(
                hostname=self.jump_host,
                username=self.jump_user,
                key_filename=SSH_KEY_PATH if SSH_KEY_PATH else None,
                password=SSH_PASSWORD,
                timeout=30,
                allow_agent=True,
                look_for_keys=True
            )
            return True
        except Exception as e:
            wait_time = 2 ** attempt  # 1s, 2s, 4s
            logging.warning(f"Connection attempt {attempt+1}/{max_attempts} failed: {e}")
            if attempt < max_attempts - 1:
                time.sleep(wait_time)
    
    return False
```

**4. Multiple Key Support**
```python
# Try multiple keys
SSH_KEYS = [
    "~/.ssh/id_rsa",
    "~/.ssh/id_ed25519",
    "/path/to/specific/key"
]

def connect_with_any_key(self) -> bool:
    """Try all available keys"""
    for key_path in SSH_KEYS:
        if not os.path.exists(os.path.expanduser(key_path)):
            continue
        
        try:
            self.client.connect(
                hostname=self.jump_host,
                username=self.jump_user,
                key_filename=os.path.expanduser(key_path),
                timeout=30
            )
            logging.info(f"Connected with key: {key_path}")
            return True
        except:
            continue
    
    # All keys failed, try password
    try:
        self.client.connect(
            hostname=self.jump_host,
            username=self.jump_user,
            password=SSH_PASSWORD,
            timeout=30
        )
        return True
    except:
        return False
```

---

## Issue 4: SSH Port Forwarding Breaks - Can't Establish Connection

### Potential Reasons/Sources
1. **Port already in use** - Another process bound to port
2. **Firewall blocking** - Port forwarding denied
3. **Jump host config** - AllowTcpForwarding disabled
4. **Resource limits** - Too many forwarded ports
5. **Network topology change** - Routing broken
6. **SSH daemon restart** - Forwarding rules lost
7. **ProxyCommand fails** - Jump host SSH broken
8. **Local port exhaustion** - No available local ports
9. **GatewayPorts mismatch** - Config incompatibility
10. **Tunnel closes unexpectedly** - Network issue

### Consequences
- **Cannot reach GPU nodes** - Direct connection fails
- **All operations blocked** - Submit, status, results
- **Manual SSH required** - Have to debug forwarding
- **Service appears down** - Users see connection errors
- **Worker threads blocked** - Cannot establish tunnel

### Potential Fixes

**1. Dynamic Port Allocation**
```python
import random

def find_available_port(start=10000, end=20000):
    """Find an available local port"""
    for _ in range(100):  # Try 100 times
        port = random.randint(start, end)
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.bind(('localhost', port))
            sock.close()
            return port
        except OSError:
            continue
    
    raise Exception("No available ports found")

def setup_port_forward(self, remote_host, remote_port):
    """Setup SSH port forwarding with dynamic local port"""
    local_port = find_available_port()
    
    try:
        transport = self.client.get_transport()
        transport.request_port_forward('', local_port, remote_host, remote_port)
        return local_port
    except Exception as e:
        logging.error(f"Port forwarding failed: {e}")
        return None
```

**2. Connection Without Port Forwarding**
```python
# Use ProxyJump instead of port forwarding
def connect_via_proxy_jump(self, node_ip: str) -> bool:
    """Connect using ProxyJump (simpler than port forwarding)"""
    try:
        # Close existing connection
        if self.client:
            self.client.close()
        
        self.client = paramiko.SSHClient()
        self.client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        
        # Create jump host client
        jump_client = paramiko.SSHClient()
        jump_client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        jump_client.connect(
            hostname=self.jump_host,
            username=self.jump_user,
            timeout=30
        )
        
        # Get transport and create channel to target
        jump_transport = jump_client.get_transport()
        dest_addr = (node_ip, SSH_PORT)
        local_addr = ('127.0.0.1', 0)
        channel = jump_transport.open_channel("direct-tcpip", dest_addr, local_addr)
        
        # Connect to target through channel
        self.client.connect(
            hostname=node_ip,
            username=SSH_USERNAME,
            password=SSH_PASSWORD,
            sock=channel,
            timeout=30
        )
        
        self.jump_client = jump_client  # Keep reference
        return True
        
    except Exception as e:
        logging.error(f"ProxyJump connection failed: {e}")
        return False
```

**3. Check Port Forwarding Support**
```python
def check_port_forwarding_support(self) -> bool:
    """Check if jump host allows port forwarding"""
    try:
        stdin, stdout, stderr = self.client.exec_command(
            'grep AllowTcpForwarding /etc/ssh/sshd_config'
        )
        config = stdout.read().decode()
        
        if 'AllowTcpForwarding no' in config:
            logging.error("Jump host does not allow TCP forwarding")
            return False
        
        return True
    except:
        # Assume it's allowed if can't check
        return True
```

---

*[Continued in SSH_CONNECTION_ISSUES_PART2.md...]*

