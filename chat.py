"""POST /chat: the GPU Finder assistant, backed by Google Gemini.

The Gemini key stays on the server (GEMINI_API_KEY). Only logged-in accounts
can chat, and shared database counters cap use per account and per day so
the free quota cannot be drained.
"""

import json
import logging
from typing import Literal
from urllib import error, request

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from config import get_settings
from database import RateLimiter, get_rate_limiter
from security import enforce_rate_limit, get_current_user

logger = logging.getLogger("gpu_api.chat")

router = APIRouter(tags=["Assistant"])

GEMINI_URL = "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
GEMINI_TIMEOUT_SECONDS = 25

MESSAGE_MAX = 500
REPLY_MAX = 2000
HISTORY_MAX = 10
PER_USER = (60, 10)                 # 10 messages a minute per account
PER_DAY = (24 * 60 * 60, 500)       # 500 messages a day for the whole site

SYSTEM_PROMPT = (
    "You are GPU Finder Assistant, a concise helper inside a GPU comparison website. "
    "Focus on GPUs, PC graphics, compatibility, VRAM, power requirements, "
    "performance concepts, and helping users understand GPU choices. "
    "Do not invent prices, benchmark numbers, or live stock. "
    "If the user asks for site-specific GPU data that you were not given, tell them "
    "to use the site's Browse or Compare data instead of fabricating values. "
    "Keep normal answers brief and easy to read in a small chat window."
)


class ChatHistoryItem(BaseModel):
    role: Literal["user", "model"]
    text: str = Field(min_length=1, max_length=REPLY_MAX)


class ChatRequest(BaseModel):
    message: str = Field(min_length=1, max_length=MESSAGE_MAX)
    history: list[ChatHistoryItem] = Field(default_factory=list, max_length=HISTORY_MAX)


class ChatReply(BaseModel):
    reply: str


def build_contents(payload: ChatRequest) -> list[dict]:
    """Turn the client's history into Gemini contents.

    History comes from the browser, so it is checked against the shape the
    real website sends: alternating user/model turns, user turns no longer
    than a normal message, and the current message last.
    """
    history = list(payload.history)

    # The website includes the current message as the last history item.
    if history and history[-1].role == "user" and history[-1].text == payload.message:
        history = history[:-1]

    # A trimmed window can start mid-exchange; Gemini needs a user turn first.
    while history and history[0].role == "model":
        history = history[1:]

    contents = []
    expected = "user"
    for item in history:
        if item.role != expected or (item.role == "user" and len(item.text) > MESSAGE_MAX):
            raise HTTPException(status_code=400, detail="Malformed chat history.")
        contents.append({"role": item.role, "parts": [{"text": item.text}]})
        expected = "model" if expected == "user" else "user"

    if expected != "user":
        raise HTTPException(status_code=400, detail="Malformed chat history.")

    contents.append({"role": "user", "parts": [{"text": payload.message}]})
    return contents


def ask_gemini(contents: list[dict]) -> str:
    """Send the conversation to Gemini and return the reply text."""
    settings = get_settings()
    if not settings.gemini_api_key:
        raise HTTPException(status_code=503, detail="The assistant is not configured on the server.")

    body = {
        "systemInstruction": {"parts": [{"text": SYSTEM_PROMPT}]},
        "contents": contents,
        "generationConfig": {"temperature": 0.5, "maxOutputTokens": 350},
    }
    req = request.Request(
        GEMINI_URL.format(model=settings.gemini_model),
        data=json.dumps(body).encode("utf-8"),
        headers={"Content-Type": "application/json", "x-goog-api-key": settings.gemini_api_key},
        method="POST",
    )
    try:
        with request.urlopen(req, timeout=GEMINI_TIMEOUT_SECONDS) as response:
            result = json.loads(response.read().decode("utf-8"))
    except error.HTTPError as exc:
        # Google's message can mention the key or quota; keep it in the log.
        logger.error("Gemini returned HTTP %s", exc.code)
        raise HTTPException(status_code=502, detail="The assistant is unavailable right now.")
    except Exception as exc:
        logger.error("Could not reach Gemini: %s", type(exc).__name__)
        raise HTTPException(status_code=502, detail="The assistant is unavailable right now.")

    try:
        reply = result["candidates"][0]["content"]["parts"][0]["text"].strip()
    except (KeyError, IndexError, TypeError):
        reply = ""
    if not reply:
        raise HTTPException(status_code=502, detail="The assistant returned an empty answer.")
    return reply[:REPLY_MAX]


@router.post("/chat", response_model=ChatReply)
def chat_with_assistant(
    payload: ChatRequest,
    user: dict = Depends(get_current_user),
    limiter: RateLimiter = Depends(get_rate_limiter),
):
    contents = build_contents(payload)
    enforce_rate_limit(
        limiter, f"chat-user:{user['id']}", *PER_USER,
        "Too many messages. Wait a minute and try again.",
    )
    enforce_rate_limit(
        limiter, "chat-day", *PER_DAY,
        "The assistant has reached its daily limit. Try again tomorrow.",
    )
    return {"reply": ask_gemini(contents)}
