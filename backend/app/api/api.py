from fastapi import APIRouter
from app.api.endpoints import search_supabase as search
from app.api.endpoints import stats_supabase as stats

api_router = APIRouter()
api_router.include_router(search.router, prefix="/search", tags=["search"])
api_router.include_router(stats.router, prefix="/stats", tags=["stats"])
