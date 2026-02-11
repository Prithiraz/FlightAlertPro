from fastapi import Request, HTTPException
from starlette.middleware.base import BaseHTTPMiddleware
import logging
from rate_limiter import rate_limiter

logger = logging.getLogger(__name__)

class RateLimitMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        if request.url.path.startswith('/api/'):
            user_id = self._get_user_id(request)

            if user_id:
                if not rate_limiter.check_api_rate_limit(user_id):
                    logger.warning(f"Rate limit exceeded for user {user_id}")
                    raise HTTPException(status_code=429, detail="API rate limit exceeded")

        response = await call_next(request)
        return response

    def _get_user_id(self, request: Request) -> str:
        auth_header = request.headers.get('Authorization')
        if auth_header:
            return auth_header.split(' ')[-1][:8]

        api_key = request.headers.get('x-api-key')
        if api_key:
            return api_key[:8]

        return request.client.host
