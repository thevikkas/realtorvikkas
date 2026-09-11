"""Performance optimization for database queries and caching.

Implements database indexing, query optimization, and caching strategies.
"""

import logging
import time
from functools import wraps

perf_logger = logging.getLogger("performance")

# Database indexes to create for optimal performance
DATABASE_INDEXES = [
    # User lookups
    "CREATE INDEX IF NOT EXISTS idx_users_email ON users(email)",
    "CREATE INDEX IF NOT EXISTS idx_users_role ON users(role)",

    # Property searches
    "CREATE INDEX IF NOT EXISTS idx_properties_city ON properties(city)",
    "CREATE INDEX IF NOT EXISTS idx_properties_locality ON properties(locality)",
    "CREATE INDEX IF NOT EXISTS idx_properties_price ON properties(price)",
    "CREATE INDEX IF NOT EXISTS idx_properties_status ON properties(status)",
    "CREATE INDEX IF NOT EXISTS idx_properties_owner_id ON properties(owner_id)",
    "CREATE INDEX IF NOT EXISTS idx_properties_created_at ON properties(created_at)",

    # Composite indexes for common queries
    "CREATE INDEX IF NOT EXISTS idx_properties_city_status ON properties(city, status)",
    "CREATE INDEX IF NOT EXISTS idx_properties_locality_price ON properties(locality, price)",
    "CREATE INDEX IF NOT EXISTS idx_properties_ptype_city ON properties(ptype, city)",

    # Session lookups
    "CREATE INDEX IF NOT EXISTS idx_sessions_token ON sessions(token)",
    "CREATE INDEX IF NOT EXISTS idx_sessions_user_id ON sessions(user_id)",
    "CREATE INDEX IF NOT EXISTS idx_sessions_expires_at ON sessions(expires_at)",

    # Query optimization indexes
    "CREATE INDEX IF NOT EXISTS idx_enquiries_property_id ON enquiries(property_id)",
    "CREATE INDEX IF NOT EXISTS idx_enquiries_customer_id ON enquiries(customer_id)",
    "CREATE INDEX IF NOT EXISTS idx_favorites_user_id ON favorites(user_id)",
    "CREATE INDEX IF NOT EXISTS idx_favorites_property_id ON favorites(property_id)",
]


def create_indexes():
    """Create all performance indexes in the database."""
    from database import get_conn

    try:
        conn = get_conn()

        for index_sql in DATABASE_INDEXES:
            try:
                conn.execute(index_sql)
                perf_logger.info(f"Created index: {index_sql.split('ON')[1].split('(')[0].strip()}")
            except Exception as e:
                perf_logger.warning(f"Index creation skipped: {index_sql[:50]}... ({e})")

        conn.commit()
        conn.close()
        perf_logger.info("Database indexing complete")

    except Exception as e:
        perf_logger.error(f"Error creating indexes: {e}")


class QueryCache:
    """Simple in-memory cache for database queries."""

    def __init__(self, ttl_seconds=3600):
        self.cache = {}
        self.ttl = ttl_seconds
        perf_logger.info(f"Query cache initialized (TTL: {ttl_seconds}s)")

    def get(self, key):
        """Get a cached value."""
        if key in self.cache:
            value, timestamp = self.cache[key]
            age = time.time() - timestamp

            if age < self.ttl:
                perf_logger.debug(f"Cache hit for key: {key[:20]}...")
                return value
            else:
                del self.cache[key]
                perf_logger.debug(f"Cache expired for key: {key[:20]}...")

        return None

    def set(self, key, value):
        """Set a cached value."""
        self.cache[key] = (value, time.time())
        perf_logger.debug(f"Cache set for key: {key[:20]}...")

    def delete(self, key):
        """Delete a cached value."""
        if key in self.cache:
            del self.cache[key]
            perf_logger.debug(f"Cache deleted for key: {key[:20]}...")

    def clear(self):
        """Clear the entire cache."""
        self.cache.clear()
        perf_logger.info("Cache cleared")


# Global cache instance
_query_cache = QueryCache(ttl_seconds=3600)


def cached_query(ttl_seconds=3600):
    """
    Decorator for caching query results.

    Usage:
        @cached_query(ttl_seconds=1800)
        def get_properties_in_city(city):
            conn = get_conn()
            return conn.execute("SELECT * FROM properties WHERE city = ?", (city,)).fetchall()
    """
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            # Generate cache key from function name and arguments
            cache_key = f"{func.__name__}:{args}:{kwargs}"

            # Try to get from cache
            cached_value = _query_cache.get(cache_key)
            if cached_value is not None:
                return cached_value

            # Execute function and cache result
            result = func(*args, **kwargs)
            _query_cache.set(cache_key, result)

            return result

        return wrapper

    return decorator


def profile_query(func):
    """
    Decorator for profiling query performance.
    Logs queries that take longer than 100ms.
    """
    @wraps(func)
    def wrapper(*args, **kwargs):
        start_time = time.time()

        try:
            result = func(*args, **kwargs)
            return result
        finally:
            elapsed_ms = (time.time() - start_time) * 1000

            if elapsed_ms > 100:
                perf_logger.warning(
                    f"SLOW_QUERY: {func.__name__} took {elapsed_ms:.2f}ms "
                    f"(args: {args[:2]})"  # Only log first 2 args to avoid spam
                )

    return wrapper


def optimize_queries():
    """
    Run common query optimizations.
    Call this periodically to maintain database performance.
    """
    from database import get_conn

    try:
        conn = get_conn()

        # Optimize query execution
        conn.execute("ANALYZE")  # Update query optimization statistics

        # Vacuum database (defragment)
        conn.execute("VACUUM")

        conn.close()
        perf_logger.info("Database optimization complete")

    except Exception as e:
        perf_logger.error(f"Error optimizing database: {e}")
