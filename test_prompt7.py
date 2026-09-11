import requests
from routers_admin import SYSTEM_INSTRUCTIONS

ENDPOINT = "https://curiousapis.name.ng/ai_gpt5"

# Real SYSTEM_INSTRUCTIONS, but strip the trailing "Admin message: " so there's
# only ONE "Admin:" prefix in the whole prompt, matching the working structure.
instructions_fixed = SYSTEM_INSTRUCTIONS.replace("Admin message: ", "").rstrip()

context = (
    "LIVE PLATFORM DATA (use these real numbers when answering questions, never guess):\n"
    "- Total users: 12 (active: 10, suspended: 2)\n"
    "- Total listings: 30\n"
    "- Total reports: 5 (pending: 2)\n"
    "- Maintenance mode: OFF\n"
    "- Announcement banner: inactive"
)

prompt = instructions_fixed + "\n\n" + context + "\n\nAdmin: Hey"

print(f"Length: {len(prompt)}")
r = requests.get(ENDPOINT, params={"query": prompt}, timeout=30)
print(r.text)
