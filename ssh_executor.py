"""
SSH Executor - handles remote job execution on GPU nodes
"""

import paramiko
import time
import os
import socket
import logging
from typing import Tuple, Optional
import config

# Configure logging
logging.basicConfig(level=logging.INFO)


class SSHExecutor:
    def __init__(self, node_id: int):
        self.node_id = node_id
        self.node_ip = config.GPU_NODES[node_id]["ip"]
        self.client = None
        self.jump_client = None
    
    def connect(self) -> bool:
        """Establish SSH connection to GPU node via jump host"""
        for attempt in range(config.SSH_RETRY_ATTEMPTS):
            try:
                return self._connect_via_jump_host()
            except Exception as e:
                print(f"SSH connection attempt {attempt + 1} failed for node {self.node_id}: {e}")
                if attempt < config.SSH_RETRY_ATTEMPTS - 1:
                    time.sleep(2)
        return False
    
    def _connect_via_jump_host(self) -> bool:
        """Connect to GPU node via SSH jump host"""
        try:
            # Connect to jump host first
            self.jump_client = paramiko.SSHClient()
            self.jump_client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
            
            # Try SSH key first, then fall back to agent
            jump_key_path = config.JUMP_SSH_KEY or os.path.expanduser("~/.ssh/id_rsa")
            
            try:
                self.jump_client.connect(
                    hostname=config.JUMP_HOST,
                    username=config.JUMP_USER,
                    key_filename=jump_key_path if os.path.exists(jump_key_path) else None,
                    timeout=config.SSH_TIMEOUT,
                    banner_timeout=config.SSH_TIMEOUT,
                    auth_timeout=config.SSH_TIMEOUT,
                    look_for_keys=True,
                    allow_agent=True
                )
                
                # ISSUE 1 FIX: Enable SSH keep-alive
                jump_transport = self.jump_client.get_transport()
                jump_transport.set_keepalive(60)  # Send keepalive every 60s
                
                # TCP keep-alive at OS level
                try:
                    sock = jump_transport.sock
                    sock.setsockopt(socket.SOL_SOCKET, socket.SO_KEEPALIVE, 1)
                    sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_KEEPIDLE, 60)
                    sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_KEEPINTVL, 10)
                    sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_KEEPCNT, 3)
                except (OSError, AttributeError) as e:
                    # Some systems don't support all TCP options
                    logging.warning(f"Could not set all TCP keepalive options: {e}")
                
            except Exception as e:
                print(f"Jump host connection failed: {e}")
                return False
            
            # Create a channel through jump host to GPU node
            jump_transport = self.jump_client.get_transport()
            dest_addr = (self.node_ip, config.SSH_PORT)
            local_addr = ('127.0.0.1', 0)
            channel = jump_transport.open_channel("direct-tcpip", dest_addr, local_addr)
            
            # Connect to GPU node via the channel
            self.client = paramiko.SSHClient()
            self.client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
            self.client.connect(
                hostname=self.node_ip,
                port=config.SSH_PORT,
                username=config.SSH_USERNAME,
                password=config.SSH_PASSWORD,
                sock=channel,
                timeout=config.SSH_TIMEOUT,
                banner_timeout=config.SSH_TIMEOUT,
                auth_timeout=config.SSH_TIMEOUT
            )
            
            # ISSUE 1 FIX: Enable keep-alive on GPU node connection too
            node_transport = self.client.get_transport()
            node_transport.set_keepalive(60)
            
            return True
            
        except Exception as e:
            print(f"Jump host connection failed for node {self.node_id}: {e}")
            if self.jump_client:
                self.jump_client.close()
                self.jump_client = None
            return False
    
    def disconnect(self):
        """Close SSH connection"""
        if self.client:
            self.client.close()
            self.client = None
        if self.jump_client:
            self.jump_client.close()
            self.jump_client = None
    
    def check_connection_alive(self) -> bool:
        """
        ISSUE 1 FIX: Check if SSH connection is still alive
        Returns True if connection is healthy, False otherwise
        """
        if not self.client:
            return False
        
        try:
            # Check if transport is active
            transport = self.client.get_transport()
            if not transport or not transport.is_active():
                return False
            
            # Try lightweight command
            stdin, stdout, stderr = self.client.exec_command('echo alive', timeout=5)
            result = stdout.read().decode().strip()
            
            # Clean up
            stdin.close()
            stdout.close()
            stderr.close()
            
            return result == 'alive'
        except Exception as e:
            logging.warning(f"Connection health check failed: {e}")
            return False
    
    def ensure_connected(self) -> bool:
        """
        ISSUE 1 FIX: Ensure connection is alive, reconnect if needed
        Returns True if connected (or successfully reconnected)
        """
        if self.check_connection_alive():
            return True
        
        logging.warning(f"Connection lost to node {self.node_id}, reconnecting...")
        self.disconnect()
        return self.connect()
    
    def upload_file(self, local_path: str, remote_path: str) -> bool:
        """Upload file to GPU node"""
        try:
            sftp = self.client.open_sftp()
            sftp.put(local_path, remote_path)
            sftp.close()
            return True
        except Exception as e:
            print(f"File upload failed for node {self.node_id}: {e}")
            return False
    
    def execute_command(self, command: str) -> Tuple[int, str, str]:
        """
        Execute command on GPU node
        Returns: (exit_code, stdout, stderr)
        """
        try:
            stdin, stdout, stderr = self.client.exec_command(command)
            exit_code = stdout.channel.recv_exit_status()
            stdout_str = stdout.read().decode('utf-8')
            stderr_str = stderr.read().decode('utf-8')
            return exit_code, stdout_str, stderr_str
        except Exception as e:
            return -1, "", str(e)
    
    def start_job(self, job_id: str, script_path: str, competition_id: str) -> Optional[int]:
        """
        Start grading job in background and return PID
        Uploads solution.py and runs grade_code.py
        """
        # Remote paths
        remote_solution = f"/home/gpuuser/work/solution.py"
        remote_results = f"/home/gpuuser/work/results.jsonl"
        remote_stdout = f"/tmp/job_{job_id}.out"
        remote_stderr = f"/tmp/job_{job_id}.err"
        
        # Ensure work directory exists
        self.execute_command("mkdir -p /home/gpuuser/work")
        
        # Upload solution file
        if not self.upload_file(script_path, remote_solution):
            return None
        
        # Build grading command
        grading_command = (
            f"cd /home/gpuuser/aira-dojo && "
            f"/home/gpuuser/miniforge3/envs/aira-dojo/bin/python "
            f"src/dojo/grade_code.py {remote_solution} {competition_id} {remote_results}"
        )
        
        # Start job in background and capture PID
        # Using setsid + nohup for maximum SSH drop protection:
        # - setsid: Creates new session, detaches from controlling terminal
        # - nohup: Immune to SIGHUP signals
        # - &: Runs in background
        command = (
            f"setsid nohup bash -c '{grading_command}' > {remote_stdout} 2> {remote_stderr} </dev/null & "
            f"echo $!"
        )
        
        exit_code, stdout, stderr = self.execute_command(command)
        
        if exit_code == 0 and stdout.strip():
            try:
                pid = int(stdout.strip())
                return pid
            except ValueError:
                print(f"Failed to parse PID: {stdout}")
                return None
        else:
            print(f"Failed to start job on node {self.node_id}: {stderr}")
            return None
    
    def is_process_running(self, pid: int) -> bool:
        """Check if process is still running"""
        command = f"ps -p {pid} > /dev/null 2>&1 && echo 'running' || echo 'stopped'"
        exit_code, stdout, stderr = self.execute_command(command)
        return stdout.strip() == 'running'
    
    def kill_process(self, pid: int) -> bool:
        """Kill running process"""
        command = f"kill -9 {pid}"
        exit_code, stdout, stderr = self.execute_command(command)
        return exit_code == 0
    
    def get_job_output(self, job_id: str) -> Tuple[str, str, str]:
        """
        Fetch results.jsonl, stdout and stderr from completed job
        Returns: (results_jsonl, stdout, stderr)
        
        ISSUE 1 FIX: Includes retry logic with connection recovery
        """
        return self.get_job_output_with_retry(job_id, max_retries=5)
    
    def get_job_output_with_retry(self, job_id: str, max_retries=5) -> Tuple[str, str, str]:
        """
        ISSUE 1 FIX: Try multiple times to retrieve job output
        Handles connection drops during result retrieval
        """
        remote_results = f"/home/gpuuser/work/results.jsonl"
        remote_stdout = f"/tmp/job_{job_id}.out"
        remote_stderr = f"/tmp/job_{job_id}.err"
        
        for attempt in range(max_retries):
            try:
                # Ensure connected
                if not self.ensure_connected():
                    logging.warning(f"Attempt {attempt+1}/{max_retries}: Reconnecting...")
                    time.sleep(5 * (attempt + 1))  # Exponential backoff
                    continue
                
                # Read results.jsonl
                command = f"cat {remote_results} 2>/dev/null || echo ''"
                _, results, _ = self.execute_command(command)
                
                # Read stdout
                command = f"cat {remote_stdout} 2>/dev/null || echo ''"
                _, stdout, _ = self.execute_command(command)
                
                # Read stderr
                command = f"cat {remote_stderr} 2>/dev/null || echo ''"
                _, stderr, _ = self.execute_command(command)
                
                logging.info(f"Successfully retrieved job output for {job_id} on attempt {attempt+1}")
                return results, stdout, stderr
                
            except Exception as e:
                logging.error(f"Attempt {attempt+1}/{max_retries} failed: {e}")
                if attempt < max_retries - 1:
                    time.sleep(5 * (attempt + 1))
                    # Try to reconnect
                    self.disconnect()
                else:
                    # Final attempt failed
                    logging.error(f"Failed to retrieve job output after {max_retries} attempts")
                    raise
        
        return "", "", "Failed to retrieve job output"
    
    def cleanup_job_files(self, job_id: str):
        """Remove temporary job files from GPU node"""
        files = [
            f"/home/gpuuser/work/solution.py",
            f"/home/gpuuser/work/results.jsonl",
            f"/tmp/job_{job_id}.out",
            f"/tmp/job_{job_id}.err"
        ]
        for file in files:
            self.execute_command(f"rm -f {file}")
    
    def restart_node_lxc(self, container_name: str = None) -> bool:
        """
        Restart GPU node using LXC
        This gives a clean environment between jobs
        
        Args:
            container_name: LXC container name (e.g., 'gpu-node-0')
                          If None, uses 'gpu-node-{node_id}'
        
        Returns:
            True if restart successful
        """
        if container_name is None:
            container_name = f"gpu-node-{self.node_id}"
        
        try:
            logging.info(f"Restarting LXC container: {container_name}")
            
            # Restart the container
            # Note: This command runs on the jump host, not inside the container
            if self.jump_client:
                stdin, stdout, stderr = self.jump_client.exec_command(
                    f"lxc restart {container_name}",
                    timeout=60
                )
                exit_code = stdout.channel.recv_exit_status()
                
                stdin.close()
                stdout.close()
                stderr_text = stderr.read().decode()
                stderr.close()
                
                if exit_code == 0:
                    logging.info(f"Successfully restarted {container_name}")
                    
                    # Wait for container to be ready (30 seconds)
                    time.sleep(30)
                    
                    # Reconnect
                    self.disconnect()
                    return self.connect()
                else:
                    logging.error(f"LXC restart failed: {stderr_text}")
                    return False
            else:
                logging.error("No jump host connection for LXC restart")
                return False
                
        except Exception as e:
            logging.error(f"Error restarting LXC container: {e}")
            return False

