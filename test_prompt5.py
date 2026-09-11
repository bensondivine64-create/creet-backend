import requests

ENDPOINT = "https://curiousapis.name.ng/ai_gpt5"

def test(name, text):
    print(f"=== {name} (len={len(text)}) ===")
    r = requests.get(ENDPOINT, params={"query": text}, timeout=30)
    print(r.text)
    print()

# Just the opening paragraph
test("A: intro only", """You are CREET's admin assistant, helping the admin manage the platform (users, listings, reports).

If the admin's message is casual conversation, a greeting, a question, or anything that isn't a specific instruction to take action (e.g. "hey", "hi", "how are you", "what can you do", "how many users do we have") just reply naturally and conversationally. Do NOT include any ACTION line for these.

Admin message: Hey""")

# Just the action-format paragraph
test("B: action format only", """Only when the admin is clearly asking you to perform a specific action, respond with EXACTLY one line FIRST, in this format, then your explanation on the next line:
ACTION: SUSPEND_USER, ACTIVATE_USER, or similar, followed by a colon and a param value.

Admin message: Hey""")

# Just the live data block
test("C: live data block only", """LIVE PLATFORM DATA (use these real numbers when answering questions, never guess):
- Total users: 12 (active: 10, suspended: 2)
- Total listings: 30
- Total reports: 5 (pending: 2)
- Maintenance mode: OFF
- Announcement banner: inactive

Conversation so far:
Admin: Hey""")
