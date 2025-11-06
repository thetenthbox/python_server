# SSH Connection Issues - Deep Analysis (Part 2)

*Continued from SSH_CONNECTION_ISSUES_PART1.md*

---

## Issue 5: SSH Timeout Too Short for Slow Network

### Potential Reasons/Sources
1. **High latency network** - Satellite, international connections
2. **Congested network** - Peak usage times
3. **Slow DNS resolution** - DNS servers responding slowly
4. **Packet loss** - Requires retransmission
5. **Bandwidth limiting** - QoS policies throttling SSH
6. **VPN overhead** - Additional encryption/routing delay
7. **Geo-distributed** - Long physical distance
8. **Network equipment** - Slow routers/switches
9. **Mobile networks** - Variable latency (4G/5G)
10. **Default timeout too aggressive** - 30s not enough

### Consequences
- **Connection fails prematurely** - Before handshake completes
- **Intermittent failures** - Works on fast network, fails on slow
- **User frustration** - "Connection timeout" errors
- **Job submission blocked** - Cannot establish SSH
- **False negatives** - Network fine, just slow
- **Geographic bias** - Works for some locations, not others

### Potential Fixes

**1. Adaptive Timeout Configuration**
```python
# In config.py
SSH_TIMEOUTS = {
    'connect': 60,      # Connection establishment (was 30)
    'auth': 45,         # Authentication (was 30)
    'banner': 45,       # Banner exchange (was 30)
    'exec': 120,        # Command execution
    'channel': 300      # Channel operations
}

# In ssh_executor.py
def connect(self) -> bool:
    """Connect with generous timeouts for slow networks"""
    try:
        self.client = paramiko.SSHClient()
        self.client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        
        self.client.connect(
            hostname=self.jump_host,
            username=self.jump_user,
            timeout=SSH_TIMEOUTS['connect'],
            banner_timeout=SSH_TIMEOUTS['banner'],
            auth_timeout=SSH_TIMEOUTS['auth'],
            # Disable DNS resolution timeout (can be slow)
            look_for_keys=True,
            allow_agent=True
        )
        
        # Set channel timeout
        transport = self.client.get_transport()
        transport.set_keepalive(30)
        
        return True
    except socket.timeout:
        logging.error("Connection timed out - network may be slow")
        return False
    except Exception as e:
        logging.error(f"Connection failed: {e}")
        return False
```

**2. Measure and Adjust Timeout**
```python
import time

def measure_connection_time(host: str) -> float:
    """Measure how long connection takes"""
    start = time.time()
    
    try:
        client = paramiko.SSHClient()
        client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        client.connect(host, timeout=120)
        client.close()
        
        duration = time.time() - start
        return duration
    except:
        return -1

def adaptive_timeout():
    """Calculate appropriate timeout based on measurement"""
    measured_time = measure_connection_time(JUMP_HOST)
    
    if measured_time < 0:
        # Connection failed, use max timeout
        return 120
    
    # Use 3x measured time as timeout (with min/max bounds)
    timeout = max(30, min(180, measured_time * 3))
    logging.info(f"Adaptive timeout: {timeout}s (measured: {measured_time:.1f}s)")
    return timeout
```

**3. TCP Options for Slow Networks**
```python
def connect_slow_network(self) -> bool:
    """Configure SSH for slow/high-latency networks"""
    try:
        self.client = paramiko.SSHClient()
        self.client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        
        # Initial connection
        self.client.connect(
            hostname=self.jump_host,
            username=self.jump_user,
            timeout=120,
            compress=True  # Enable compression for slow links
        )
        
        # Configure TCP socket for high latency
        transport = self.client.get_transport()
        sock = transport.sock
        
        # Increase TCP buffer sizes
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_RCVBUF, 524288)  # 512KB
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_SNDBUF, 524288)
        
        # Disable Nagle's algorithm (better for interactive use)
        sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
        
        return True
    except Exception as e:
        logging.error(f"Connection failed: {e}")
        return False
```

