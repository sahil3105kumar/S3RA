"""agentic rag chat pipeline with tool calling and postprocessing.

includes confidence filtering, groundedness checks, and source shaping.
"""

import json
import re
from typing import Any, cast

import groq
from groq import Groq

from config import GROQ_API_KEY, GROQ_MODEL
from tools import search_internal_db, search_the_web

_client = Groq(api_key=GROQ_API_KEY)

# some models may call tools that were not offered in this request.
# groq rejects that call with tool use failed.
# this regex extracts the invalid name for corrective retry.
_INVALID_TOOL_NAME_RE = re.compile(r"attempted to call tool '([^']+)'")

# hard cap on tool rounds per request to prevent loops.
MAX_TOOL_ROUNDS = 5

# minimum similarity for accepted retrieved chunks.
# threshold is a practical start point and can be tuned later.
CONFIDENCE_THRESHOLD = 0.5

WEB_SEARCH_TOOL: dict[str, Any] = {
    "type": "function",
    "function": {
        "name": "search_the_web",
        "description": (
            "Search the public web for current information. Use this for "
            "anything time-sensitive, general-knowledge, or that would not "
            "plausibly be in the user's own uploaded documents."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "The search query.",
                }
            },
            "required": ["query"],
        },
    },
}

DOC_SEARCH_TOOL: dict[str, Any] = {
    "type": "function",
    "function": {
        "name": "search_internal_db",
        "description": (
            "Search the requesting user's own uploaded documents. Use this "
            "first for any question that could plausibly be answered by "
            "something the user has uploaded, before falling back to the "
            "web."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "The search query.",
                }
            },
            "required": ["query"],
        },
    },
}


def _build_tools(user_id: str | None) -> list[dict[str, Any]]:
    """web search is always available.
    doc search is added only for logged in users.
    """
    tools = [WEB_SEARCH_TOOL]
    if user_id:
        tools.append(DOC_SEARCH_TOOL)
    return tools


def _build_system_prompt(user_id: str | None) -> str:
    """prompt must match the exact tool list for this request."""
    base = (
        "You are S3RA, a retrieval-augmented assistant. Answer using tools "
        "rather than memorized knowledge whenever the question depends on "
        "specific, current, or document-sourced facts -- don't guess at "
        "things a search could confirm. If a tool returns nothing relevant, "
        "say so plainly rather than filling the gap with a guess."
    )
    if user_id:
        return base + (
            " You have two tools: search_internal_db (the user's own "
            "uploaded documents) and search_the_web (public web search). "
            "Try search_internal_db first for anything that could be in the "
            "user's documents, since that's more likely to be exactly what "
            "they're asking about; use search_the_web for anything current "
            "or general-knowledge instead."
        )
    return base + (
        " You have one tool: search_the_web. This user is not logged in, so "
        "there are no documents to search -- don't imply you checked any."
    )


def _execute_tool_call(
    name: str, arguments: dict, user_id: str | None, token: str | None
) -> tuple[str, list[dict]]:
    """run one tool call and return model content plus retrieved chunks.

    only internal doc search returns chunks for later grounding and sources.
    """
    if name == "search_the_web":
        return search_the_web(arguments.get("query", "")), []

    if name == "search_internal_db":
        if not token:
            # this path should not happen, but return safe fallback if it does.
            return "Document search is unavailable for this request.", []

        raw_chunks = search_internal_db(arguments.get("query", ""), token=token)

        # drop low confidence nearest matches before model sees them.
        confident = [c for c in raw_chunks if c.get("similarity", 0) >= CONFIDENCE_THRESHOLD]

        # extra ownership check on top of rls when user id is present.
        owned = [c for c in confident if c.get("user_id") in (None, user_id)]
        if len(owned) != len(confident):
            print(
                f"search_internal_db: dropped {len(confident) - len(owned)} chunk(s) "
                f"with a user_id mismatch for requester {user_id!r} -- should be "
                f"impossible under RLS, not trusted blindly here regardless."
            )

        if not owned:
            return "No sufficiently relevant documents found for this query.", []

        model_facing = "\n\n".join(
            f"[source: {c.get('metadata', {}).get('source', 'unknown')}, "
            f"page {c.get('metadata', {}).get('page_start', '?')}] "
            f"{c.get('content', '')}"
            for c in owned
        )
        return model_facing, owned

    return f"Unknown tool: {name}", []


