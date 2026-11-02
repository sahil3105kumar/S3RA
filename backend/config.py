"""shared backend environment config."""

import os
from pathlib import Path

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

# model is env overrideable so swaps do not need code edits.
# default model supports tool calling used by chat.py.
GROQ_MODEL = os.getenv("GROQ_MODEL", "qwen/qwen3.6-27b")

# frontend origin for cors.
# defaults to local next dev port.
# deployed env must set real frontend url for credentialed requests.
FRONTEND_ORIGIN = os.getenv("FRONTEND_ORIGIN", "http://localhost:3000")

HF_TOKEN = _required_env("HF_TOKEN")

SUPABASE_URL = _required_env("SUPABASE_URL")
SUPABASE_SERVICE_ROLE_KEY = _required_env("SUPABASE_SERVICE_ROLE_KEY", "SUPABASE_KEY")
SUPABASE_KEY = SUPABASE_SERVICE_ROLE_KEY

# public client key.
# used with user jwt for per request rls scoped clients.
# service role key bypasses rls and is for trusted backend work only.
SUPABASE_ANON_KEY = _required_env("SUPABASE_ANON_KEY")