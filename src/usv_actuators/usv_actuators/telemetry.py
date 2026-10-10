"""Validate integer values received through the Bridge."""


def bounded_integer(value, minimum, maximum, default=0):
    """Convert a value to an integer and clamp it to the requested range."""
    try:
        if value is None or isinstance(value, bool):
            return default
        return max(minimum, min(maximum, int(value)))
    except (TypeError, ValueError, OverflowError):
        return default
