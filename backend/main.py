import tempfile
from pathlib import Path

from fastapi import FastAPI, Header, HTTPException, UploadFile

from auth import get_token, require_user_id
from config import GROQ_API_KEY, SUPABASE_KEY, SUPABASE_URL
from ingest import ingest_file
from preprocessing.extract import SUPPORTED_EXTENSIONS

app = FastAPI(title="S3RA API")

@app.get("/health")
def health_check():
    return {
        "status": "healthy",
        "groq_configured": bool(GROQ_API_KEY),
        "supabase_configured": bool(SUPABASE_URL and SUPABASE_KEY),
    }


@app.post("/upload")
async def upload(file: UploadFile, authorization: str | None = Header(default=None)):
    """Accept a document upload, run it through the ingestion pipeline, and
    store the resulting chunks tagged with the uploader's user_id.

    Login required: require_user_id raises a clean 401 if the Authorization
    header is missing or the token doesn't verify. Per Milestone 4's
    decision, ingestion runs through a per-request authenticated Supabase
    client (built from the caller's own token) rather than service_role, so
    the same token that authenticates the request is what's used to insert
    the rows -- RLS enforces `auth.uid() = user_id` at write time either way.
    """
    owner_id = require_user_id(authorization)
    token = get_token(authorization)

    suffix = Path(file.filename or "").suffix.lower()
    if suffix not in SUPPORTED_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported file type '{suffix}'. Supported: {sorted(SUPPORTED_EXTENSIONS)}",
        )

    # ingest_file/extract_pages work off a filesystem path, so the upload is
    # spooled to a temp file first and removed once ingestion finishes
    # (success or failure) -- nothing from the upload is left on disk.
    with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
        tmp_path = tmp.name
        contents = await file.read()
        tmp.write(contents)

    try:
        inserted = ingest_file(tmp_path, token=token, owner_id=owner_id)
    except Exception as e:
        print(f"upload: ingestion failed for {file.filename!r}: {e}")
        raise HTTPException(status_code=500, detail="Failed to process the uploaded file") from e
    finally:
        Path(tmp_path).unlink(missing_ok=True)

    return {"filename": file.filename, "chunks_inserted": inserted}