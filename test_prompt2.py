import requests

# Test 1: the exact instructions block alone, no context/history
from routers_admin import SYSTEM_INSTRUCTIONS
resp1 = requests.get("https://curiousapis.name.ng/ai_gpt5", params={"query": SYSTEM_INSTRUCTIONS + "Hey"}, timeout=30)
print("=== TEST 1: instructions + 'Hey' ===")
print(resp1.text)
print()

# Test 2: just the angle-bracket ACTION line syntax in isolation
test2 = "Respond with ACTION:<SUSPEND_USER|ACTIVATE_USER>:<param> if relevant. Otherwise just say hi. Message: Hey"
resp2 = requests.get("https://curiousapis.name.ng/ai_gpt5", params={"query": test2}, timeout=30)
print("=== TEST 2: angle-bracket syntax alone ===")
print(resp2.text)
