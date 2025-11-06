"""
Worker threads - one per GPU node to process jobs from queue
"""

import threading
import time
import os
from datetime import datetime
from typing import List
import config
import models
from queue_manager import queue_manager
from ssh_executor import SSHExecutor


class Worker(threading.Thread):
    def __init__(self, node_id: int):
        super().__init__(daemon=True)
        self.node_id = node_id
        self.running = True
        self.executor = SSHExecutor(node_id)
    
    def run(self):
        """Main worker loop"""
        print(f"Worker for node {self.node_id} started")
        
        while self.running:
            # Get next job from queue
            job_id = queue_manager.get_next_job(self.node_id)
            
            if job_id:
                self.process_job(job_id)
            else:
                # No jobs, sleep briefly
                time.sleep(config.WORKER_POLL_INTERVAL)
    
    def process_job(self, job_id: str):
        """Process a single job"""
        db = next(models.get_db())
        
        try:
            # Get job from database
            job = db.query(models.Job).filter(models.Job.job_id == job_id).first()
            if not job:
                print(f"Job {job_id} not found in database")
                return
            
            # Update job status to running
            job.status = "running"
            job.node_id = self.node_id
            job.started_at = datetime.utcnow()
            db.commit()
            
            # Update node state
            node_state = db.query(models.NodeState).filter(
                models.NodeState.node_id == self.node_id
            ).first()
            if node_state:
                node_state.is_busy = True
                node_state.current_job_id = job_id
                db.commit()
            
            print(f"Starting job {job_id} on node {self.node_id}")
            
            # Connect to GPU node
            if not self.executor.connect():
                job.status = "failed"
                job.stderr = "Failed to connect to GPU node"
                job.completed_at = datetime.utcnow()
                db.commit()
                queue_manager.job_completed(self.node_id, job.expected_time)
                return
            
            # Start the job
            pid = self.executor.start_job(job_id, job.code_path, job.competition_id)
            
            if not pid:
                job.status = "failed"
                job.stderr = "Failed to start job on GPU node"
                job.completed_at = datetime.utcnow()
                db.commit()
                self.executor.disconnect()
                queue_manager.job_completed(self.node_id, job.expected_time)
                return
            
            # Store PID
            job.remote_pid = pid
            db.commit()
            
            # Monitor job execution
            timeout = job.expected_time * config.MAX_JOB_TIMEOUT_MULTIPLIER
            start_time = time.time()
            
            while True:
                # Check if job is still running
                if not self.executor.is_process_running(pid):
                    # Job completed
                    break
                
                # Check for timeout
                elapsed = time.time() - start_time
                if elapsed > timeout:
                    print(f"Job {job_id} timed out, killing process")
                    self.executor.kill_process(pid)
                    job.status = "failed"
                    job.stderr = f"Job exceeded timeout ({timeout}s)"
                    break
                
                # Refresh job from DB to check for cancellation
                db.refresh(job)
                if job.status == "cancelled":
                    print(f"Job {job_id} was cancelled, killing process")
                    self.executor.kill_process(pid)
                    break
                
                time.sleep(2)  # Poll every 2 seconds
            
            # Fetch output - now returns results.jsonl as stdout
            results_jsonl, stdout, stderr = self.executor.get_job_output(job_id)
            job.stdout = results_jsonl  # Return results.jsonl as main output
            job.stderr = stderr if job.status == "failed" else stderr
            
            # Save results.jsonl locally with user_competition_time format
            if results_jsonl.strip():
                timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
                results_filename = f"{job.user_id}_{job.competition_id}_{timestamp}.jsonl"
                results_dir = os.path.join(config.JOBS_DIR, "results")
                os.makedirs(results_dir, exist_ok=True)
                results_path = os.path.join(results_dir, results_filename)
                try:
                    with open(results_path, 'w') as f:
                        f.write(results_jsonl)
                    print(f"Saved results to: {results_path}")
                except Exception as e:
                    print(f"Failed to save results.jsonl locally: {e}")
            
            # Get exit code
            if job.status != "failed" and job.status != "cancelled":
                job.status = "completed"
                job.exit_code = 0
            
            job.completed_at = datetime.utcnow()
            db.commit()
            
            # Cleanup
            self.executor.cleanup_job_files(job_id)
            
            # Optional: Restart LXC container between jobs for clean environment
            if config.LXC_RESTART_BETWEEN_JOBS:
                container_name = f"{config.LXC_CONTAINER_PREFIX}-{self.node_id}"
                print(f"Restarting LXC container {container_name}...")
                if self.executor.restart_node_lxc(container_name):
                    print(f"Container {container_name} restarted successfully")
                else:
                    print(f"Warning: Failed to restart container {container_name}")
                    # Disconnect and reconnect anyway
                    self.executor.disconnect()
            else:
                self.executor.disconnect()
            
            print(f"Job {job_id} finished with status: {job.status}")
            
        except Exception as e:
            print(f"Error processing job {job_id}: {e}")
            job = db.query(models.Job).filter(models.Job.job_id == job_id).first()
            if job:
                job.status = "failed"
                job.stderr = str(e)
                job.completed_at = datetime.utcnow()
                db.commit()
        
        finally:
            # Mark node as not busy
            queue_manager.job_completed(self.node_id, job.expected_time)
            db.close()
    
    def stop(self):
        """Stop the worker thread"""
        self.running = False


class WorkerPool:
    def __init__(self):
        self.workers: List[Worker] = []
    
    def start(self):
        """Start all worker threads"""
        for i in range(8):
            worker = Worker(i)
            worker.start()
            self.workers.append(worker)
        print("All workers started")
    
    def stop(self):
        """Stop all worker threads"""
        for worker in self.workers:
            worker.stop()
        print("All workers stopped")


# Global worker pool
worker_pool = WorkerPool()

