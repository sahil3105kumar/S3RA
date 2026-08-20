import tempfile
from pathlib import Path

from fastapi import FastAPI, Header, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from auth import get_token, get_user_id, require_user_id
from chat import run_chat
from config import FRONTEND_ORIGIN, GROQ_API_KEY, SUPABASE_KEY, SUPABASE_URL
from ingest import ingest_file
from preprocessing.extract import SUPPORTED_EXTENSIONS

app = FastAPI(title="S3RA API")

# No frontend exists yet (Milestone 7), so this is scoped to a single
# configurable origin rather than "*" -- both /chat and /upload accept an
# Authorization header, which makes these credentialed requests, and
# wildcard origins aren't allowed alongside credentials by the CORS spec
# anyway.
app.add_middleware(
    CORSMiddleware,
    allow_origins=[FRONTEND_ORIGIN],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class ChatRequest(BaseModel):
    message: str


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


@app.post("/chat")
async def chat(request: ChatRequest, authorization: str | None = Header(default=None)):
    """Answer a question using the agentic tool-calling loop in chat.py.

    Auth is optional here, unlike /upload: get_user_id (not require_user_id)
    means a missing/invalid token doesn't raise -- it just means the request
    proceeds as anonymous, with web search as the only available tool.
    A valid token additionally makes internal document search available,
    scoped to that user via their own token (see chat.py/tools.py -- no
    service_role involved).
    """
    user_id = get_user_id(authorization)
    token = get_token(authorization) if user_id else None

    try:
        return run_chat(request.message, user_id=user_id, token=token)
    except Exception as e:
        print(f"chat: request failed for message={request.message!r}: {e}")
        raise HTTPException(status_code=500, detail="Failed to generate a response") from e