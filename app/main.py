import structlog
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.core.config import settings
from app.middleware import LoggingMiddleware
from app.routers.auth import router as auth_router
from app.routers.cart import router as cart_router
from app.routers.favourites import router as favourites_router
from app.routers.menu_items import router as menu_items_router
from app.routers.orders import router as orders_router
from app.routers.profile import router as profile_router
from app.routers.recommendations import router as recommendations_router
from app.routers.restaurants import router as restaurants_router

# Configure structured logging
structlog.configure(
    wrapper_class=structlog.make_filtering_bound_logger(20),
    processors=[
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.add_log_level,
        structlog.dev.ConsoleRenderer(),
    ],
)

logger = structlog.get_logger(__name__)

# API version prefix
API_V1_PREFIX = "/api/v1"

# Initialize FastAPI application
app = FastAPI(
    title=settings.APP_NAME,
    description="Food Ordering Application API",
    version="1.0.0",
    debug=settings.DEBUG,
    docs_url="/docs",
    redoc_url="/redoc",
)

# Add middleware (order matters - first added = outermost)
app.add_middleware(LoggingMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    
    logger.error(
        "unhandled_exception",
        method=request.method,
        path=request.url.path,
        error=str(exc),
        exc_info=True,
    )
    return JSONResponse(
        status_code=500,
        content={"detail": "Internal server error"},
    )


# Register API routers
app.include_router(auth_router, prefix=API_V1_PREFIX)
app.include_router(restaurants_router, prefix=API_V1_PREFIX)
app.include_router(menu_items_router, prefix=API_V1_PREFIX)
app.include_router(cart_router, prefix=API_V1_PREFIX)
app.include_router(orders_router, prefix=API_V1_PREFIX)
app.include_router(profile_router, prefix=API_V1_PREFIX)
app.include_router(favourites_router, prefix=API_V1_PREFIX)
app.include_router(recommendations_router, prefix=API_V1_PREFIX)


@app.get("/health", tags=["health"])
async def health() -> dict[str, str]:
    return {"status": "ok"}
