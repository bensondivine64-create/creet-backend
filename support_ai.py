import requests

CURIOUSAPIS_KEY = "ct_QLyoKynL6dcexZ-nlb2R19i2G-YijX62D8E7Aq0H-Cs"
CHAT_URL = "https://curiousapis.name.ng/ai_chat/"

# Phrases that indicate the underlying model refused to act as CREET Support
# or answered as its default (trading/AIW3) persona instead. If any of these
# show up, we treat the call as failed and fall back to knowledge-base-only
# or escalate — never show an off-topic or refused reply to a real user.
REFUSAL_MARKERS = [
    "AIW3", "on-chain", "backtest", "cannot ignore my role",
    "jailbreak", "derivatives", "memecoin", "Hyperliquid",
]


def ask_support_ai(user_message, context, history_text):
    """
    Returns (reply_text, confident) — confident=False means the caller
    should fall back to knowledge-base-only or escalate rather than show
    this response.
    """
    prompt = (
        "You are CREET Support, answering questions about the CREET marketplace app "
        "(buyers, freelancers, vendors, listings, connections, messaging). "
        "Answer only using the information below. If the information below doesn't "
        "cover the question, say you don't have enough information and offer to "
        "connect the user with a human agent — never guess or make up an answer.\n\n"
        f"CREET knowledge:\n{context}\n\n"
        f"Conversation so far:\n{history_text}\n\n"
        f"User: {user_message}\n"
        "CREET Support:"
    )

    try:
        resp = requests.get(
            CHAT_URL,
            headers={"X-API-Key": CURIOUSAPIS_KEY},
            params={"prompt": prompt},
            timeout=20,
        )
        data = resp.json()
    except Exception:
        return None, False

    if not data.get("status"):
        return None, False

    reply = (data.get("response") or "").strip()
    if not reply:
        return None, False

    lowered = reply.lower()
    for marker in REFUSAL_MARKERS:
        if marker.lower() in lowered:
            return None, False

    return reply, True