def _extract_invalid_tool_name(error: groq.BadRequestError) -> str | None:
    """extract invalid tool names from tool use failed errors.

    return none for unrelated bad request errors.
    """
    body = getattr(error, "body", None)
    detail = body.get("error") if isinstance(body, dict) else None
    message = detail.get("message", "") if isinstance(detail, dict) else str(error)
    code = detail.get("code") if isinstance(detail, dict) else None

    if code != "tool_use_failed":
        return None

    match = _INVALID_TOOL_NAME_RE.search(message)
    return match.group(1) if match else "an unavailable tool"


def _run_agentic_loop(
    message: str, user_id: str | None, token: str | None
) -> tuple[str, list[dict], list[str]]:
    """run chat loop until final answer or max tool rounds.

    returns draft answer, retrieved chunks, and tools used.
    """
    tools = _build_tools(user_id)
    # use plain dict message shape and cast at call site.
    messages: list[dict[str, Any]] = [
        {"role": "system", "content": _build_system_prompt(user_id)},
        {"role": "user", "content": message},
    ]

    tools_used: list[str] = []
    retrieved_chunks: list[dict] = []

    for _ in range(MAX_TOOL_ROUNDS):
        try:
            response = _client.chat.completions.create(
                model=GROQ_MODEL,
                messages=cast(Any, messages),
                tools=cast(Any, tools),
                tool_choice="auto",
            )
        except groq.BadRequestError as e:
            bad_tool = _extract_invalid_tool_name(e)
            if bad_tool is None:
                # unrelated bad request errors should propagate.
                raise

            # invalid tool calls get a corrective message and retry.
            print(
                f"_run_agentic_loop: model attempted invalid tool {bad_tool!r}, "
                "retrying with a corrective message"
            )
            valid_names = ", ".join(t["function"]["name"] for t in tools)
            messages.append(
                {
                    "role": "user",
                    "content": (
                        f"The tool '{bad_tool}' does not exist. The only tools "
                        f"available for this request are: {valid_names}. Call "
                        "one of those if you need to, or answer directly if "
                        "you don't."
                    ),
                }
            )
            continue

        msg = response.choices[0].message

        if not msg.tool_calls:
            return msg.content or "", retrieved_chunks, tools_used

        messages.append(
            {
                "role": "assistant",
                "content": msg.content or "",
                "tool_calls": [
                    {
                        "id": tc.id,
                        "type": "function",
                        "function": {
                            "name": tc.function.name,
                            "arguments": tc.function.arguments,
                        },
                    }
                    for tc in msg.tool_calls
                ],
            }
        )

        for tc in msg.tool_calls:
            name = tc.function.name
            try:
                arguments = json.loads(tc.function.arguments or "{}")
            except json.JSONDecodeError:
                arguments = {}

            tools_used.append(name)
            content, chunks = _execute_tool_call(name, arguments, user_id, token)
            retrieved_chunks.extend(chunks)

            messages.append(
                {
                    "role": "tool",
                    "tool_call_id": tc.id,
                    "name": name,
                    "content": content,
                }
            )

    # max rounds reached, request final answer with tools disabled.
    messages.append(
        {
            "role": "user",
            "content": "Give your final answer now, based only on what you've already found.",
        }
    )
    try:
        response = _client.chat.completions.create(model=GROQ_MODEL, messages=cast(Any, messages))
    except groq.BadRequestError as e:
        if _extract_invalid_tool_name(e) is None:
            raise
        # final call has no tools.
        # if model still emits invalid tool behavior, return graceful fallback.
        print(
            "_run_agentic_loop: invalid tool call on the final no-tools call, "
            f"giving up gracefully: {e}"
        )
        return (
            "I wasn't able to put together an answer this time -- could you "
            "try rephrasing your question?",
            retrieved_chunks,
            tools_used,
        )
    return response.choices[0].message.content or "", retrieved_chunks, tools_used


