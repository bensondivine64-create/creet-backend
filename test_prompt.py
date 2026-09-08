import requests
from routers_admin import SYSTEM_INSTRUCTIONS

context = (
    "LIVE PLATFORM DATA (use these real numbers when answering questions, never guess):\n"
    "- Total users: 12 (active: 10, suspended: 2)\n"
    "- Total listings: 30\n"
    "- Total reports: 5 (pending: 2)\n"
    "- Maintenance mode: OFF\n"
    "- Announcement banner: inactive\n"
)

convo = ""
prompt = SYSTEM_INSTRUCTIONS + context + "\nConversation so far:\n" + convo + "Admin: Hey"

print("=== FULL PROMPT BEING SENT ===")
print(prompt)
print(f"=== PROMPT LENGTH: {len(prompt)} chars ===")

resp = requests.get("https://curiousapis.name.ng/ai_gpt5", params={"query": prompt}, timeout=30)
print("=== RAW RESPONSE ===")
print(resp.status_code)
print(resp.text)
