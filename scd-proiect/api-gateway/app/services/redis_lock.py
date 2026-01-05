import redis
import os

# Connect to Redis
REDIS_URL = os.getenv("REDIS_URL", "redis://redis:6379/0")
r = redis.from_url(REDIS_URL)

def acquire_lock(lock_key: str, value: str, ttl_seconds: int = 30) -> bool:
    """
    Sets the lock key to 'value' (user_id) if it doesn't exist.
    """
    return r.set(lock_key, value, ex=ttl_seconds, nx=True)

def get_lock_owner(lock_key: str) -> str:
    val = r.get(lock_key)
    return val.decode('utf-8') if val else None

def release_lock(lock_key: str):
    r.delete(lock_key)

def check_lock(lock_key: str) -> bool:
    """Returns True if locked, False otherwise"""
    return r.exists(lock_key) == 1
