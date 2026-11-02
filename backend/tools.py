from typing import Any, cast

from ddgs import DDGS
from ddgs.exceptions import DDGSException

from auth import get_authenticated_client
from embeddings import embed


def search_internal_db(query: str, token: str, top_k: int = 3) -> list[dict[str, Any]]:
    """search internal docs with the match documents rpc.

    token is the caller access token without bearer prefix.
    query runs as that user with rls applied.
    returns matching chunks or empty list on no match or lookup failure.
    """
    try:
        supabase = get_authenticated_client(token)
        query_embedding = embed([query])[0]
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

    # match documents rpc returns row dict list at runtime.
    # cast narrows broad sdk json typing for callers and type checks.
    return cast(list, result.data)


def search_the_web(query: str, top_k=3):
    """search the web with ddgs.

    returns formatted results, or a short message when search fails or has no hits.
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