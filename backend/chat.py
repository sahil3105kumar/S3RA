"""Agentic RAG chat pipeline: tool selection -> Groq tool-calling loop ->
postprocessing (groundedness check, confidence thresholding, citations,
per-user ownership check).

Milestone 6. Builds on tools.py's search_internal_db/search_the_web (built
and tested independently in Milestone 3) and auth.py's optional-auth
helpers (Milestone 4/5). main.py's /chat route is a thin wrapper around
run_chat() here, matching the ingest_file()/main.py split from Milestone 5.
"""

import json
import re
from typing import Any, cast

import groq
from groq import Groq

from config import GROQ_API_KEY, GROQ_MODEL
from tools import search_internal_db, search_the_web

_client = Groq(api_key=GROQ_API_KEY)

# Some Groq-hosted models (notably openai/gpt-oss-*, trained on OpenAI's
# "Harmony" format) occasionally reach for a tool baked into their own
# training -- e.g. "open_file" -- instead of one of the tools actually
# offered in this request. Groq validates the tool name server-side and
# hard-rejects the whole completion with a 400 tool_use_failed when this
# happens, rather than returning it as a normal assistant tool-call message
# the loop could otherwise catch and redirect. _INVALID_TOOL_NAME_RE pulls
# the hallucinated name out of that error's message for the corrective
# retry in _run_agentic_loop below.
_INVALID_TOOL_NAME_RE = re.compile(r"attempted to call tool '([^']+)'")

# Hard cap on tool-call round trips per request. Not expected to be hit in
# normal use (most questions resolve in 1-2 tool calls), but without a cap a
# model that keeps calling tools instead of answering would turn one /chat
# request into an unbounded number of Groq calls.
MAX_TOOL_ROUNDS = 5

# Cosine-similarity floor for a retrieved chunk to be treated as actually
# relevant, rather than just "the least-far match we had." match_documents
# returns the closest rows regardless of whether any of them are good
# matches, so this is enforced here, not left to the model to judge from
# the raw scores. 0.5 is a starting point (all-MiniLM-L6-v2 embeddings),
# not a value derived from real query traffic yet -- revisit once there's
# usage data to tune it against.
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
    """Web search is always available; doc search only exists as an option
    for the model when there's a logged-in user_id to scope it to -- an
    anonymous request has no documents to search in the first place.
    """
    tools = [WEB_SEARCH_TOOL]
    if user_id:
        tools.append(DOC_SEARCH_TOOL)
    return tools


