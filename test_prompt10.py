import requests

ENDPOINT = "https://curiousapis.name.ng/ai_gpt5"

middle_block = """Only when the admin is clearly asking you to perform a specific action, respond with EXACTLY one line FIRST, in this format, then your explanation on the next line:
ACTION:<SUSPEND_USER|ACTIVATE_USER|VERIFY_USER|UNVERIFY_USER|MAKE_ADMIN|REMOVE_ADMIN|DELETE_LISTING|RESOLVE_REPORT|SET_MAINTENANCE|ANNOUNCE>:<param>

For most actions, <param> is the numeric target ID.
For SET_MAINTENANCE, <param> is 1 to turn maintenance mode ON or 0 to turn it OFF.
For ANNOUNCE, <param> is 0=all users, 1=buyers only, 2=freelancers only, 3=vendors only — and you MUST add a second line: MESSAGE:<the announcement text, taken from what the admin asked to announce>

Admin: Hey"""

print(f"Length: {len(middle_block)}")
r = requests.get(ENDPOINT, params={"query": middle_block}, timeout=30)
print(r.text)
