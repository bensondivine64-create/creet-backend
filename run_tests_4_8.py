import subprocess
import sys

for name in [
    "test_prompt4.py",
    "test_prompt5.py",
    "test_prompt6.py",
    "test_prompt7.py",
    "test_prompt8.py",
]:
    print("\n" + "=" * 60)
    print(f"===== {name} =====")
    print("=" * 60)

    result = subprocess.run(
        [sys.executable, name],
        capture_output=True,
        text=True
    )

    print(result.stdout)

    if result.stderr:
        print("----- STDERR -----")
        print(result.stderr)
