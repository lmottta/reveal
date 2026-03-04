from fastapi import Request, status
import requests
import os
from starlette.middleware.base import BaseHTTPMiddleware

SUPABASE_URL = os.environ.get("SUPABASE_URL", "")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY", "")

class SupabaseAuthMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        # Allow public read access on specific endpoints or methods
        if request.method == "GET":
            response = await call_next(request)
            return response

        # For write operations, require authentication
        auth_header = request.headers.get("Authorization")
        if not auth_header:
            return await self._unauthorized_response()

        try:
            token = auth_header.split(" ")[1]
            # Validate token using Supabase Auth API
            # Note: This is a synchronous call in an async function, which is not ideal for performance
            # but acceptable for this migration context. Ideally use httpx or run in threadpool.
            user_response = requests.get(
                f"{SUPABASE_URL}/auth/v1/user",
                headers={"Authorization": f"Bearer {token}", "apikey": SUPABASE_KEY}
            )
            
            if user_response.status_code != 200:
                return await self._unauthorized_response()
            
            user = user_response.json()
            request.state.user = user
        except Exception as e:
            print(f"Auth Error: {e}")
            return await self._unauthorized_response()

        response = await call_next(request)
        return response

    async def _unauthorized_response(self):
        from fastapi.responses import JSONResponse
        return JSONResponse(
            status_code=status.HTTP_401_UNAUTHORIZED,
            content={"detail": "Could not validate credentials"},
            headers={"WWW-Authenticate": "Bearer"},
        )