**4. Connection with Retry and Backoff**
```python
def connect_with_patience(self, max_attempts=3) -> bool:
    """Retry with increasing timeouts"""
    base_timeout = 30
    
    for attempt in range(max_attempts):
        timeout = base_timeout * (attempt + 1)  # 30s, 60s, 90s
        
        try:
            logging.info(f"Connection attempt {attempt+1}/{max_attempts} (timeout: {timeout}s)")
            
            self.client = paramiko.SSHClient()
            self.client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
            
            self.client.connect(
                hostname=self.jump_host,
                username=self.jump_user,
                timeout=timeout,
                banner_timeout=timeout,
                auth_timeout=timeout
            )
            
            logging.info(f"Connected successfully on attempt {attempt+1}")
            return True
            
        except socket.timeout:
            logging.warning(f"Attempt {attempt+1} timed out after {timeout}s")
            if attempt < max_attempts - 1:
                time.sleep(5)
        except Exception as e:
            logging.error(f"Attempt {attempt+1} failed: {e}")
            return False
    
    return False
```

---

## Issue 6: Too Many Simultaneous SSH Connections - Connection Refused

### Potential Reasons/Sources
1. **MaxSessions limit** - sshd_config MaxSessions reached
2. **MaxStartups limit** - sshd_config MaxStartups exceeded
3. **Worker threads** - 8 workers × connections = many connections
4. **Connection pooling missing** - New connection per operation
5. **Connections not closed** - Resource leak
6. **Rate limiting** - Jump host limiting connection rate
7. **File descriptor limit** - System FD limit reached
8. **Memory exhaustion** - Too many SSH daemons
9. **Cloud provider limits** - AWS/GCP connection limits
10. **DDoS protection** - Automated blocking

### Consequences
- **Connection refused errors** - New connections fail
- **System-wide failure** - All workers blocked
- **Cascading failure** - Existing connections timeout
- **Manual intervention required** - Restart SSH daemon
- **Service degradation** - Queue backs up
- **Cannot scale** - Adding workers makes it worse

### Potential Fixes

**1. Connection Pooling**
```python
from queue import Queue
import threading

class SSHConnectionPool:
    """Pool of reusable SSH connections"""
    
    def __init__(self, node_id: int, pool_size: int = 3):
        self.node_id = node_id
        self.pool_size = pool_size
        self.pool = Queue(maxsize=pool_size)
        self.lock = threading.Lock()
        
        # Pre-create connections
        for _ in range(pool_size):
            executor = SSHExecutor(node_id)
            if executor.connect():
                self.pool.put(executor)
    
    def get_connection(self, timeout=30):
        """Get a connection from pool"""
        try:
            executor = self.pool.get(timeout=timeout)
            
            # Check if still alive
            if not executor.check_connection_alive():
                executor.disconnect()
                executor.connect()
            
            return executor
        except Queue.Empty:
            # Pool exhausted, create new connection
            executor = SSHExecutor(self.node_id)
            if executor.connect():
                return executor
            return None
    
    def return_connection(self, executor):
        """Return connection to pool"""
        try:
            if executor.check_connection_alive():
                self.pool.put(executor, block=False)
            else:
                executor.disconnect()
        except Queue.Full:
            # Pool full, close this connection
            executor.disconnect()

# Global connection pools
connection_pools = {}
for node_id in range(8):
    connection_pools[node_id] = SSHConnectionPool(node_id, pool_size=3)

# In worker.py
def process_job(self, job):
    """Use pooled connection"""
    executor = connection_pools[job.node_id].get_connection()
    if not executor:
        job.status = 'failed'
        return
    
    try:
        # Do work
        pid = executor.start_job(job.job_id, job.code_path, job.competition_id)
        # ...
    finally:
        # Always return to pool
        connection_pools[job.node_id].return_connection(executor)
```

**2. Single Persistent Connection Per Worker**
```python
class Worker:
    """Worker with persistent SSH connection"""
    
    def __init__(self, node_id: int):
        self.node_id = node_id
        self.executor = SSHExecutor(node_id)
        self.connected = False
    
    def ensure_connected(self):
        """Ensure we have a connection"""
        if not self.connected or not self.executor.check_connection_alive():
            self.executor.disconnect()
            self.connected = self.executor.connect()
        return self.connected
    
    def run(self):
        """Worker main loop with single connection"""
        while True:
            # Ensure connected
            if not self.ensure_connected():
                logging.error(f"Worker {self.node_id}: Cannot connect")
                time.sleep(10)
                continue
            
            # Get next job (reusing same connection)
            job = queue_manager.get_next_job(self.node_id)
            if job:
                self.process_job(job)
            
            time.sleep(1)
```

