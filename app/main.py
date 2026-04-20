from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request as StarletteRequest
from starlette.responses import Response as StarletteResponse

from app.config import settings
from app.routes import medications, payments, reports, users, whatsapp
from app.security import limiter

app = FastAPI(
    title="Remindam Bot API",
    description="WhatsApp Medication Reminder Bot with Celery backend",
    version="0.1.0",
)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# Register Routers
app.include_router(whatsapp.router)
app.include_router(payments.router)
app.include_router(users.router)
app.include_router(medications.router)
app.include_router(reports.router)

# CORS configuration — restrict to your own domain in production
app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.BASE_URL],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Security Headers Middleware
class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: StarletteRequest, call_next):
        response: StarletteResponse = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["Permissions-Policy"] = (
            "geolocation=(), camera=(), microphone=()"
        )
        return response


app.add_middleware(SecurityHeadersMiddleware)

# Serve Legal Documents
app.mount("/legal", StaticFiles(directory="app/static"), name="legal")


@app.get("/")
async def root():
    return {
        "message": "Welcome to Remindam Bot API",
        "status": "active",
        "version": "0.1.0",
    }


@app.get("/health")
async def health_check():
    return {"status": "healthy"}
