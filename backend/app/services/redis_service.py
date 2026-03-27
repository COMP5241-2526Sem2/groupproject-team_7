"""
Upstash Redis service for serverless task queue and caching.

This module provides:
- Connection to Upstash Redis (HTTP-based, serverless-compatible)
- Task queue operations (enqueue, dequeue, status)
- Caching utilities
- Rate limiting support
"""

import os
import json
import uuid
from datetime import datetime
from typing import Any, Optional, Dict
from enum import Enum


class TaskStatus(str, Enum):
    """Task status enum for queue operations."""
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


class RedisService:
    """
    Upstash Redis service for serverless environments.
    
    Uses HTTP-based REST API which works in serverless functions
    without persistent connections.
    """
    
    def __init__(self):
        """Initialize Redis connection using Upstash credentials."""
        self._client = None
        self._initialized = False
    
    def _get_client(self):
        """Lazily initialize the Upstash Redis client."""
        if self._client is None:
            try:
                from upstash_redis import Redis
                
                url = os.environ.get("UPSTASH_REDIS_REST_URL", "")
                token = os.environ.get("UPSTASH_REDIS_REST_TOKEN", "")
                
                if url and token:
                    self._client = Redis(url=url, token=token)
                    self._initialized = True
                else:
                    print("Warning: Upstash Redis credentials not configured")
            except ImportError:
                print("Warning: upstash-redis package not installed")
            except Exception as e:
                print(f"Error initializing Upstash Redis: {e}")
        
        return self._client
    
    @property
    def is_available(self) -> bool:
        """Check if Redis is available and configured."""
        return self._get_client() is not None
    
    # ==================== Caching Operations ====================
    
    def get(self, key: str) -> Optional[Any]:
        """Get a value from cache."""
        client = self._get_client()
        if not client:
            return None
        
        try:
            value = client.get(key)
            if value:
                try:
                    return json.loads(value)
                except (json.JSONDecodeError, TypeError):
                    return value
            return None
        except Exception as e:
            print(f"Redis GET error: {e}")
            return None
    
    def set(self, key: str, value: Any, ttl: Optional[int] = None) -> bool:
        """
        Set a value in cache.
        
        Args:
            key: Cache key
            value: Value to store (will be JSON serialized)
            ttl: Time to live in seconds (optional)
        """
        client = self._get_client()
        if not client:
            return False
        
        try:
            serialized = json.dumps(value) if not isinstance(value, str) else value
            if ttl:
                client.setex(key, ttl, serialized)
            else:
                client.set(key, serialized)
            return True
        except Exception as e:
            print(f"Redis SET error: {e}")
            return False
    
    def delete(self, key: str) -> bool:
        """Delete a key from cache."""
        client = self._get_client()
        if not client:
            return False
        
        try:
            client.delete(key)
            return True
        except Exception as e:
            print(f"Redis DELETE error: {e}")
            return False
    
    def exists(self, key: str) -> bool:
        """Check if a key exists in cache."""
        client = self._get_client()
        if not client:
            return False
        
        try:
            return client.exists(key) > 0
        except Exception as e:
            print(f"Redis EXISTS error: {e}")
            return False
    
    # ==================== Task Queue Operations ====================
    
    def enqueue_task(
        self, 
        queue_name: str, 
        task_type: str, 
        payload: Dict[str, Any],
        priority: int = 0
    ) -> Optional[str]:
        """
        Add a task to the queue.
        
        Args:
            queue_name: Name of the queue (e.g., "video_processing")
            task_type: Type of task (e.g., "transcode", "generate_thumbnail")
            payload: Task data
            priority: Task priority (higher = more important)
            
        Returns:
            Task ID if successful, None otherwise
        """
        client = self._get_client()
        if not client:
            return None
        
        try:
            task_id = str(uuid.uuid4())
            task = {
                "id": task_id,
                "type": task_type,
                "payload": payload,
                "status": TaskStatus.PENDING.value,
                "priority": priority,
                "created_at": datetime.utcnow().isoformat(),
                "updated_at": datetime.utcnow().isoformat(),
            }
            
            # Store task data
            task_key = f"task:{task_id}"
            client.set(task_key, json.dumps(task))
            
            # Add to queue (sorted set with priority as score)
            queue_key = f"queue:{queue_name}"
            client.zadd(queue_key, {task_id: priority})
            
            return task_id
        except Exception as e:
            print(f"Redis ENQUEUE error: {e}")
            return None
    
    def dequeue_task(self, queue_name: str) -> Optional[Dict[str, Any]]:
        """
        Get the next task from the queue.
        
        Args:
            queue_name: Name of the queue
            
        Returns:
            Task data if available, None otherwise
        """
        client = self._get_client()
        if not client:
            return None
        
        try:
            queue_key = f"queue:{queue_name}"
            
            # Get highest priority task
            result = client.zpopmax(queue_key, 1)
            if not result:
                return None
            
            task_id = result[0][0] if isinstance(result[0], (list, tuple)) else result[0]
            
            # Get task data
            task_key = f"task:{task_id}"
            task_data = client.get(task_key)
            
            if task_data:
                task = json.loads(task_data)
                task["status"] = TaskStatus.PROCESSING.value
                task["updated_at"] = datetime.utcnow().isoformat()
                client.set(task_key, json.dumps(task))
                return task
            
            return None
        except Exception as e:
            print(f"Redis DEQUEUE error: {e}")
            return None
    
    def get_task(self, task_id: str) -> Optional[Dict[str, Any]]:
        """Get task data by ID."""
        client = self._get_client()
        if not client:
            return None
        
        try:
            task_key = f"task:{task_id}"
            task_data = client.get(task_key)
            if task_data:
                return json.loads(task_data)
            return None
        except Exception as e:
            print(f"Redis GET_TASK error: {e}")
            return None
    
    def update_task_status(
        self, 
        task_id: str, 
        status: TaskStatus, 
        result: Optional[Dict[str, Any]] = None,
        error: Optional[str] = None
    ) -> bool:
        """
        Update task status.
        
        Args:
            task_id: Task ID
            status: New status
            result: Task result (for completed tasks)
            error: Error message (for failed tasks)
        """
        client = self._get_client()
        if not client:
            return False
        
        try:
            task_key = f"task:{task_id}"
            task_data = client.get(task_key)
            
            if not task_data:
                return False
            
            task = json.loads(task_data)
            task["status"] = status.value
            task["updated_at"] = datetime.utcnow().isoformat()
            
            if result:
                task["result"] = result
            if error:
                task["error"] = error
            if status in [TaskStatus.COMPLETED, TaskStatus.FAILED]:
                task["completed_at"] = datetime.utcnow().isoformat()
            
            client.set(task_key, json.dumps(task))
            return True
        except Exception as e:
            print(f"Redis UPDATE_TASK error: {e}")
            return False
    
    def get_queue_length(self, queue_name: str) -> int:
        """Get the number of tasks in a queue."""
        client = self._get_client()
        if not client:
            return 0
        
        try:
            queue_key = f"queue:{queue_name}"
            return client.zcard(queue_key) or 0
        except Exception as e:
            print(f"Redis QUEUE_LENGTH error: {e}")
            return 0
    
    # ==================== Rate Limiting ====================
    
    def check_rate_limit(
        self, 
        key: str, 
        max_requests: int, 
        window_seconds: int
    ) -> tuple:
        """
        Check if a rate limit has been exceeded.
        
        Args:
            key: Rate limit key (e.g., "rate:user:123")
            max_requests: Maximum requests allowed in window
            window_seconds: Time window in seconds
            
        Returns:
            Tuple of (allowed: bool, remaining: int)
        """
        client = self._get_client()
        if not client:
            return True, max_requests  # Allow if Redis unavailable
        
        try:
            current = client.incr(key)
            
            if current == 1:
                client.expire(key, window_seconds)
            
            remaining = max(0, max_requests - current)
            allowed = current <= max_requests
            
            return allowed, remaining
        except Exception as e:
            print(f"Redis RATE_LIMIT error: {e}")
            return True, max_requests


# Singleton instance
redis_service = RedisService()