**3. Rate Limiting Connection Attempts**
```python
import time
from collections import deque

class ConnectionRateLimiter:
    """Limit rate of new SSH connections"""
    
    def __init__(self, max_per_minute=20):
        self.max_per_minute = max_per_minute
        self.attempts = deque()
        self.lock = threading.Lock()
    
    def can_connect(self) -> bool:
        """Check if we can make a new connection"""
        with self.lock:
            now = time.time()
            
            # Remove attempts older than 1 minute
            while self.attempts and self.attempts[0] < now - 60:
                self.attempts.popleft()
            
            # Check limit
            if len(self.attempts) >= self.max_per_minute:
                wait_time = 60 - (now - self.attempts[0])
                logging.warning(f"Rate limit reached, wait {wait_time:.1f}s")
                return False
            
            # Record this attempt
            self.attempts.append(now)
            return True
    
    def wait_and_connect(self, executor):
        """Wait for rate limit then connect"""
        while not self.can_connect():
            time.sleep(1)
        
        return executor.connect()

# Global rate limiter
ssh_rate_limiter = ConnectionRateLimiter(max_per_minute=20)

# Use it
ssh_rate_limiter.wait_and_connect(executor)
```

**4. Increase Server Limits**
```bash
# On jump host, edit /etc/ssh/sshd_config
MaxSessions 50      # Default is 10
MaxStartups 30:30:60  # Default is 10:30:60

# Restart SSH daemon
sudo systemctl restart sshd
```

**5. Monitor Connection Count**
```python
def count_ssh_connections() -> int:
    """Count active SSH connections from this server"""
    try:
        # Count open connections to jump host
        result = subprocess.run(
            ['netstat', '-an', '|', 'grep', f'{JUMP_HOST}:22', '|', 'grep', 'ESTABLISHED'],
            shell=True,
            capture_output=True,
            text=True
        )
        count = len(result.stdout.strip().split('\n')) if result.stdout else 0
        return count
    except:
        return 0

def alert_if_too_many_connections():
    """Alert if connection count is high"""
    count = count_ssh_connections()
    if count > 40:
        logging.warning(f"High SSH connection count: {count}")
        send_alert(f"SSH connections: {count}/50")
```

---

## Issue 7: SSH Session Limit Reached on GPU Node

### Potential Reasons/Sources
1. **MaxSessions per connection** - sshd limit per user
2. **Too many concurrent operations** - Multiple exec_command() calls
3. **Sessions not closed** - Resource leak
4. **Multiplexing issues** - ControlMaster problems
5. **PAM session limits** - /etc/security/limits.conf
6. **systemd limits** - User slice resource limits
7. **Channels not cleaned up** - Paramiko channel leak
8. **Long-running commands** - Sessions held open
9. **File descriptor limit** - Per-user FD limit
10. **Kernel limits** - Maximum PIDs per user

### Consequences
- **Channel creation fails** - Cannot exec commands
- **Job execution blocked** - Cannot start new jobs
- **Monitoring fails** - Cannot check job status
- **Resource leak** - Sessions accumulate
- **Node becomes unusable** - All operations fail
- **Manual cleanup required** - SSH in and kill sessions

### Potential Fixes

**1. Properly Close Sessions**
```python
def exec_command_with_cleanup(self, command: str, timeout=None) -> str:
    """Execute command and properly clean up session"""
    stdin = stdout = stderr = None
    
    try:
        stdin, stdout, stderr = self.client.exec_command(command, timeout=timeout)
        
        # Wait for command to complete
        exit_status = stdout.channel.recv_exit_status()
        
        # Read output
        output = stdout.read().decode('utf-8')
        error = stderr.read().decode('utf-8')
        
        return output
        
    finally:
        # Always close streams
        if stdin:
            stdin.close()
        if stdout:
            stdout.close()
        if stderr:
            stderr.close()
```

