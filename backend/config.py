"""Shared environment configuration for the backend."""

from pathlib import Path
import os

from dotenv import load_dotenv


_ENV_PATH = Path(__file__).resolve().parents[1] / ".env"
load_dotenv(_ENV_PATH)


def _required_env(*names: str) -> str:
	for name in names:
		value = os.getenv(name)
		if value:
			return value
	raise RuntimeError(f"Missing required environment variable: {' or '.join(names)}")

GROQ_API_KEY = os.getenv("GROQ_API_KEY")
SUPABASE_URL = _required_env("SUPABASE_URL")
SUPABASE_SERVICE_ROLE_KEY = _required_env("SUPABASE_SERVICE_ROLE_KEY", "SUPABASE_KEY")
SUPABASE_KEY = SUPABASE_SERVICE_ROLE_KEY