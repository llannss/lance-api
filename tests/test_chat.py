"""POST /chat with Gemini replaced by a stub. Run with:  python -m pytest"""

import io
import json
from urllib import error

import pytest

import chat


class StubGemini:
    """Stands in for urllib.request.urlopen and records what was sent."""

    def __init__(self, reply="RTX 4070 is a good 1440p card."):
        self.reply = reply
        self.sent: list[dict] = []
        self.fail_with: Exception | None = None

    def __call__(self, req, timeout):
        self.sent.append(json.loads(req.data))
        assert req.headers["X-goog-api-key"] == "test-gemini-key"
        if self.fail_with:
            raise self.fail_with
        body = {"candidates": [{"content": {"parts": [{"text": self.reply}]}}]}
        return io.BytesIO(json.dumps(body).encode())


@pytest.fixture
def gemini(monkeypatch) -> StubGemini:
    stub = StubGemini()
    monkeypatch.setenv("GEMINI_API_KEY", "test-gemini-key")
    monkeypatch.setattr(chat.request, "urlopen", stub)
    return stub


def ask(client, message="Which GPU for 1440p?", history=None):
    history = history if history is not None else [{"role": "user", "text": message}]
    return client.post("/chat", json={"message": message, "history": history})


def test_chat_requires_login(anonymous, gemini):
    assert ask(anonymous).status_code == 401
    assert gemini.sent == []


def test_chat_returns_the_reply(client, gemini):
    response = ask(client)
    assert response.status_code == 200
    assert response.json() == {"reply": "RTX 4070 is a good 1440p card."}
    sent = gemini.sent[0]
    assert [c["role"] for c in sent["contents"]] == ["user"]
    assert "GPU Finder Assistant" in sent["systemInstruction"]["parts"][0]["text"]


def test_chat_accepts_a_trimmed_history_window(client, gemini):
    history = [
        {"role": "model", "text": "earlier reply"},
        {"role": "user", "text": "q1"},
        {"role": "model", "text": "a1"},
        {"role": "user", "text": "q2"},
    ]
    assert ask(client, "q2", history).status_code == 200
    assert [c["role"] for c in gemini.sent[0]["contents"]] == ["user", "model", "user"]


@pytest.mark.parametrize("history", [
    [{"role": "user", "text": "a"}, {"role": "user", "text": "b"}],
    [{"role": "user", "text": "x" * 600}, {"role": "model", "text": "ok"}],
    [{"role": "user", "text": "a"}, {"role": "model", "text": "b"}, {"role": "model", "text": "c"}],
])
def test_chat_rejects_tampered_history(client, gemini, history):
    assert ask(client, "next", history).status_code == 400
    assert gemini.sent == []


def test_chat_rejects_oversized_requests(client, gemini):
    assert ask(client, "x" * 501).status_code == 422
    too_long = [{"role": "user", "text": "a"}, {"role": "model", "text": "b"}] * 6
    assert ask(client, "a", too_long).status_code == 422


def test_chat_is_limited_per_account(client, api, gemini):
    api.rate_limit_override["chat-user"] = 2
    assert ask(client).status_code == 200
    assert ask(client).status_code == 200
    third = ask(client)
    assert third.status_code == 429
    assert len(gemini.sent) == 2


def test_chat_has_a_daily_cap_for_the_whole_site(client, api, gemini):
    api.rate_limit_override["chat-day"] = 1
    assert ask(client).status_code == 200
    assert ask(client).json()["detail"] == "The assistant has reached its daily limit. Try again tomorrow."


def test_chat_without_a_gemini_key_returns_503(client, gemini, monkeypatch):
    monkeypatch.delenv("GEMINI_API_KEY")
    response = ask(client)
    assert response.status_code == 503
    assert gemini.sent == []


def test_gemini_errors_do_not_leak_details(client, gemini):
    gemini.fail_with = error.HTTPError(
        "url", 403, "API key test-gemini-key invalid", {}, io.BytesIO(b'{"error":{"message":"key leaked"}}')
    )
    response = ask(client)
    assert response.status_code == 502
    assert "key" not in response.text.lower()