**2. Session Pooling**
```python
class SSHSessionPool:
    """Reuse SSH sessions (channels) within a connection"""
    
    def __init__(self, ssh_client, max_sessions=5):
        self.client = ssh_client
        self.max_sessions = max_sessions
        self.active_sessions = 0
        self.lock = threading.Lock()
    
    def can_create_session(self) -> bool:
        """Check if we can create another session"""
        with self.lock:
            return self.active_sessions < self.max_sessions
    
    def exec_command(self, command: str, timeout=None):
        """Execute command with session management"""
        # Wait for available session slot
        while not self.can_create_session():
            time.sleep(0.1)
        
        with self.lock:
            self.active_sessions += 1
        
        try:
            stdin, stdout, stderr = self.client.exec_command(command, timeout=timeout)
            output = stdout.read().decode()
            
            # Clean up
            stdin.close()
            stdout.close()
            stderr.close()
            
            return output
            
        finally:
            with self.lock:
                self.active_sessions -= 1
```

**3. Command Batching**
```python
def exec_commands_batch(self, commands: list) -> list:
    """Execute multiple commands in single session"""
    # Combine commands with &&
    combined = ' && '.join([f'({cmd})' for cmd in commands])
    
    try:
        stdin, stdout, stderr = self.client.exec_command(combined)
        output = stdout.read().decode()
        
        # Parse individual outputs
        # (would need better delimiter in practice)
        return output.split('\n')
        
    finally:
        stdin.close()
        stdout.close()
        stderr.close()
```

**4. Monitor Session Count**
```python
def count_active_sessions(self) -> int:
    """Count active SSH sessions to this host"""
    try:
        stdin, stdout, stderr = self.client.exec_command('who | wc -l')
        count = int(stdout.read().decode().strip())
        stdout.close()
        return count
    except:
        return -1

def ensure_session_limit_not_exceeded(self):
    """Check session count before creating new one"""
    count = self.count_active_sessions()
    if count > 8:  # Warning threshold
        logging.warning(f"High session count on node: {count}")
        # Could wait or use different node
        time.sleep(5)
```

**5. Increase Node Limits**
```bash
# On GPU node, edit /etc/ssh/sshd_config
MaxSessions 100  # Increase from default 10

# Edit /etc/security/limits.conf
gpuuser soft nofile 65536
gpuuser hard nofile 65536
gpuuser soft nproc 32768
gpuuser hard nproc 32768

# Restart SSH
sudo systemctl restart sshd
```

---

## Issue 8: Network Partition Between Jump Host and GPU Nodes

### Potential Reasons/Sources
1. **Switch failure** - Network equipment down
2. **VLAN misconfiguration** - Network segmentation error
3. **Routing issue** - Routes lost or misconfigured
4. **Firewall change** - New rules block traffic
5. **Cable unplugged** - Physical disconnection
6. **ARP cache issues** - Layer 2 problems
7. **MTU mismatch** - Packet fragmentation issues
8. **DHCP failure** - IP addresses lost
9. **DNS failure** - Cannot resolve hostnames
10. **Security isolation** - Intentional network split

### Consequences
- **Jump host works but nodes unreachable** - Confusing failure mode
- **Cannot execute any jobs** - All nodes inaccessible
- **Health checks fail** - Nodes appear down
- **Manual intervention required** - Network admin needed
- **Service outage** - Complete system unavailable
- **Difficult to diagnose** - Jump host accessible but useless

### Potential Fixes

**1. Network Connectivity Test**
```python
def test_network_path(self) -> dict:
    """Test network connectivity from jump host to GPU node"""
    if not self.client:
        return {'reachable': False, 'error': 'Not connected to jump host'}
    
    try:
        # Ping test
        stdin, stdout, stderr = self.client.exec_command(
            f'ping -c 3 -W 2 {self.node_ip}'
        )
        ping_output = stdout.read().decode()
        ping_success = 'bytes from' in ping_output
        
        # TCP connection test
        stdin, stdout, stderr = self.client.exec_command(
            f'nc -zv -w 5 {self.node_ip} {SSH_PORT}'
        )
        nc_output = stderr.read().decode()  # nc outputs to stderr
        tcp_success = 'succeeded' in nc_output or 'open' in nc_output
        
        # Traceroute (limited hops)
        stdin, stdout, stderr = self.client.exec_command(
            f'traceroute -m 10 -w 2 {self.node_ip}'
        )
        trace_output = stdout.read().decode()
        
        return {
            'reachable': ping_success and tcp_success,
            'ping': ping_success,
            'tcp_port': tcp_success,
            'traceroute': trace_output[:500],  # First 500 chars
            'node_ip': self.node_ip
        }
        
    except Exception as e:
        return {
            'reachable': False,
            'error': str(e)
        }
```

