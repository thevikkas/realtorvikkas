"""Security module for input validation and sanitization.

Provides functions to prevent SQL injection, XSS, and other attacks.
All user inputs must be validated before use.
"""

import re
import html
import logging

security_logger = logging.getLogger("security")

# Constants for validation
MAX_STRING_LENGTH = 5000
MAX_EMAIL_LENGTH = 255
MAX_PHONE_LENGTH = 20
MAX_NAME_LENGTH = 200
MAX_PASSWORD_LENGTH = 128
MAX_TEXT_LENGTH = 10000

# Regex patterns for validation
EMAIL_PATTERN = re.compile(r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$')
PHONE_PATTERN = re.compile(r'^[0-9+\-() ]{10,20}$')
NUMERIC_PATTERN = re.compile(r'^[0-9]+$')


def sanitize_string(value, max_length=MAX_STRING_LENGTH, allow_html=False):
    """
    Sanitize a string input.

    Args:
        value: The input string to sanitize
        max_length: Maximum allowed length
        allow_html: Whether to allow HTML (default: False)

    Returns:
        Sanitized string or raises ValueError if invalid
    """
    if value is None:
        return ""

    if not isinstance(value, str):
        raise ValueError(f"Expected string, got {type(value)}")

    # Strip whitespace
    value = value.strip()

    # Check length
    if len(value) > max_length:
        raise ValueError(f"String exceeds maximum length of {max_length}")

    # Escape HTML if not allowed
    if not allow_html:
        value = html.escape(value)

    # Remove null bytes (potential SQL injection vector)
    if '\x00' in value:
        raise ValueError("Null bytes not allowed")

    return value


def validate_email(email):
    """
    Validate an email address.

    Args:
        email: Email string to validate

    Returns:
        Validated email or raises ValueError
    """
    if not email or len(email) > MAX_EMAIL_LENGTH:
        raise ValueError("Invalid email length")

    email = email.strip().lower()

    if not EMAIL_PATTERN.match(email):
        raise ValueError("Invalid email format")

    return email


def validate_password(password):
    """
    Validate a password.

    Args:
        password: Password string to validate

    Returns:
        Validated password or raises ValueError
    """
    if not password:
        raise ValueError("Password required")

    if len(password) < 8:
        raise ValueError("Password must be at least 8 characters")

    if len(password) > MAX_PASSWORD_LENGTH:
        raise ValueError(f"Password exceeds maximum length of {MAX_PASSWORD_LENGTH}")

    # Require at least one uppercase, one lowercase, one digit
    has_upper = any(c.isupper() for c in password)
    has_lower = any(c.islower() for c in password)
    has_digit = any(c.isdigit() for c in password)

    if not (has_upper and has_lower and has_digit):
        raise ValueError("Password must contain uppercase, lowercase, and digits")

    return password


def validate_phone(phone):
    """
    Validate a phone number.

    Args:
        phone: Phone number string to validate

    Returns:
        Validated phone or raises ValueError
    """
    if not phone:
        return ""

    phone = phone.strip()

    if len(phone) > MAX_PHONE_LENGTH:
        raise ValueError(f"Phone exceeds maximum length of {MAX_PHONE_LENGTH}")

    if not PHONE_PATTERN.match(phone):
        raise ValueError("Invalid phone format")

    return phone


def validate_number(value, min_val=0, max_val=None):
    """
    Validate a numeric value.

    Args:
        value: The value to validate (int, float, or string)
        min_val: Minimum allowed value
        max_val: Maximum allowed value

    Returns:
        Validated number or raises ValueError
    """
    try:
        num = float(value) if isinstance(value, str) else value
        num = int(num)

        if num < min_val:
            raise ValueError(f"Value below minimum of {min_val}")

        if max_val is not None and num > max_val:
            raise ValueError(f"Value exceeds maximum of {max_val}")

        return num
    except (ValueError, TypeError) as e:
        raise ValueError(f"Invalid number: {e}")


def validate_enum(value, allowed_values):
    """
    Validate that a value is one of allowed options.

    Args:
        value: The value to validate
        allowed_values: List of allowed values

    Returns:
        Validated value or raises ValueError
    """
    if value not in allowed_values:
        raise ValueError(f"Value must be one of: {', '.join(allowed_values)}")

    return value


def sanitize_sql_identifier(identifier):
    """
    Sanitize a SQL identifier (table name, column name).

    WARNING: Only use for identifiers, NOT values.
    For values, use parameterized queries with ?.

    Args:
        identifier: The identifier to sanitize

    Returns:
        Validated identifier or raises ValueError
    """
    if not identifier:
        raise ValueError("Identifier required")

    # Only allow alphanumeric and underscore
    if not re.match(r'^[a-zA-Z_][a-zA-Z0-9_]*$', identifier):
        raise ValueError("Invalid identifier format")

    return identifier


def validate_user_input(data, schema):
    """
    Validate user input against a schema.

    Args:
        data: Dictionary of user input
        schema: Dictionary of {field: validation_function}

    Returns:
        Validated data dictionary or raises ValueError
    """
    validated = {}

    for field, validator in schema.items():
        value = data.get(field)

        try:
            validated[field] = validator(value)
        except ValueError as e:
            security_logger.warning(f"Validation failed for field '{field}': {e}")
            raise ValueError(f"Invalid {field}: {e}")

    return validated


def log_security_event(event_type, details, severity="INFO"):
    """
    Log a security event.

    Args:
        event_type: Type of security event (e.g., "INVALID_INPUT", "AUTH_FAILED")
        details: Details about the event
        severity: Log level (INFO, WARNING, ERROR)
    """
    message = f"[{event_type}] {details}"

    if severity == "ERROR":
        security_logger.error(message)
    elif severity == "WARNING":
        security_logger.warning(message)
    else:
        security_logger.info(message)
