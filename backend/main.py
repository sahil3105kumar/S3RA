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

# use one configured frontend origin for cors.
# both chat and upload take auth headers.
# wildcard origins dont work with credentialed requests.
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
    """accept uploads, run ingestion, and store chunks for the caller user id.

    login is required here. we use the caller token for inserts.
    rls still enforces auth uid equals user id on write.
    """
    owner_id = require_user_id(authorization)
    token = get_token(authorization)

    suffix = Path(file.filename or "").suffix.lower()
    if suffix not in SUPPORTED_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported file type '{suffix}'. Supported: {sorted(SUPPORTED_EXTENSIONS)}",
        )

    # ingest works from a file path.
    # write to a temp file, then delete it after ingestion.
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
    """answer a question with the agent tool calling loop.

    auth is optional here. no token means anonymous mode with web search only.
    valid token also enables internal document search for that user.
    """
    user_id = get_user_id(authorization)
    token = get_token(authorization) if user_id else None

    try:
        return run_chat(request.message, user_id=user_id, token=token)
    except Exception as e:
        print(f"chat: request failed for message={request.message!r}: {e}")
        raise HTTPException(status_code=500, detail="Failed to generate a response") from e