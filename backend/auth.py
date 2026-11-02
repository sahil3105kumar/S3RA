"""auth helpers for token verification and user id extraction.

verification uses supabase auth api instead of local jwt decoding.
"""

from supabase import Client, create_client

from config import SUPABASE_ANON_KEY, SUPABASE_KEY, SUPABASE_URL

_auth_client = create_client(SUPABASE_URL, SUPABASE_KEY)


def get_user_id(authorization: str | None) -> str | None:
    """extract and verify user id from authorization header.

    returns user id for valid token, else none.
    no exceptions are raised, so optional auth flows stay simple.
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


def get_token(authorization: str | None) -> str | None:
    """extract raw bearer token string from authorization header.

    returns token when header is valid, else none.
    """
    if not authorization:
        return None

    scheme, _, token = authorization.partition(" ")
    if scheme.lower() != "bearer" or not token:
        return None

    return token


def require_user_id(authorization: str | None) -> str:
    """same as get user id, but raises 401 for protected routes."""
    from fastapi import HTTPException

    user_id = get_user_id(authorization)
    if user_id is None:
        raise HTTPException(status_code=401, detail="Missing or invalid authentication token")
    return user_id


def get_authenticated_client(token: str) -> Client:
    """build per request supabase client scoped to one user session.

    use anon key plus user token so rls applies for that user.
    """
    client = create_client(SUPABASE_URL, SUPABASE_ANON_KEY)
    client.postgrest.auth(token)
    return client
