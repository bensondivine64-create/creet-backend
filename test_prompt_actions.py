import requests
from routers_admin import SYSTEM_INSTRUCTIONS

ENDPOINT = "https://curiousapis.name.ng/ai_gpt5"

context = """LIVE PLATFORM DATA (use these real numbers when answering questions, never guess):
- Total users: 12 (active: 10, suspended: 2)
- Total listings: 30
- Total reports: 5 (pending: 2)
- Maintenance mode: OFF
- Announcement banner: inactive"""

commands = [
    "Suspend user 5",
    "Activate user 5",
    "Verify user 5",
    "Unverify user 5",
    "Make user 5 an admin",
    "Remove admin from user 5",
    "Delete listing 12",
    "Resolve report 3",
    "Turn maintenance mode on",
    "Turn maintenance mode off",
]

for command in commands:
    prompt = (
        SYSTEM_INSTRUCTIONS
        + context
        + "\nConversation so far:\n"
        + f"Admin: {command}"
    )

    print(f"\n===== {command} =====")
    print(f"Prompt length: {len(prompt)}")

    try:
        r = requests.get(
            ENDPOINT,
            params={"query": prompt},
            timeout=30
        )
        print(r.text)
    except Exception as e:
        print("ERROR:", e)
