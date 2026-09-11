"""Centralized error handling and logging for production.

All errors are logged server-side with full stack traces.
Users see friendly error IDs, not technical details.
"""

import logging
import traceback
import secrets
from datetime import datetime
from functools import wraps

# Configure error logging
logging.basicConfig(
    level=logging.ERROR,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('error.log'),
        logging.StreamHandler()
    ]
)

error_logger = logging.getLogger("error_handler")


class AppError(Exception):
    """Base application error."""

    def __init__(self, message, error_code=None, status_code=500, user_message=None):
        self.message = message
        self.error_code = error_code or self._generate_error_id()
        self.status_code = status_code
        self.user_message = user_message or "An error occurred. Please try again."
        super().__init__(self.message)

    @staticmethod
    def _generate_error_id():
        """Generate a unique error ID for tracking."""
        return f"ERR-{secrets.token_hex(6).upper()}"

    def to_dict(self):
        """Return error as dictionary for JSON response."""
        return {
            "error": True,
            "error_id": self.error_code,
            "message": self.user_message,
            "status": self.status_code
        }


class ValidationError(AppError):
    """Input validation error (400)."""

    def __init__(self, message, field=None):
        super().__init__(
            message,
            status_code=400,
            user_message=f"Invalid {field}: {message}" if field else f"Validation error: {message}"
        )
        self.field = field


class AuthError(AppError):
    """Authentication error (401)."""

    def __init__(self, message):
        super().__init__(
            message,
            status_code=401,
            user_message="Authentication failed. Please log in again."
        )


class PermissionError(AppError):
    """Permission denied error (403)."""

    def __init__(self, message):
        super().__init__(
            message,
            status_code=403,
            user_message="You do not have permission to perform this action."
        )


class NotFoundError(AppError):
    """Resource not found error (404)."""

    def __init__(self, resource):
        super().__init__(
            f"{resource} not found",
            status_code=404,
            user_message=f"{resource} not found."
        )


class DatabaseError(AppError):
    """Database error (500)."""

    def __init__(self, message):
        super().__init__(
            message,
            status_code=500,
            user_message="Database error. Please try again later."
        )


class ExternalServiceError(AppError):
    """External service error (503)."""

    def __init__(self, service_name):
        super().__init__(
            f"External service {service_name} failed",
            status_code=503,
            user_message=f"Service temporarily unavailable. Please try again later."
        )


def log_error(error, context=None):
    """
    Log an error with full context and stack trace.

    Args:
        error: Exception object
        context: Additional context dictionary
    """
    error_id = getattr(error, 'error_code', AppError._generate_error_id())

    log_message = f"[{error_id}] {str(error)}"
    if context:
        log_message += f"\nContext: {context}"

    # Log stack trace
    stack_trace = traceback.format_exc()
    log_message += f"\nStack Trace:\n{stack_trace}"

    error_logger.error(log_message)

    return error_id


def handle_error(func):
    """
    Decorator for handling errors in request handlers.
    Logs full error details server-side, shows friendly message to user.
    """
    @wraps(func)
    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except AppError as e:
            # Already formatted error
            error_id = log_error(e)
            return {
                "status": "error",
                "error_id": error_id,
                "message": e.user_message,
                "code": e.status_code
            }
        except Exception as e:
            # Unexpected error
            error_id = log_error(e, context={"function": func.__name__})
            return {
                "status": "error",
                "error_id": error_id,
                "message": "An unexpected error occurred. Please contact support.",
                "code": 500
            }

    return wrapper


def safe_operation(func):
    """
    Decorator for database and critical operations.
    Ensures errors are logged and handled gracefully.
    """
    @wraps(func)
    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except AppError:
            raise  # Re-raise app errors
        except Exception as e:
            error_id = log_error(e, context={"operation": func.__name__})
            raise AppError(
                f"Operation {func.__name__} failed",
                error_code=error_id,
                status_code=500,
                user_message="Operation failed. Please try again."
            )

    return wrapper


class ErrorAuditTrail:
    """Track errors for audit and monitoring."""

    @staticmethod
    def log_security_error(event_type, user_id=None, ip_address=None, details=None):
        """
        Log a security-related error event.

        Args:
            event_type: Type of security event
            user_id: User ID (if applicable)
            ip_address: User's IP address
            details: Additional details
        """
        audit_log = {
            "timestamp": datetime.utcnow().isoformat(),
            "event_type": event_type,
            "user_id": user_id,
            "ip_address": ip_address,
            "details": details
        }

        error_logger.warning(f"SECURITY_EVENT: {audit_log}")

    @staticmethod
    def log_data_error(operation, record_type, record_id, error_message):
        """
        Log a data operation error.

        Args:
            operation: Operation type (create, update, delete, read)
            record_type: Type of record affected
            record_id: ID of record affected
            error_message: Error message
        """
        audit_log = {
            "timestamp": datetime.utcnow().isoformat(),
            "operation": operation,
            "record_type": record_type,
            "record_id": record_id,
            "error": error_message
        }

        error_logger.error(f"DATA_ERROR: {audit_log}")
