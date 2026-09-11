import requests

ENDPOINT = "https://curiousapis.name.ng/ai_gpt5"

def test(name, text):
    print(f"=== {name} ===")
    r = requests.get(ENDPOINT, params={"query": text}, timeout=30)
    print(r.text)
    print()

# Just the em-dash in a short sentence
test("F: em-dash only", "Say hi — nothing else needed.")

# The exact ANNOUNCE paragraph from the real instructions, standalone
test("G: real ANNOUNCE paragraph", "For ANNOUNCE, the param is 0=all users, 1=buyers only, 2=freelancers only, 3=vendors only — and you MUST add a second line: MESSAGE:<the announcement text, taken from what the admin asked to announce>\n\nAdmin: Hey")
