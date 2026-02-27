from datetime import datetime
from enum import Enum
from typing import Generic, Optional, TypeVar

from pydantic import BaseModel

T = TypeVar("T")


class Result(str, Enum):
    SUCCESS = "SUCCESS"
    FAIL = "FAIL"


class SuccessResponse(BaseModel, Generic[T]):
    result: str = Result.SUCCESS
    data: Optional[T] = None
    message: Optional[str] = None


class BasicErrorResponse(BaseModel):
    result: str = Result.FAIL
    errorCode: str
    message: str
    data: Optional[dict] = None
    timestamp: Optional[datetime] = None
    request_id: Optional[str] = None
    path: Optional[str] = None


COMMON_ERROR_RESPONSES: dict[int, dict] = {
    400: {"model": BasicErrorResponse, "description": "Bad Request"},
    401: {"model": BasicErrorResponse, "description": "Unauthorized"},
    403: {"model": BasicErrorResponse, "description": "Forbidden"},
    404: {"model": BasicErrorResponse, "description": "Not Found"},
    422: {
        "model": BasicErrorResponse,
        "description": "Validation Error",
        "content": {
            "application/json": {
                "example": {
                    "result": "FAIL",
                    "errorCode": "VALIDATION_ERROR",
                    "message": "입력값 검증에 실패했습니다",
                    "data": {
                        "errors": [
                            {
                                "field": "body.email",
                                "message": "value is not a valid email address",
                                "type": "value_error",
                            }
                        ]
                    },
                    "timestamp": "2025-01-01T00:00:00+09:00",
                    "request_id": "abc-123",
                    "path": "/api/v1/example",
                }
            }
        },
    },
    500: {"model": BasicErrorResponse, "description": "Internal Server Error"},
}
