"""
Job Queue Manager - handles job assignment and queue operations
"""

from collections import deque
from threading import Lock
from typing import Optional, List, Dict
import models


class QueueManager:
    def __init__(self):
        # 8 queues, one per GPU node
        self.node_queues: List[deque] = [deque() for _ in range(8)]
        self.node_loads: List[int] = [0] * 8  # cumulative expected_time
        self.lock = Lock()
    
    def assign_job(self, job_id: str, expected_time: int) -> int:
        """
        Assign job to node with minimum queue load
        Returns: node_id where job was assigned
        """
        with self.lock:
            # Find node with minimum load
            node_id = self.node_loads.index(min(self.node_loads))
            
            # Add job to that node's queue
            self.node_queues[node_id].append(job_id)
            self.node_loads[node_id] += expected_time
            
            # Update database
            db = next(models.get_db())
            try:
                node_state = db.query(models.NodeState).filter(
                    models.NodeState.node_id == node_id
                ).first()
                if node_state:
                    node_state.total_queue_time = self.node_loads[node_id]
                db.commit()
            finally:
                db.close()
            
            return node_id
    
    def get_next_job(self, node_id: int) -> Optional[str]:
        """Get next job from node's queue"""
        with self.lock:
            if self.node_queues[node_id]:
                job_id = self.node_queues[node_id].popleft()
                return job_id
            return None
    
    def remove_job(self, job_id: str, node_id: int, expected_time: int) -> bool:
        """
        Remove job from queue (for cancellation)
        Returns: True if job was in queue and removed
        """
        with self.lock:
            if job_id in self.node_queues[node_id]:
                self.node_queues[node_id].remove(job_id)
                self.node_loads[node_id] -= expected_time
                
                # Update database
                db = next(models.get_db())
                try:
                    node_state = db.query(models.NodeState).filter(
                        models.NodeState.node_id == node_id
                    ).first()
                    if node_state:
                        node_state.total_queue_time = self.node_loads[node_id]
                    db.commit()
                finally:
                    db.close()
                
                return True
            return False
    
    def job_completed(self, node_id: int, expected_time: int):
        """Update load when job completes"""
        with self.lock:
            self.node_loads[node_id] = max(0, self.node_loads[node_id] - expected_time)
            
            # Update database
            db = next(models.get_db())
            try:
                node_state = db.query(models.NodeState).filter(
                    models.NodeState.node_id == node_id
                ).first()
                if node_state:
                    node_state.total_queue_time = self.node_loads[node_id]
                    node_state.is_busy = False
                    node_state.current_job_id = None
                db.commit()
            finally:
                db.close()
    
    def get_queue_position(self, job_id: str, node_id: int) -> Optional[int]:
        """Get position of job in queue (0-indexed)"""
        with self.lock:
            try:
                queue_list = list(self.node_queues[node_id])
                return queue_list.index(job_id)
            except ValueError:
                return None
    
    def get_node_stats(self) -> List[Dict]:
        """Get statistics for all nodes"""
        with self.lock:
            stats = []
            for i in range(8):
                stats.append({
                    "node_id": i,
                    "queue_length": len(self.node_queues[i]),
                    "total_wait_time": self.node_loads[i],
                    "jobs_in_queue": list(self.node_queues[i])
                })
            return stats


# Global queue manager instance
queue_manager = QueueManager()

