import requests
from routers_admin import SYSTEM_INSTRUCTIONS

ENDPOINT = "https://curiousapis.name.ng/ai_gpt5"

context = """LIVE PLATFORM DATA (use these real numbers when answering questions, never guess):
- Total users: 12 (active: 10, suspended: 2)
- Total listings: 30
- Total reports: 5 (pending: 2)
- Maintenance mode: OFF
- Announcement banner: inactive"""

prompt = SYSTEM_INSTRUCTIONS + context + "\nConversation so far:\nAdmin: Hey"

print("SYSTEM_INSTRUCTIONS length:", len(SYSTEM_INSTRUCTIONS))
print("TOTAL prompt length:", len(prompt))
print("===== RESPONSE =====")

r = requests.get(
    ENDPOINT,
    params={"query": prompt},
    timeout=30
)

print(r.text)
