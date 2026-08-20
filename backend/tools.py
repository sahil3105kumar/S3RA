from typing import Any, cast

from ddgs import DDGS
from ddgs.exceptions import DDGSException
from sentence_transformers import SentenceTransformer

from auth import get_authenticated_client

model = SentenceTransformer("all-MiniLM-L6-v2")


def search_internal_db(query: str, token: str, top_k: int = 3) -> list[dict[str, Any]]:
    """Search the internal document store via the match_documents RPC.

    `token` is the requesting user's raw access token (no "Bearer " prefix).
    A fresh, per-request client is built from it so this query runs as that
    authenticated user and is subject to RLS -- no service_role client is
    used here, matching the per-request authenticated client decision for
    anything tied to a live user request (`documents` is a shared read pool,
    so RLS lets any authenticated user read all rows; this still ensures
    logged-out/invalid-token callers get nothing, per the `to authenticated`
    policy).

    Returns a list of matching chunks, or an empty list if there's nothing
    relevant or the lookup couldn't be completed (network/DB/auth error).
    Errors are swallowed rather than raised so a down Supabase instance (or
    an expired token) doesn't take the whole agent turn down with it -- the
    caller just sees "no matches".
    """
    try:
        supabase = get_authenticated_client(token)
        query_embedding = model.encode([query])[0].tolist()
        result = supabase.rpc("match_documents", {
            "query_embedding": query_embedding,
            "match_count": top_k
        }).execute()
    except Exception as e:
        print(f"search_internal_db: lookup failed for query={query!r}: {e}")
        return []

    if not result.data:
        print(f"search_internal_db: no matches for query={query!r}")
        return []

    # match_documents is a SETOF-returning RPC, so this is always a list of
    # row dicts at runtime -- postgrest-py's stubs just can't express that
    # generically (RPC responses are typed as the broad JSON union), which
    # is what the cast is narrowing back down for callers/type-checking.
    return cast(list, result.data)


def search_the_web(query: str, top_k=3):
    """Search the web via DDGS.

    Returns a formatted string of results, or a short human-readable message
    if there's nothing found or the search couldn't be completed (network
    error, rate limit, timeout). Kept as a string return (matching the
    success case) so callers don't have to special-case the failure modes.
    """
    try:
        with DDGS() as ddgs:
            results = list(ddgs.text(query, max_results=top_k))
    except DDGSException as e:
        print(f"search_the_web: search failed for query={query!r}: {e}")
        return "Web search is currently unavailable. Please try again later."
    except Exception as e:
        print(f"search_the_web: unexpected error for query={query!r}: {e}")
        return "Web search is currently unavailable. Please try again later."

    if not results:
        print(f"search_the_web: no results for query={query!r}")
        return "No web results found for this query."

    return "\n\n".join(f"{r['title']}: {r['body']}" for r in results)