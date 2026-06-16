from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class ApiError(Exception):
    status_code: int
    code: str
    message: str
    details: dict[str, object] = field(default_factory=dict)

    def to_response(self) -> dict[str, object]:
        return {
            "error": {
                "code": self.code,
                "message": self.message,
                "details": self.details,
            }
        }


def not_found(message: str, *, resource_type: str, **details: object) -> ApiError:
    return ApiError(
        status_code=404,
        code="not_found",
        message=message,
        details={"resource_type": resource_type, **details},
    )


def conflict(message: str, *, resource_type: str, **details: object) -> ApiError:
    return ApiError(
        status_code=409,
        code="conflict",
        message=message,
        details={"resource_type": resource_type, **details},
    )


def bad_request(message: str, *, resource_type: str, **details: object) -> ApiError:
    return ApiError(
        status_code=400,
        code="bad_request",
        message=message,
        details={"resource_type": resource_type, **details},
    )
