from typing import Optional
from fastapi import Request

def get_ip(request: Request) -> Optional[str]:
    # Si hay proxy/railway/render, podrías usar x-forwarded-for
    xff = request.headers.get("x-forwarded-for")
    if xff:
        return xff.split(",")[0].strip()
    return request.client.host if request.client else None

def get_user_agent(request: Request) -> Optional[str]:
    return request.headers.get("user-agent")
