"""Performance tracking decorator for automatic profiling."""

import functools
import inspect
import time
import logging
from typing import Callable, Any

logger = logging.getLogger("guildscout.performance")


def track_performance(operation_name: str = None):
    """
    Decorator to automatically track function execution time.

    Usage:
        @track_performance("my_operation")
        async def my_function():
            ...

        @track_performance()  # Uses function name
        def my_sync_function():
            ...

    Args:
        operation_name: Custom name for the operation (defaults to function name)
    """
    def decorator(func: Callable) -> Callable:
        # Import here to avoid circular imports
        from src.commands.profile import get_tracker

        op_name = operation_name or f"{func.__module__}.{func.__name__}"

        if inspect.iscoroutinefunction(func):
            @functools.wraps(func)
            async def async_wrapper(*args, **kwargs) -> Any:
                tracker = get_tracker()
                start_time = time.perf_counter()
                error_occurred = False

                try:
                    result = await func(*args, **kwargs)
                    return result
                except Exception as e:
                    error_occurred = True
                    raise
                finally:
                    duration = time.perf_counter() - start_time
                    tracker.record_execution(op_name, duration, error=error_occurred)

                    # Log slow operations (>1s)
                    if duration > 1.0:
                        logger.warning(f"Slow operation: {op_name} took {duration:.2f}s")

            return async_wrapper
        else:
            @functools.wraps(func)
            def sync_wrapper(*args, **kwargs) -> Any:
                tracker = get_tracker()
                start_time = time.perf_counter()
                error_occurred = False

                try:
                    result = func(*args, **kwargs)
                    return result
                except Exception as e:
                    error_occurred = True
                    raise
                finally:
                    duration = time.perf_counter() - start_time
                    tracker.record_execution(op_name, duration, error=error_occurred)

                    # Log slow operations (>1s)
                    if duration > 1.0:
                        logger.warning(f"Slow operation: {op_name} took {duration:.2f}s")

            return sync_wrapper

    return decorator