def _build_system_prompt(user_id: str | None) -> str:
    """The prompt has to match the tool list exactly -- telling the model
    about a tool it wasn't given (or hiding one it has) causes it to either
    hallucinate a call that will fail or ignore a tool it should use.
    """
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
    """Run one tool call. Returns (content shown to the model, chunks
    retrieved for postprocessing).

    Only search_internal_db populates the chunks list -- citations and the
    groundedness check are scoped to document retrieval, not web search
    (see run_chat's docstring for why).
    """
    if name == "search_the_web":
        return search_the_web(arguments.get("query", "")), []

    if name == "search_internal_db":
        if not token:
            # Shouldn't be reachable -- the tool is only offered when
            # user_id is set, and user_id/token come from the same header --
            # but fail loudly-but-safely rather than crash the request if
            # this invariant is ever violated by a future change.
            return "Document search is unavailable for this request.", []

        raw_chunks = search_internal_db(arguments.get("query", ""), token=token)

        # Confidence thresholding: drop chunks that are simply the nearest
        # thing available, not an actually relevant match. This happens
        # before the model or the citation list ever sees them, so a weak
        # match can't get woven into the answer just because it was
        # top-ranked among bad options.
        confident = [c for c in raw_chunks if c.get("similarity", 0) >= CONFIDENCE_THRESHOLD]

        # Defense-in-depth ownership check on top of RLS (per the README's
        # stated model: RLS is the enforced boundary, this is a redundant
        # second layer, not a substitute for it). match_documents may not
        # return a user_id column at all, so this only ever rejects a chunk
        # when one *is* present and doesn't match -- absence of the field
        # isn't treated as a pass, but it also can't be checked further here.
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
    """If `error` is Groq's tool_use_failed response -- the model called a
    tool name that wasn't in this request's tool list, or sent arguments
    that didn't parse -- return the attempted tool name (or a generic
    placeholder if the message didn't include one) so the caller can feed
    it back to the model as a correction. Returns None for any other kind
    of 400 (a genuinely malformed request, an unrelated validation error,
    etc.), which the caller should let propagate rather than retry.

    `error.body` mirrors the raw JSON error payload on Groq/OpenAI-style
    SDKs (`{"error": {"message": ..., "code": ..., ...}}`); falls back to
    parsing `str(error)` if the SDK version in use doesn't expose `.body`.
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
    """Send -> check tool_calls -> execute -> append -> resend -> repeat,
    until Groq returns a final answer instead of another tool call (or
    MAX_TOOL_ROUNDS is hit). Returns (draft_answer, retrieved_chunks,
    tools_used).
    """
    tools = _build_tools(user_id)
    # Typed as dict[str, Any] rather than Groq's ChatCompletionMessageParam
    # union deliberately -- messages here mix shapes (plain content vs.
    # assistant messages carrying tool_calls vs. tool-role replies), which
    # is exactly what that union expresses, but constructing them as plain
    # dicts and casting at the call site is far more readable than importing
    # and satisfying each individual TypedDict variant by hand. Groq's
    # client (like OpenAI's) accepts plain dicts matching the API shape at
    # runtime regardless of the stub's nominal typing.
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
                # Some other kind of 400 (bad request shape, unsupported
                # param, etc.) -- not something a corrective message can
                # fix, so this is a real failure. Let it propagate to
                # main.py's handler, same as before this fix.
                raise

            # Groq rejects the whole completion server-side when the model
            # (some models, e.g. openai/gpt-oss-*, occasionally reach for a
            # tool baked into their own training instead of one actually
            # offered here) calls a tool that isn't in this request's tool
            # list -- there's no assistant message to append in this case,
            # just a corrective nudge, consuming one of MAX_TOOL_ROUNDS so a
            # model that keeps doing this still can't loop forever.
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

    # Exhausted MAX_TOOL_ROUNDS without a final answer. Ask once more with
    # tools disabled so the model is forced to wrap up with whatever it's
    # gathered so far, instead of the request silently returning nothing.
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
        # No `tools` param is passed on this final call, so a genuine
        # tool-call attempt shouldn't be possible here -- but some models
        # can still emit tool-call-shaped output from their own training
        # even when nothing was offered. There's no more budget left to
        # retry (MAX_TOOL_ROUNDS is already exhausted), so this degrades to
        # a plain apology instead of a 500.
        print(f"_run_agentic_loop: invalid tool call on the final no-tools call, giving up gracefully: {e}")
        return (
            "I wasn't able to put together an answer this time -- could you try rephrasing your question?",
            retrieved_chunks,
            tools_used,
        )
    return response.choices[0].message.content or "", retrieved_chunks, tools_used


def _groundedness_check(
    draft_answer: str, retrieved_chunks: list[dict], tools_used: list[str]
) -> str:
    """Verify the draft answer is actually supported by the retrieved
    document chunks, and soften/strip claims that aren't.

    Scoped to document retrieval only -- web search results are treated as
    already-current by design (that's the point of the tool), so this isn't
    re-litigating web-sourced claims, only doc-sourced ones. A second Groq
    call is used rather than a keyword/substring check, since "is this
    supported" is a semantic judgment a string match can't make reliably.
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
        # Groq models sometimes wrap JSON in a markdown fence despite being
        # told not to -- strip it rather than let json.loads fail on it.
        if raw.startswith("```"):
            raw = raw.strip("`")
            if raw.startswith("json"):
                raw = raw[4:]
            raw = raw.strip()
        revised = json.loads(raw).get("revised_answer")
        if revised:
            return revised
    except Exception as e:
        # A broken verification call shouldn't take the whole answer down
        # with it -- fall back to the ungrounded-checked draft rather than
        # erroring the request over a postprocessing step.
        print(f"_groundedness_check: verification failed, returning draft unchanged: {e}")

    return draft_answer


# Some Groq-hosted models (esp. openai/gpt-oss-*, trained on OpenAI's
# "Harmony"/browsing format) emit citation markers like "【5†L1-L4】" out of
# habit. Nothing in this pipeline produces footnotes for them to resolve
# against, so on the frontend they just show up as literal noise -- strip
# them here rather than teach the frontend to special-case them.
_CITATION_ARTIFACT_RE = re.compile(r"【[^】]*】")

# The model writes LaTeX with \[ \] (display) and \( \) (inline)
# delimiters -- valid LaTeX, but not what the frontend's markdown+math
# renderer (remark-math) looks for, which is $$ $$ and $ $. Converting
# here keeps this a pure output-formatting concern instead of fighting the
# model's prompt to change its LaTeX style.
_LATEX_DISPLAY_RE = re.compile(r"\\\[(.+?)\\\]", re.DOTALL)
_LATEX_INLINE_RE = re.compile(r"\\\((.+?)\\\)", re.DOTALL)


def _postprocess_answer(answer: str) -> str:
    """Clean up raw model output before it's sent to the frontend.

    Runs after the groundedness check, on whatever text is actually going
    out the door, so it catches artifacts regardless of whether they came
    from the original draft or a revised_answer.
    """
    cleaned = _CITATION_ARTIFACT_RE.sub("", answer)
    cleaned = _LATEX_DISPLAY_RE.sub(lambda m: f"\n\n$$\n{m.group(1).strip()}\n$$\n\n", cleaned)
    cleaned = _LATEX_INLINE_RE.sub(lambda m: f"${m.group(1).strip()}$", cleaned)
    # Collapse the blank-line runs the delimiter conversion above can leave
    # behind (e.g. a display equation that already sat on its own line).
    cleaned = re.sub(r"\n{3,}", "\n\n", cleaned)
    return cleaned.strip()


def _build_sources(retrieved_chunks: list[dict]) -> list[dict]:
    """Dedupe retrieved chunks down to distinct (source, page) citations.

    Several chunks can land on the same source/page range (e.g. two
    neighboring chunks both matched); the response only needs to say which
    source/page combinations were actually used, not list every raw chunk.
    """
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
    """Entry point for POST /chat.

    Auth is optional: user_id/token are None together for an anonymous
    caller (web search only) or both set together for a logged-in one
    (both tools) -- they come from the same Authorization header via
    auth.py's get_user_id/get_token, so they can't be set independently.

    Returns the structured shape the route always sends back:
    {"answer": str, "sources": [{"source": str, "page": ...}], "tool_used": [str]}
    """
    draft_answer, retrieved_chunks, tools_used = _run_agentic_loop(message, user_id, token)
    checked_answer = _groundedness_check(draft_answer, retrieved_chunks, tools_used)
    final_answer = _postprocess_answer(checked_answer)

    return {
        "answer": final_answer,
        "sources": _build_sources(retrieved_chunks),
        "tool_used": sorted(set(tools_used)),
    }