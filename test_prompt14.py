import requests

ENDPOINT = "https://curiousapis.name.ng/ai_gpt5"

tests = {
    "A: target ID only":
        "For user/listing/report actions use the target ID.",

    "B: maintenance only":
        "SET_MAINTENANCE uses 1 for ON or 0 for OFF.",

    "C: announce only":
        "ANNOUNCE uses 0 for all, 1 for buyers, 2 for freelancers, or 3 for vendors.",

    "D: A+B":
        "For user/listing/report actions use the target ID; SET_MAINTENANCE uses 1 for ON or 0 for OFF.",

    "E: A+C":
        "For user/listing/report actions use the target ID; ANNOUNCE uses 0 for all, 1 for buyers, 2 for freelancers, or 3 for vendors.",

    "F: B+C":
        "SET_MAINTENANCE uses 1 for ON or 0 for OFF; ANNOUNCE uses 0 for all, 1 for buyers, 2 for freelancers, or 3 for vendors.",

    "G: full":
        "For user/listing/report actions use the target ID; SET_MAINTENANCE uses 1 for ON or 0 for OFF; ANNOUNCE uses 0 for all, 1 for buyers, 2 for freelancers, or 3 for vendors.",
}

for name, text in tests.items():
    prompt = text + "\n\nAdmin: Hey"
    print(f"\n===== {name} (len={len(prompt)}) =====")

    try:
        r = requests.get(
            ENDPOINT,
            params={"query": prompt},
            timeout=30
        )
        print(r.text)
    except Exception as e:
        print("ERROR:", e)
