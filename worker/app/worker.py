
import json
import os
import time

import redis
from pypdf import PdfReader


REDIS_URL = os.getenv("REDIS_URL", "redis://redis:6379/0")
r = redis.Redis.from_url(REDIS_URL, decode_responses=True)

JOB_QUEUE_KEY = "queue:jobs"
JOB_KEY_PREFIX = "job:"
UPLOAD_KEY_PREFIX = "upload:"


def _get_json(key: str):
    val = r.get(key)
    return json.loads(val) if val else None


def _set_json(key: str, obj):
    r.set(key, json.dumps(obj))


def _extract_text_pypdf(pdf_path: str) -> str:
    reader = PdfReader(pdf_path)
    parts = []
    for page in reader.pages:
        parts.append(page.extract_text() or "")
    return "\n".join(parts).strip()


def process_job(job_id: str) -> None:
    job_key = f"{JOB_KEY_PREFIX}{job_id}"
    job = _get_json(job_key)
    if not job:
        print(f"[worker] job not found: {job_id}")
        return

    job["status"] = "running"
    job["started_at"] = int(time.time())
    job["error"] = None
    _set_json(job_key, job)

    engine = job.get("engine")
    upload = _get_json(f"{UPLOAD_KEY_PREFIX}{job.get('upload_id')}")
    if not upload:
        job["status"] = "failed"
        job["error"] = "Upload not found"
        job["finished_at"] = int(time.time())
        _set_json(job_key, job)
        return

    pdf_path = upload.get("path")
    if not pdf_path or not os.path.exists(pdf_path):
        job["status"] = "failed"
        job["error"] = f"PDF path missing: {pdf_path}"
        job["finished_at"] = int(time.time())
        _set_json(job_key, job)
        return

    try:
        if engine == "markitdown":
            # Real extraction for text-based PDFs
            text = _extract_text_pypdf(pdf_path)
            job["result"] = text if text else "[No extractable text found]"

        elif engine == "mineru":
            # Placeholder: keep async behavior & show where real integration goes
            time.sleep(3)
            job["result"] = (
                "[DEMO] MinerU engine not implemented yet.\n"
                "This placeholder demonstrates async processing via worker + Redis."
            )

        elif engine == "tesseract":
            # Placeholder: OCR would require system deps; keep as demo for now
            time.sleep(6)
            job["result"] = (
                "[DEMO] Tesseract OCR not implemented yet.\n"
                "This placeholder demonstrates async processing via worker + Redis."
            )

        else:
            job["result"] = f"Unknown engine: {engine}"

        job["status"] = "succeeded"
        job["finished_at"] = int(time.time())
        _set_json(job_key, job)

    except Exception as e:
        job["status"] = "failed"
        job["error"] = f"Extraction error: {e}"
        job["finished_at"] = int(time.time())
        _set_json(job_key, job)
        print(f"[worker] error processing {job_id}: {e}")


def main():
    print(f"[worker] starting... REDIS_URL={REDIS_URL}")
    while True:
        # Block until a job is available
        item = r.blpop(JOB_QUEUE_KEY, timeout=0)
        if not item:
            continue
        _, job_id = item
        print(f"[worker] got job: {job_id}")
        process_job(job_id)


if __name__ == "__main__":
    main()