import cactus
from tools import OPERATOR_TOOLS

prompts = [
    "Run PowerShell: git status",
    "Restart proxy.mjs",
    "Inspect the last 10 lines of README.md",
    "Check if node is installed"
]

print("=== LIVE TEST SUITE: NEEDLE 3 (CACTUS COMPUTE) ===\n")

with cactus.Cactus(tools=OPERATOR_TOOLS, stateless=True) as agent:
    for idx, p in enumerate(prompts, 1):
        print(f"\n[{idx}/4] TESTING PROMPT: \"{p}\"")
        try:
            res = agent.run(p)
            print(f"  Success:     {res.get('success')}")
            print(f"  Confidence:  {res.get('confidence')}")
            print(f"  Reasoning:   {res.get('reasoning')}")
            print(f"  Results:     {res.get('results')}")
        except Exception as e:
            print(f"  CRASHED:     {e}")
        print("-" * 50)

