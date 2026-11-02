"""ingestion pipeline from file to db rows.

current support includes txt and pdf.
"""

import os
from pathlib import Path

from auth import get_authenticated_client
from embeddings import MODEL_MAX_SEQ_LENGTH, count_tokens, embed
from preprocessing.chunk import chunk_pages
from preprocessing.clean import clean_pages
from preprocessing.dedupe import filter_near_duplicates
from preprocessing.extract import extract_pages


_SAFETY_MARGIN = 8  # reserve room for special tokens and rounding drift.
CHUNK_MAX_TOKENS = max(32, MODEL_MAX_SEQ_LENGTH - _SAFETY_MARGIN)


def ingest_file(path: str, token: str, owner_id: str) -> int:
    """run full ingestion for one file and insert generated chunks.

    token is the uploader token without bearer prefix.
    owner id is stamped on rows and must match auth uid under rls policy.
    upload flow is synchronous, so token and owner id come from same request.
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

    # verify chunk token limits were respected.
    # if this fires, chunk budgeting has a real bug.
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
    # ingest file needs a real user token and owner id.
    # use values from a real logged in session for local tests.
    _token = os.environ.get("TEST_USER_TOKEN")
    _owner_id = os.environ.get("TEST_USER_ID")

    if not _token or not _owner_id:
        raise SystemExit(
            "Set TEST_USER_TOKEN and TEST_USER_ID (from a real logged-in "
            "Supabase session) to run this script locally -- ingestion now "
            "goes through RLS, so there's no anonymous/service_role path."
        )

    # resolve test file from this directory, not caller cwd.
    _TEST_FILE = Path(__file__).resolve().parent / "data" / "test.txt"

    ingest_file(
        str(_TEST_FILE),
        token=_token,
        owner_id=_owner_id,
    )