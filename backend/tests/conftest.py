"""Shared test fixtures and import-time environment setup.

Everything at module level here runs before pytest imports any test module,
which matters a lot for this codebase specifically:

- config.py raises RuntimeError at IMPORT time if SUPABASE_URL/
  SUPABASE_ANON_KEY/SUPABASE_SERVICE_ROLE_KEY aren't set -- so those have to
  exist in os.environ before `main` (or anything main imports) is touched.
- tools.py and ingest.py both instantiate a real SentenceTransformer at
  import time (`model = SentenceTransformer("all-MiniLM-L6-v2")`), which
  would otherwise try to download real model weights from Hugging Face on
  every test run. Stubbed out here since these tests exercise the chat/
  route logic, not embedding quality.
- tools.py imports `ddgs`, which isn't installed in the test environment
  (search_the_web is mocked directly in any test that touches it, so the
  real package is never needed).

Both stubs are injected into sys.modules before the real imports happen,
so `from sentence_transformers import SentenceTransformer` and
`from ddgs.exceptions import DDGSException` resolve to these fakes instead
of hitting the network or failing on a missing package.
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

    _fake_st_module.SentenceTransformer = _FakeSentenceTransformer
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

    _fake_ddgs_module.DDGS = _FakeDDGS
    sys.modules["ddgs"] = _fake_ddgs_module

    _fake_ddgs_exceptions_module = ModuleType("ddgs.exceptions")

    class _FakeDDGSException(Exception):
        pass

    _fake_ddgs_exceptions_module.DDGSException = _FakeDDGSException
    sys.modules["ddgs.exceptions"] = _fake_ddgs_exceptions_module


@pytest.fixture
def client():
    """FastAPI TestClient, imported lazily so the sys.modules/env setup
    above always runs first regardless of test collection order."""
    from fastapi.testclient import TestClient

    from main import app

    return TestClient(app)