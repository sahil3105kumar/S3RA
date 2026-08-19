"""Auth helpers: verify a Supabase-issued access token and extract the user id.

Verification goes through Supabase's own Auth API (`auth.get_user`) rather
than decoding the JWT locally, so there's no separate JWT secret to manage
and token revocation/expiry is handled by Supabase itself.
"""

from supabase import Client, create_client

from config import SUPABASE_ANON_KEY, SUPABASE_KEY, SUPABASE_URL

_auth_client = create_client(SUPABASE_URL, SUPABASE_KEY)


def get_user_id(authorization: str | None) -> str | None:
    """Extract and verify the user id from an `Authorization` header value.

    Returns the user's id (str) if the header carries a valid, non-expired
    Supabase access token. Returns None for anything else -- missing header,
    wrong scheme, empty token, expired/invalid/revoked token, or a network
    error talking to Supabase. Never raises, so callers (route handlers,
    optional-auth endpoints) can treat "no user" uniformly without a
    try/except at every call site.

    `authorization` is the raw header value, e.g. "Bearer eyJhbGciOi...".
    Pass `request.headers.get("authorization")` from a FastAPI route.
    """
    if not authorization:
        return None

    scheme, _, token = authorization.partition(" ")
    if scheme.lower() != "bearer" or not token:
        return None

    try:
        response = _auth_client.auth.get_user(token)
    except Exception as e:
        print(f"get_user_id: token verification failed: {e}")
        return None

    user = getattr(response, "user", None)
    if user is None:
        return None

    return user.id


def require_user_id(authorization: str | None) -> str:
    """Same as get_user_id, but raises FastAPI's 401 for protected routes.

    Use this in route handlers that must have a logged-in user (e.g. chat,
    upload). Use get_user_id directly for routes where auth is optional.
    """
    from fastapi import HTTPException

    user_id = get_user_id(authorization)
    if user_id is None:
        raise HTTPException(status_code=401, detail="Missing or invalid authentication token")
    return user_id


def get_authenticated_client(token: str) -> Client:
    """Build a Supabase client scoped to one user's session, for one request.

    Uses the anon key (safe, no special privileges on its own) plus the
    user's own access token attached on top -- Postgres then sees the
    request as the `authenticated` role with `auth.uid()` resolving to this
    user, so RLS policies apply exactly as written (issue 3/4's decision:
    per-request authenticated client, no service_role, for anything tied to
    a live user request).

    `token` is the bare access token (no "Bearer " prefix) -- callers that
    already have a verified user id from get_user_id/require_user_id should
    reuse the same raw token here rather than re-parsing the header.

    Build a fresh client per request; don't cache/reuse across users.
    """
    client = create_client(SUPABASE_URL, SUPABASE_ANON_KEY)
    client.postgrest.auth(token)
    return client