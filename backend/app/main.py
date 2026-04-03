import logging
import logging.config
import traceback
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, status
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
import uvicorn

from app.routes.routes_cv import router as cv_router
from app.core.config import LOG_LEVEL

# Configure logging
LOG_CONFIG = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "default": {
            "format": "[%(asctime)s] [%(levelname)s] [%(name)s:%(lineno)d] %(message)s",
            "datefmt": "%Y-%m-%d %H:%M:%S",
        },
        "detailed": {
            "format": "[%(asctime)s] [%(process)d] [%(levelname)s] [%(name)s:%(lineno)d] %(funcName)s() - %(message)s",
            "datefmt": "%Y-%m-%d %H:%M:%S",
        },
    },
    "handlers": {
        "default": {
            "formatter": "default",
            "class": "logging.StreamHandler",
            "stream": "ext://sys.stdout",
        },
    },
    "loggers": {
        "app": {"handlers": ["default"], "level": LOG_LEVEL, "propagate": False},
        "uvicorn": {"handlers": ["default"], "level": LOG_LEVEL},
        "uvicorn.access": {"handlers": ["default"], "level": LOG_LEVEL, "propagate": False},
    },
}

logging.config.dictConfig(LOG_CONFIG)
logger = logging.getLogger("app.main")


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("[STARTUP] CV Generation MicroService starting...")
    logger.info("[STARTUP] Logging level: %s", LOG_LEVEL)
    yield
    logger.info("[SHUTDOWN] CV Generation MicroService shutting down...")


app = FastAPI(
    title="CV Generation MicroService",
    description="Microservice to generate CV PDFs and upload to S3 or Google Drive",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
    allow_credentials=True,
)


@app.middleware("http")
async def log_requests(request: Request, call_next):
    """Log all HTTP requests and responses with timing."""
    import time
    
    request_id = request.headers.get("X-Request-ID", "unknown")
    logger.info(
        "[REQUEST] %s %s %s | Request-ID: %s",
        request.method,
        request.url.path,
        request.query_params if request.query_params else "",
        request_id,
    )

    start_time = time.time()
    try:
        response = await call_next(request)
        process_time = time.time() - start_time
        logger.info(
            "[RESPONSE] %s %s | Status: %d | Time: %.3fs | Request-ID: %s",
            request.method,
            request.url.path,
            response.status_code,
            process_time,
            request_id,
        )
        return response
    except Exception as exc:
        process_time = time.time() - start_time
        logger.error(
            "[ERROR] %s %s | Exception: %s | Time: %.3fs | Request-ID: %s\n%s",
            request.method,
            request.url.path,
            type(exc).__name__,
            process_time,
            request_id,
            traceback.format_exc(),
        )
        raise


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """Global exception handler for unhandled errors."""
    request_id = request.headers.get("X-Request-ID", "unknown")
    logger.error(
        "[GLOBAL_ERROR] %s %s | Type: %s | Message: %s | Request-ID: %s\n%s",
        request.method,
        request.url.path,
        type(exc).__name__,
        str(exc),
        request_id,
        traceback.format_exc(),
    )
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={
            "status": "error",
            "code": "INTERNAL_SERVER_ERROR",
            "message": "An unexpected error occurred",
            "request_id": request_id,
        },
    )


app.include_router(cv_router)

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000, log_config=LOG_CONFIG)