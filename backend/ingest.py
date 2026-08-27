"""Ingestion pipeline: file -> extract -> clean -> chunk -> embed -> dedupe -> insert.

Supports .txt and .pdf today. Other formats can be added later by extending
preprocessing/extract.py's dispatch.
"""

import os
from pathlib import Path

from auth import get_authenticated_client
from embeddings import MODEL_MAX_SEQ_LENGTH, count_tokens, embed
from preprocessing.chunk import chunk_pages
from preprocessing.clean import clean_pages
from preprocessing.dedupe import filter_near_duplicates
from preprocessing.extract import extract_pages


_SAFETY_MARGIN = 8  # headroom for special tokens + any residual rounding
CHUNK_MAX_TOKENS = max(32, MODEL_MAX_SEQ_LENGTH - _SAFETY_MARGIN)


def ingest_file(path: str, token: str, owner_id: str) -> int:
    """Run the full pipeline for one file and insert the resulting chunks.

    `token` is the uploading user's raw access token (no "Bearer " prefix);
    it's used to build a per-request, RLS-scoped Supabase client so the
    insert runs as that authenticated user rather than via service_role.
    `owner_id` is that same user's id, stamped onto every row's `user_id` --
    it must match `auth.uid()` for the token given, since the
    `authenticated_insert_own` policy checks `auth.uid() = user_id` and will
    reject the insert otherwise.

    This is meant to be called synchronously from the upload endpoint (per
    the decided flow: user waits while OCR + embedding runs, no queue/
    service_role involved), so both `token` and `owner_id` should come
    straight from that same request.
    """
    supabase = get_authenticated_client(token)

    pages = extract_pages(path)
    pages = clean_pages(pages)

    chunks = chunk_pages(
        pages,
        count_tokens=count_tokens,
        max_tokens=CHUNK_MAX_TOKENS,
    )

    if not chunks:
        print(f"No content extracted from {path}; nothing to insert.")
        return 0

    # Verify the packing logic actually held, rather than assuming it did.
    # If this ever fires, chunk.py's budget-checking has a real bug -- it
    # means a chunk reached here already over the limit we asked for.
    oversized = [
        c for c in chunks
        if count_tokens(c.text) > CHUNK_MAX_TOKENS
    ]

    if oversized:
        print(
            f"WARNING: {len(oversized)} chunk(s) exceeded "
            f"{CHUNK_MAX_TOKENS} tokens after chunking "
            f"(max seen: {max(count_tokens(c.text) for c in oversized)}). "
            f"This means chunk.py's budget check has a bug -- please report it."
        )

    texts = [c.text for c in chunks]

    try:
        embeddings = embed(texts)
    except Exception as exc:
        print(f"Embedding generation failed for {path}: {exc}")
        raise RuntimeError(
            "Failed to generate embeddings. "
            "The Hugging Face inference service may be temporarily unavailable."
        ) from exc

    chunks, embeddings = filter_near_duplicates(chunks, embeddings)

    source = os.path.basename(path)
    rows = [
        {
            "content": chunk.text,
            "embedding": embedding,
            "user_id": owner_id,
            "metadata": {
                "source": source,
                "page_start": chunk.page_start,
                "page_end": chunk.page_end,
                "section": chunk.section,
            },
        }
        for chunk, embedding in zip(chunks, embeddings, strict=True)
    ]

    supabase.table("documents").insert(rows).execute()
    print(f"Inserted {len(rows)} chunks from {path}")
    return len(rows)


if __name__ == "__main__":
    # ingest_file now requires a real user token + owner_id (it inserts
    # through a per-request, RLS-scoped client -- there's no service_role
    # fallback). For local testing, log in via the frontend/Supabase and
    # paste that session's access token + user id here as env vars, rather
    # than running this against a fake/empty identity.
    _token = os.environ.get("TEST_USER_TOKEN")
    _owner_id = os.environ.get("TEST_USER_ID")

    if not _token or not _owner_id:
        raise SystemExit(
            "Set TEST_USER_TOKEN and TEST_USER_ID (from a real logged-in "
            "Supabase session) to run this script locally -- ingestion now "
            "goes through RLS, so there's no anonymous/service_role path."
        )

    # Resolve relative to this file's directory so this still works
    # regardless of the caller's cwd, without depending on package-relative
    # import machinery.
    _TEST_FILE = Path(__file__).resolve().parent / "data" / "test.txt"

    ingest_file(
        str(_TEST_FILE),
        token=_token,
        owner_id=_owner_id,
    )