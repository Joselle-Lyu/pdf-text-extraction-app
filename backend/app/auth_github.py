import os
import time
import secrets
from urllib.parse import urlencode

import httpx
import jwt
from fastapi import APIRouter, HTTPException
from fastapi.responses import RedirectResponse

router = APIRouter()

def _env(name: str) -> str:
    v = os.getenv(name)
    if not v:
        raise RuntimeError(f"Missing env var: {name}")
    return v

@router.get("/auth/github/login")
def github_login():
    client_id = _env("GITHUB_CLIENT_ID")
    redirect_uri = _env("GITHUB_REDIRECT_URI")

   
    state = secrets.token_urlsafe(16)

    params = {
        "client_id": client_id,
        "redirect_uri": redirect_uri,
        "scope": "read:user user:email",
        "state": state,
    }
    url = "https://github.com/login/oauth/authorize?" + urlencode(params)
    return RedirectResponse(url)

@router.get("/auth/github/callback")
async def github_callback(code: str | None = None, state: str | None = None):
    if not code:
        raise HTTPException(status_code=400, detail="Missing code")

    client_id = _env("GITHUB_CLIENT_ID")
    client_secret = _env("GITHUB_CLIENT_SECRET")
    frontend_url = _env("FRONTEND_URL")
    jwt_secret = _env("JWT_SECRET")

   
    async with httpx.AsyncClient(timeout=15) as client:
        token_resp = await client.post(
            "https://github.com/login/oauth/access_token",
            headers={"Accept": "application/json"},
            data={
                "client_id": client_id,
                "client_secret": client_secret,
                "code": code,
            },
        )

    token_data = token_resp.json()
    access_token = token_data.get("access_token")
    if not access_token:
        raise HTTPException(status_code=400, detail=f"Token exchange failed: {token_data}")

    
    async with httpx.AsyncClient(timeout=15) as client:
        user_resp = await client.get(
            "https://api.github.com/user",
            headers={
                "Accept": "application/vnd.github+json",
                "Authorization": f"Bearer {access_token}",
            },
        )
    user = user_resp.json()

   
    now = int(time.time())
    payload = {
        "sub": str(user.get("id")),
        "login": user.get("login"),
        "name": user.get("name"),
        "iat": now,
        "exp": now + 60 * 60 * 24 * 7,  # 7天
    }
    token = jwt.encode(payload, jwt_secret, algorithm="HS256")

    
    return RedirectResponse(f"{frontend_url}/?token={token}")