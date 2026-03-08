from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from app.core.config import settings
from app.api.api import api_router
from app.middleware.auth import SupabaseAuthMiddleware
import os

app = FastAPI(
    title=settings.PROJECT_NAME,
    openapi_url=f"{settings.API_V1_STR}/openapi.json"
)

# Security Headers Middleware
@app.middleware("http")
async def add_security_headers(request: Request, call_next):
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    # Basic CSP for dev - adjust for prod
    response.headers["Content-Security-Policy"] = (
        "default-src 'self'; "
        "script-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net https://unpkg.com; "
        "style-src 'self' 'unsafe-inline' https://unpkg.com https://fonts.googleapis.com; "
        "img-src 'self' data: https://unpkg.com https://*.tile.openstreetmap.org https://*.basemaps.cartocdn.com; "
        "font-src 'self' https://fonts.gstatic.com data:;"
    )
    response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
    return response

# Set all CORS enabled origins
if settings.BACKEND_CORS_ORIGINS:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[str(origin) for origin in settings.BACKEND_CORS_ORIGINS],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

app.add_middleware(SupabaseAuthMiddleware)

app.include_router(api_router, prefix=settings.API_V1_STR)

@app.get("/health")
def health_check():
    return {"status": "ok"}

@app.get("/diagnostics")
def diagnostics():
    checks = {
        "playwright": False,
        "supabase": False,
        "lxml": False,
        "env_vars": {}
    }
    
    # Check Playwright
    try:
        from playwright.sync_api import sync_playwright
        checks["playwright"] = True
    except ImportError as e:
        checks["playwright_error"] = str(e)
        
    # Check Supabase
    try:
        from app.core.supabase import get_supabase
        client = get_supabase()
        checks["supabase"] = client is not None
    except Exception as e:
        checks["supabase_error"] = str(e)

    # Check lxml
    try:
        import lxml
        checks["lxml"] = True
    except ImportError as e:
        checks["lxml_error"] = str(e)

    # Check Env Vars (safe list)
    safe_vars = ["SUPABASE_URL", "PROJECT_NAME", "API_V1_STR"]
    for var in safe_vars:
        checks["env_vars"][var] = bool(os.getenv(var))
        
    return checks

# Mount static files
static_dir = os.path.join(os.path.dirname(__file__), "static")
if os.path.exists(static_dir):
    app.mount("/static", StaticFiles(directory=static_dir, html=True), name="static")

@app.get("/favicon.ico", include_in_schema=False)
async def favicon():
    file_path = os.path.join(static_dir, "favicon.ico")
    if os.path.exists(file_path):
        return FileResponse(file_path)
    return {"message": "Favicon not found"}

@app.get("/")
def root():
    index_path = os.path.join(static_dir, "index.html")
    if os.path.exists(index_path):
        return FileResponse(index_path)
    return {"message": "Welcome to Reveal API"}
