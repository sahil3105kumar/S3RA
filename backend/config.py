"""Shared environment configuration for the backend."""

from pathlib import Path
import os

from dotenv import load_dotenv


_ENV_PATH = Path(__file__).resolve().parent / ".env"
load_dotenv(_ENV_PATH)


def _required_env(*names: str) -> str:
	for name in names:
		value = os.getenv(name)
		if value:
			return value
	raise RuntimeError(f"Missing required environment variable: {' or '.join(names)}")

GROQ_API_KEY = os.getenv("GROQ_API_KEY")

# Overridable via env so we can swap models without a code change (e.g. if a
# Groq-hosted model is deprecated). Defaults to a current Groq-hosted model
# that supports tool calling, which the agentic loop in chat.py depends on.
GROQ_MODEL = os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile")

# Frontend origin for CORS. No frontend exists yet (Milestone 7), so this
# defaults to the conventional local Next.js dev port. Must be set to the
# real deployed frontend URL in Milestone 8 -- CORS does not accept
# wildcard origins alongside credentialed requests, and the Authorization
# header on /chat and /upload makes this a credentialed request.
FRONTEND_ORIGIN = os.getenv("FRONTEND_ORIGIN", "http://localhost:3000")

SUPABASE_URL = _required_env("SUPABASE_URL")
SUPABASE_SERVICE_ROLE_KEY = _required_env("SUPABASE_SERVICE_ROLE_KEY", "SUPABASE_KEY")
SUPABASE_KEY = SUPABASE_SERVICE_ROLE_KEY

# Public/client-safe key. Used (together with a user's own JWT, attached
# per request) to build RLS-scoped Supabase clients -- as opposed to
# SUPABASE_SERVICE_ROLE_KEY, which bypasses RLS entirely and should only
# ever be used for trusted, non-request-bound backend work.
SUPABASE_ANON_KEY = _required_env("SUPABASE_ANON_KEY")