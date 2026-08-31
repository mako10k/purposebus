class PurposeBusError(Exception):
    """Expected command failure with a stable exit and error identity."""

    def __init__(self, message, *, error="purposebus_error", exit_code=70, hint=None):
        super().__init__(message)
        self.error = error
        self.exit_code = exit_code
        self.hint = hint


class InvalidInput(PurposeBusError):
    def __init__(self, message, *, hint=None):
        super().__init__(message, error="invalid_input", exit_code=2, hint=hint)


class NotFound(PurposeBusError):
    def __init__(self, message, *, hint=None):
        super().__init__(message, error="not_found", exit_code=3, hint=hint)


class NoMessage(PurposeBusError):
    def __init__(self, message="no matching message is available", *, hint=None):
        super().__init__(message, error="no_message", exit_code=4, hint=hint)


class Conflict(PurposeBusError):
    def __init__(self, message, *, hint=None):
        super().__init__(message, error="conflict", exit_code=5, hint=hint)
