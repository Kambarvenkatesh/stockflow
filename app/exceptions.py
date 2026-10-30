class AppError(Exception):
    """Base class for all expected (business) errors."""
    status_code = 400

    def __init__(self, detail: str = "Bad request"):
        self.detail = detail
        super().__init__(detail)


class NotFoundError(AppError):
    status_code = 404


class ConflictError(AppError):
    status_code = 409


class InsufficientStockError(AppError):
    status_code = 409


class UnauthorizedError(AppError):
    status_code = 401


class ForbiddenError(AppError):
    status_code = 403


class BusinessRuleError(AppError):
    status_code = 400


class FileTooLargeError(AppError):
    status_code = 413


class UnsupportedFileTypeError(AppError):
    status_code = 415
