"""
Rate limiting and security middleware
"""

import time
from collections import defaultdict
from datetime import datetime, timedelta
from typing import Dict, Tuple
import threading

class RateLimiter:
    def __init__(self):
        # {user_id: [(timestamp, count), ...]}
        self.user_requests: Dict[str, list] = defaultdict(list)
        self.lock = threading.Lock()
    
    def check_rate_limit(self, user_id: str, max_requests: int = 5, window_seconds: int = 60) -> Tuple[bool, str]:
        """
        Check if user has exceeded rate limit
        Returns: (allowed, message)
        """
        with self.lock:
            now = time.time()
            cutoff = now - window_seconds
            
            # Remove old requests outside window
            self.user_requests[user_id] = [
                ts for ts in self.user_requests[user_id] if ts > cutoff
            ]
            
            # Check current count
            current_count = len(self.user_requests[user_id])
            
            if current_count >= max_requests:
                oldest = min(self.user_requests[user_id])
                retry_after = int(window_seconds - (now - oldest)) + 1
                return False, f"Rate limit exceeded. Maximum {max_requests} requests per {window_seconds}s. Retry after {retry_after}s."
            
            # Add current request
            self.user_requests[user_id].append(now)
            return True, ""
    
    def get_user_request_count(self, user_id: str, window_seconds: int = 60) -> int:
        """Get current request count for user in window"""
        with self.lock:
            now = time.time()
            cutoff = now - window_seconds
            self.user_requests[user_id] = [
                ts for ts in self.user_requests[user_id] if ts > cutoff
            ]
            return len(self.user_requests[user_id])


class EndpointProtection:
    def __init__(self):
        # General endpoint rate limiting (per IP or global)
        self.endpoint_requests: Dict[str, list] = defaultdict(list)
        self.lock = threading.Lock()
    
    def check_endpoint_limit(self, identifier: str, max_requests: int = 100, window_seconds: int = 60) -> Tuple[bool, str]:
        """
        Check endpoint rate limit (for general API protection)
        identifier can be IP address or user_id
        """
        with self.lock:
            now = time.time()
            cutoff = now - window_seconds
            
            self.endpoint_requests[identifier] = [
                ts for ts in self.endpoint_requests[identifier] if ts > cutoff
            ]
            
            current_count = len(self.endpoint_requests[identifier])
            
            if current_count >= max_requests:
                oldest = min(self.endpoint_requests[identifier])
                retry_after = int(window_seconds - (now - oldest)) + 1
                return False, f"Too many requests. Maximum {max_requests} per {window_seconds}s. Retry after {retry_after}s."
            
            self.endpoint_requests[identifier].append(now)
            return True, ""


# Global instances
rate_limiter = RateLimiter()
endpoint_protection = EndpointProtection()

