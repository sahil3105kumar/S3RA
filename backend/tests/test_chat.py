"""Tests for POST /chat.

Groq is mocked at chat._client (the module-level Groq client instance) so
no real API call is ever made. search_the_web/search_internal_db are
mocked at their chat.py-bound names (chat.py does
`from tools import search_internal_db, search_the_web`, so those are
separate module attributes on `chat`, not on `tools`) so no real DDGS or
Supabase call happens either.
"""

from unittest.mock import MagicMock


class _FakeFunction:
    def __init__(self, name, arguments):
        self.name = name
        self.arguments = arguments


class _FakeToolCall:
    def __init__(self, call_id, name, arguments):
        self.id = call_id
        self.function = _FakeFunction(name, arguments)


class _FakeMessage:
    def __init__(self, content=None, tool_calls=None):
        self.content = content
        self.tool_calls = tool_calls


class _FakeChoice:
    def __init__(self, message):
        self.message = message


class _FakeCompletion:
    def __init__(self, message):
        self.choices = [_FakeChoice(message)]


def test_chat_anonymous_direct_answer_no_tool_call(client, monkeypatch):
    """Model answers without calling any tool -- the simplest path through
    the agentic loop. Also checks that an anonymous request is never even
    offered search_internal_db, per the auth-scoped tool list."""
    import chat as chat_module

    fake_client = MagicMock()
    fake_client.chat.completions.create.return_value = _FakeCompletion(
        _FakeMessage(content="Paris is the capital of France.", tool_calls=None)
    )
    monkeypatch.setattr(chat_module, "_client", fake_client)

    response = client.post("/chat", json={"message": "What is the capital of France?"})

    assert response.status_code == 200
    body = response.json()
    assert body == {
        "answer": "Paris is the capital of France.",
        "sources": [],
        "tool_used": [],
    }

    _, kwargs = fake_client.chat.completions.create.call_args
    offered_tools = [t["function"]["name"] for t in kwargs["tools"]]
    assert offered_tools == ["search_the_web"]


def test_chat_calls_web_search_tool(client, monkeypatch):
    """First Groq response requests a tool call; second returns the final
    answer once the tool result has been fed back in."""
    import chat as chat_module

    tool_call = _FakeToolCall("call_1", "search_the_web", '{"query": "latest AI news"}')
    first_response = _FakeCompletion(_FakeMessage(content=None, tool_calls=[tool_call]))
    second_response = _FakeCompletion(
        _FakeMessage(content="Here's the latest AI news.", tool_calls=None)
    )

    fake_client = MagicMock()
    fake_client.chat.completions.create.side_effect = [first_response, second_response]
    monkeypatch.setattr(chat_module, "_client", fake_client)
    monkeypatch.setattr(
        chat_module, "search_the_web", lambda query: f"Mocked web results for {query!r}"
    )

    response = client.post("/chat", json={"message": "What's new in AI?"})

    assert response.status_code == 200
    body = response.json()
    assert body["answer"] == "Here's the latest AI news."
    assert body["tool_used"] == ["search_the_web"]
    assert body["sources"] == []
    assert fake_client.chat.completions.create.call_count == 2


def test_chat_authenticated_uses_doc_search_with_groundedness(client, monkeypatch):
    """Authenticated request: doc search is offered and used, and the
    groundedness check's revised_answer is what actually goes out."""
    import chat as chat_module
    import main as main_module

    monkeypatch.setattr(main_module, "get_user_id", lambda authorization: "user-123")
    monkeypatch.setattr(main_module, "get_token", lambda authorization: "fake-token")

    chunk = {
        "content": "S3RA uses Groq's llama-3.3-70b-versatile for inference.",
        "similarity": 0.9,
        "user_id": "user-123",
        "metadata": {"source": "notes.pdf", "page_start": 1, "page_end": 1},
    }
    monkeypatch.setattr(chat_module, "search_internal_db", lambda query, token: [chunk])

    tool_call = _FakeToolCall("call_1", "search_internal_db", '{"query": "what llm"}')
    first_response = _FakeCompletion(_FakeMessage(content=None, tool_calls=[tool_call]))
    second_response = _FakeCompletion(
        _FakeMessage(content="S3RA uses Groq.", tool_calls=None)
    )
    groundedness_response = _FakeCompletion(
        _FakeMessage(content='{"grounded": true, "revised_answer": "S3RA uses Groq."}')
    )

    fake_client = MagicMock()
    fake_client.chat.completions.create.side_effect = [
        first_response,
        second_response,
        groundedness_response,
    ]
    monkeypatch.setattr(chat_module, "_client", fake_client)

    response = client.post(
        "/chat",
        json={"message": "What LLM does this project use?"},
        headers={"Authorization": "Bearer whatever"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["answer"] == "S3RA uses Groq."
    assert body["tool_used"] == ["search_internal_db"]
    assert body["sources"] == [{"source": "notes.pdf", "page": 1}]
    assert fake_client.chat.completions.create.call_count == 3


def test_chat_groq_failure_returns_500(client, monkeypatch):
    """An unexpected exception from the Groq client should surface as a
    clean 500 through main.py's handler, not an unhandled crash."""
    import chat as chat_module

    fake_client = MagicMock()
    fake_client.chat.completions.create.side_effect = RuntimeError("Groq is down")
    monkeypatch.setattr(chat_module, "_client", fake_client)

    response = client.post("/chat", json={"message": "hello"})

    assert response.status_code == 500