**2. Diagnostic Endpoint**
```python
# In api.py
@app.get("/api/diagnostics/network")
async def diagnose_network(authorization: str = Header(...), db: Session = Depends(get_db)):
    """Diagnose network connectivity issues (admin only)"""
    # Check admin
    token_result = auth.validate_token(authorization.split(" ")[1], db)
    if not token_result or not token_result[1]:
        raise HTTPException(status_code=403, detail="Admin access required")
    
    results = {}
    
    for node_id in range(8):
        executor = SSHExecutor(node_id)
        if executor.connect():
            test_result = executor.test_network_path()
            results[f'node_{node_id}'] = test_result
            executor.disconnect()
        else:
            results[f'node_{node_id}'] = {
                'reachable': False,
                'error': 'Cannot connect to jump host'
            }
    
    return {
        'timestamp': datetime.utcnow().isoformat(),
        'jump_host': JUMP_HOST,
        'nodes': results
    }
```

**3. Automatic Failover to Working Nodes**
```python
def get_reachable_nodes() -> list:
    """Get list of currently reachable nodes"""
    reachable = []
    
    for node_id in range(8):
        executor = SSHExecutor(node_id)
        if executor.connect():
            test = executor.test_network_path()
            if test.get('reachable'):
                reachable.append(node_id)
            executor.disconnect()
    
    return reachable

# In queue_manager.py
def assign_job_to_best_node(self, job):
    """Assign job only to reachable nodes"""
    reachable_nodes = get_reachable_nodes()
    
    if not reachable_nodes:
        logging.error("No reachable nodes!")
        return None
    
    # Pick from reachable nodes with shortest queue
    best_node = min(reachable_nodes, 
                   key=lambda n: self.get_total_queue_time(n))
    
    return best_node
```

---

*[Continuing with remaining issues...]*

## Summary & Priority Matrix

| Issue | Severity | Likelihood | Priority | Effort |
|-------|----------|------------|----------|--------|
| Connection drops mid-job | High | High | 🔴 P0 | Medium |
| Jump host down | Critical | Low | 🔴 P0 | High |
| Auth fails randomly | Medium | Medium | 🟡 P1 | Low |
| Port forwarding breaks | High | Low | 🟡 P1 | Medium |
| Timeout too short | Low | High | 🟢 P2 | Low |
| Too many connections | High | Medium | 🔴 P0 | Medium |
| Session limit | Medium | Medium | 🟡 P1 | Low |
| Network partition | Critical | Low | 🟡 P1 | High |

## Quick Wins

**Immediate improvements (low effort, high impact):**

1. **Enable SSH keep-alive** - Prevents connection drops
2. **Increase timeouts** - Handle slow networks
3. **Validate SSH key on startup** - Catch config issues early
4. **Connection retry with backoff** - Handle transient failures
5. **Proper session cleanup** - Prevent resource leaks

```python
# Apply these in ssh_executor.py
def connect(self) -> bool:
    """Improved connection with quick wins"""
    for attempt in range(3):
        try:
            self.client = paramiko.SSHClient()
            self.client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
            
            self.client.connect(
                hostname=self.jump_host,
                username=self.jump_user,
                password=SSH_PASSWORD,
                timeout=60,  # Increased
                banner_timeout=60,
                auth_timeout=60,
                compress=True  # For slow networks
            )
            
            # Keep-alive
            transport = self.client.get_transport()
            transport.set_keepalive(30)
            
            return True
        except Exception as e:
            if attempt < 2:
                time.sleep(2 ** attempt)
                continue
            logging.error(f"Connection failed: {e}")
            return False
```