def _groundedness_check(
    draft_answer: str, retrieved_chunks: list[dict], tools_used: list[str]
) -> str:
    """verify draft answer support against retrieved document chunks.

    this runs only when internal document search was used.
    """
    if "search_internal_db" not in tools_used or not retrieved_chunks:
        return draft_answer

    context = "\n\n".join(f"- {c.get('content', '')}" for c in retrieved_chunks)
    verification_prompt = (
        f"Document context:\n{context}\n\n"
        f"Draft answer: {draft_answer}\n\n"
        "Is the draft answer fully supported by the document context above? "
        "Reply with ONLY a JSON object and nothing else: "
        '{"grounded": true or false, "revised_answer": "..."}. '
        "If grounded is false, revised_answer should remove or clearly "
        "qualify any claim the context doesn't support. If grounded is "
        "true, revised_answer should just repeat the draft answer verbatim."
    )

    try:
        response = _client.chat.completions.create(
            model=GROQ_MODEL,
            messages=cast(Any, [{"role": "user", "content": verification_prompt}]),
        )
        raw = (response.choices[0].message.content or "").strip()
        # strip markdown fences if model wraps json output.
        if raw.startswith("```"):
            raw = raw.strip("`")
            if raw.startswith("json"):
                raw = raw[4:]
            raw = raw.strip()
        revised = json.loads(raw).get("revised_answer")
        if revised:
            return revised
    except Exception as e:
        # verification failures should not break the main answer flow.
        print(f"_groundedness_check: verification failed, returning draft unchanged: {e}")

    return draft_answer


# some models emit stray citation markers.
# remove them before sending output to frontend.
_CITATION_ARTIFACT_RE = re.compile(r"【[^】]*】")

# convert latex delimiters to markdown math style for frontend renderer.
_LATEX_DISPLAY_RE = re.compile(r"\\\[(.+?)\\\]", re.DOTALL)
_LATEX_INLINE_RE = re.compile(r"\\\((.+?)\\\)", re.DOTALL)


def _postprocess_answer(answer: str) -> str:
    """clean model output before returning it to frontend."""
    cleaned = _CITATION_ARTIFACT_RE.sub("", answer)
    cleaned = _LATEX_DISPLAY_RE.sub(lambda m: f"\n\n$$\n{m.group(1).strip()}\n$$\n\n", cleaned)
    cleaned = _LATEX_INLINE_RE.sub(lambda m: f"${m.group(1).strip()}$", cleaned)
    # collapse extra blank lines after delimiter conversion.
    cleaned = re.sub(r"\n{3,}", "\n\n", cleaned)
    return cleaned.strip()


def _build_sources(retrieved_chunks: list[dict]) -> list[dict]:
    """dedupe retrieved chunks to distinct source and page citations."""
    seen = set()
    sources = []
    for c in retrieved_chunks:
        metadata = c.get("metadata") or {}
        source = metadata.get("source", "unknown")
        page_start = metadata.get("page_start")
        page_end = metadata.get("page_end")
        page = page_start if page_start == page_end else f"{page_start}-{page_end}"
        key = (source, page)
        if key in seen:
            continue
        seen.add(key)
        sources.append({"source": source, "page": page})
    return sources


def run_chat(message: str, user_id: str | None, token: str | None) -> dict:
    """entry point for chat route.

    auth is optional.
    returns answer, sources, and tools used.
    """
    draft_answer, retrieved_chunks, tools_used = _run_agentic_loop(message, user_id, token)
    checked_answer = _groundedness_check(draft_answer, retrieved_chunks, tools_used)
    final_answer = _postprocess_answer(checked_answer)

    return {
        "answer": final_answer,
        "sources": _build_sources(retrieved_chunks),
        "tool_used": sorted(set(tools_used)),
    }