"""shared test fixtures and import time env setup.

module level setup runs before test imports.
this ensures required env vars exist early.
heavy or missing deps are stubbed to keep tests fast and offline.
"""

import os
import sys
from types import ModuleType
from unittest.mock import MagicMock

import pytest

os.environ.setdefault("SUPABASE_URL", "https://test.supabase.co")
os.environ.setdefault("SUPABASE_ANON_KEY", "test-anon-key")
os.environ.setdefault("SUPABASE_SERVICE_ROLE_KEY", "test-service-role-key")
os.environ.setdefault("GROQ_API_KEY", "test-groq-key")
os.environ.setdefault("FRONTEND_ORIGIN", "http://localhost:3000")


if "sentence_transformers" not in sys.modules:
    _fake_st_module = ModuleType("sentence_transformers")

    class _FakeSentenceTransformer:
        def __init__(self, *args, **kwargs):
            self.tokenizer = MagicMock(model_max_length=256)
            self.max_seq_length = 256

        def encode(self, texts, *args, **kwargs):
            return [[0.0] * 384 for _ in texts]

    _fake_st_module.SentenceTransformer = _FakeSentenceTransformer #type:ignore
    sys.modules["sentence_transformers"] = _fake_st_module


if "ddgs" not in sys.modules:
    _fake_ddgs_module = ModuleType("ddgs")

    class _FakeDDGS:
        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def text(self, *args, **kwargs):
            return []

    _fake_ddgs_module.DDGS = _FakeDDGS #type:ignore
    sys.modules["ddgs"] = _fake_ddgs_module

    _fake_ddgs_exceptions_module = ModuleType("ddgs.exceptions")

    class _FakeDDGSException(Exception):
        pass

    _fake_ddgs_exceptions_module.DDGSException = _FakeDDGSException #type:ignore
    sys.modules["ddgs.exceptions"] = _fake_ddgs_exceptions_module


@pytest.fixture
def client():
    """lazy fastapi test client import so setup above runs first."""
    from fastapi.testclient import TestClient

    from main import app

    return TestClient(app)