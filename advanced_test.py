import cactus
from tools import OPERATOR_TOOLS

tests = [
    "Check if git is installed",
    "Run dir in powershell",
    "What is the meaning of life?"
]

print("=== RUNNING ADVANCED TESTS & OUT-OF-SCOPE FALLBACK ===\n")

with cactus.Cactus(tools=OPERATOR_TOOLS, stateless=True) as agent:
    for t in tests:
        print(f"\nPROMPT: \"{t}\"")
        res = agent.run(t)
        print(f"  Confidence: {res.get('confidence')}")
        print(f"  Reasoning:  {res.get('reasoning')}")
        print(f"  Result:     {res.get('results')}")
        print("-" * 50)

