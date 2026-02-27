from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.openapi.utils import get_openapi
from fastapi.responses import JSONResponse
from loguru import logger

from api.router import api_router
from core.config import settings
from core.database import engine
from core.logging import setup_logging
from exceptions.common import ServiceException
from exceptions.error_codes import HTTP_STATUS_TO_ERROR_CODE, ErrorCode
from middleware.request_id import RequestIDMiddleware
from models.base import Base
from schemas.common import BasicErrorResponse
from util.time_util import now_kst


@asynccontextmanager
async def lifespan(app: FastAPI):
    setup_logging()
    Base.metadata.create_all(bind=engine)
    logger.info("애플리케이션 시작 (ENVIRONMENT={})", settings.ENVIRONMENT)
    yield
    logger.info("애플리케이션 종료")


app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    lifespan=lifespan,
    docs_url="/docs" if settings.is_local else None,
    redoc_url="/redoc" if settings.is_local else None,
)

# ── 미들웨어 ──
app.add_middleware(RequestIDMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── 라우터 ──
app.include_router(api_router)


# ── 예외 핸들러 ──
@app.exception_handler(RequestValidationError)
async def validation_exception_handler(
    request: Request, exc: RequestValidationError
):
    request_id = getattr(request.state, "request_id", None)
    errors = [
        {
            "field": " → ".join(str(loc) for loc in err["loc"]),
            "message": err["msg"],
            "type": err["type"],
        }
        for err in exc.errors()
    ]
    logger.warning(
        "유효성 검사 실패 (request_id={}): {}", request_id, errors
    )
    return JSONResponse(
        status_code=422,
        content=BasicErrorResponse(
            errorCode=ErrorCode.VALIDATION_ERROR,
            message="입력값 검증에 실패했습니다",
            data={"errors": errors},
            timestamp=now_kst(),
            request_id=request_id,
            path=request.url.path,
        ).model_dump(mode="json"),
    )


@app.exception_handler(ServiceException)
async def service_exception_handler(request: Request, exc: ServiceException):
    request_id = getattr(request.state, "request_id", None)
    logger.error(
        "서비스 예외 발생: {} - {} (request_id={})",
        exc.error_code,
        exc.message,
        request_id,
    )
    return JSONResponse(
        status_code=exc.status_code,
        content=BasicErrorResponse(
            errorCode=exc.error_code,
            message=exc.message,
            data=exc.data,
            timestamp=now_kst(),
            request_id=request_id,
            path=request.url.path,
        ).model_dump(mode="json"),
    )


@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    request_id = getattr(request.state, "request_id", None)
    error_code = HTTP_STATUS_TO_ERROR_CODE.get(
        exc.status_code, ErrorCode.INTERNAL_SERVER_ERROR
    )
    message = exc.detail if isinstance(exc.detail, str) else str(exc.detail)
    logger.warning(
        "HTTP 예외 발생: {} - {} (request_id={})",
        error_code,
        message,
        request_id,
    )
    return JSONResponse(
        status_code=exc.status_code,
        content=BasicErrorResponse(
            errorCode=error_code,
            message=message,
            timestamp=now_kst(),
            request_id=request_id,
            path=request.url.path,
        ).model_dump(mode="json"),
    )


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    request_id = getattr(request.state, "request_id", None)
    logger.exception(
        "처리되지 않은 예외 (request_id={}): {}", request_id, str(exc)
    )
    return JSONResponse(
        status_code=500,
        content=BasicErrorResponse(
            errorCode="INTERNAL_SERVER_ERROR",
            message="서버 내부 오류가 발생했습니다",
            timestamp=now_kst(),
            request_id=request_id,
            path=request.url.path,
        ).model_dump(mode="json"),
    )


# ── OpenAPI 스키마 커스터마이징 ──
def custom_openapi():
    if app.openapi_schema:
        return app.openapi_schema

    openapi_schema = get_openapi(
        title=app.title,
        version=app.version,
        routes=app.routes,
    )

    # FastAPI 기본 422 스키마(HTTPValidationError, ValidationError) 제거
    schemas = openapi_schema.get("components", {}).get("schemas", {})
    schemas.pop("HTTPValidationError", None)
    schemas.pop("ValidationError", None)

    # 모든 경로의 422 응답을 BasicErrorResponse로 교체
    for path_item in openapi_schema.get("paths", {}).values():
        for operation in path_item.values():
            if not isinstance(operation, dict):
                continue
            resp_422 = operation.get("responses", {}).get("422")
            if resp_422:
                resp_422["description"] = "Validation Error"
                resp_422["content"] = {
                    "application/json": {
                        "schema": {
                            "$ref": "#/components/schemas/BasicErrorResponse"
                        }
                    }
                }

    app.openapi_schema = openapi_schema
    return app.openapi_schema


app.openapi = custom_openapi
