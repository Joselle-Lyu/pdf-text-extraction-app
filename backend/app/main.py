import json
import os
import time
import uuid
from typing import Any, Dict, Optional

import jwt
import redis
from fastapi import FastAPI, File, Header, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware

from .auth_github import router as github_router

app = FastAPI()
app.include_router(github_router)

# --- CORS ---
frontend_url = os.getenv("FRONTEND_URL", "http://localhost:5173")
app.add_middleware(
    CORSMiddleware,
    allow_origins=[frontend_url],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- Redis ---
REDIS_URL = os.getenv("REDIS_URL", "redis://redis:6379/0")
r = redis.Redis.from_url(REDIS_URL, decode_responses=True)

JOB_QUEUE_KEY = "queue:jobs"
JOB_KEY_PREFIX = "job:"
UPLOAD_KEY_PREFIX = "upload:"


# --- Auth helpers ---
def _get_jwt_secret() -> str:
    secret = os.getenv("JWT_SECRET", "")
    if not secret:
        raise HTTPException(status_code=500, detail="Missing JWT_SECRET")
    return secret


def get_current_user(authorization: Optional[str]) -> Dict[str, Any]:
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing Bearer token")

    token = authorization.split(" ", 1)[1]
    try:
        payload = jwt.decode(token, _get_jwt_secret(), algorithms=["HS256"])
    except jwt.PyJWTError:
        raise HTTPException(status_code=401, detail="Invalid token")

    return {
        "id": payload.get("sub"),
        "login": payload.get("login"),
        "name": payload.get("name"),
    }


# --- Redis JSON helpers ---
def _set_json(key: str, obj: Dict[str, Any]) -> None:
    r.set(key, json.dumps(obj))


def _get_json(key: str) -> Optional[Dict[str, Any]]:
    val = r.get(key)
    return json.loads(val) if val else None


# --- Upload storage ---
def _uploads_dir() -> str:
    base = os.getenv("DATA_DIR", "/data")
    path = os.path.join(base, "uploads")
    os.makedirs(path, exist_ok=True)
    return path


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/me")
def me(authorization: Optional[str] = Header(default=None)):
    return get_current_user(authorization)


@app.post("/uploads")
async def upload_pdf(
    authorization: Optional[str] = Header(default=None),
    file: UploadFile = File(...),
):
    user = get_current_user(authorization)

    if file.content_type not in ("application/pdf", "application/x-pdf"):
        raise HTTPException(status_code=400, detail="Only PDF files are allowed")

    data = await file.read()
    if len(data) > 20 * 1024 * 1024:
        raise HTTPException(status_code=413, detail="PDF too large (max 20MB for this demo)")

    upload_id = str(uuid.uuid4())
    safe_name = file.filename or "upload.pdf"
    save_path = os.path.join(_uploads_dir(), f"{upload_id}.pdf")

    with open(save_path, "wb") as f:
        f.write(data)

    upload_obj = {
        "id": upload_id,
        "user_id": user["id"],
        "user_login": user["login"],
        "filename": safe_name,
        "path": save_path,
        "size": len(data),
        "created_at": int(time.time()),
    }

    _set_json(f"{UPLOAD_KEY_PREFIX}{upload_id}", upload_obj)

    return {"upload_id": upload_id, "filename": safe_name, "size": len(data)}


@app.post("/jobs")
async def create_job(
    payload: Dict[str, Any],
    authorization: Optional[str] = Header(default=None),
):
    user = get_current_user(authorization)

    upload_id = payload.get("upload_id")
    engine = payload.get("engine")

    if not upload_id:
        raise HTTPException(status_code=400, detail="Invalid upload_id")
    if engine not in ("markitdown", "tesseract", "mineru"):
        raise HTTPException(status_code=400, detail="Invalid engine")

    upload = _get_json(f"{UPLOAD_KEY_PREFIX}{upload_id}")
    if not upload:
        raise HTTPException(status_code=400, detail="Invalid upload_id")
    if upload.get("user_id") != user["id"]:
        raise HTTPException(status_code=403, detail="Not your upload")

    job_id = str(uuid.uuid4())
    job_obj = {
        "id": job_id,
        "upload_id": upload_id,
        "engine": engine,
        "status": "queued",
        "result": None,
        "error": None,
        "created_at": int(time.time()),
        "started_at": None,
        "finished_at": None,
        "user_id": user["id"],
        "user_login": user["login"],
    }

    _set_json(f"{JOB_KEY_PREFIX}{job_id}", job_obj)
    r.rpush(JOB_QUEUE_KEY, job_id)

    return {"job_id": job_id, "status": "queued"}


@app.get("/jobs/{job_id}")
async def get_job(
    job_id: str,
    authorization: Optional[str] = Header(default=None),
):
    user = get_current_user(authorization)

    job = _get_json(f"{JOB_KEY_PREFIX}{job_id}")
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    if job.get("user_id") != user["id"]:
        raise HTTPException(status_code=403, detail="Not your job")

    return {
        "job_id": job.get("id"),
        "upload_id": job.get("upload_id"),
        "engine": job.get("engine"),
        "status": job.get("status"),
        "result": job.get("result"),
        "error": job.get("error"),
        "created_at": job.get("created_at"),
        "started_at": job.get("started_at"),
        "finished_at": job.get("finished_at"),
    }