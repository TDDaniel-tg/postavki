class WBAPIError(Exception):
    """Base exception for WB API errors"""
    pass


class InvalidAPIKeyError(WBAPIError):
    """Invalid API key error"""
    pass


class RateLimitError(WBAPIError):
    """Rate limit exceeded error"""
    pass


class BookingError(WBAPIError):
    """Slot booking error"""
    pass 