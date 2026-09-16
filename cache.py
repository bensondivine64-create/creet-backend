"""Simple Redis (Upstash) caching helper. Fails silently if Redis is
unreachable so caching is always best-effort and never breaks a request."""
import json
from upstash_redis import Redis

_redis = Redis(
    url="https://natural-pug-280797.upstash.io",
    token="gQAAAAAABEjdAAIgcDEzNjFlYTEzNDIyYmY0Nzg3OWQzYTZkNzUwZTdkYWYzOQ",
)


def cache_get(key):
    try:
        raw = _redis.get(key)
        if raw is None:
            return None
        return json.loads(raw)
    except Exception:
        return None


def cache_set(key, value, ttl_seconds=60):
    try:
        _redis.set(key, json.dumps(value), ex=ttl_seconds)
    except Exception:
        pass


def cache_delete(key):
    try:
        _redis.delete(key)
    except Exception:
        pass
