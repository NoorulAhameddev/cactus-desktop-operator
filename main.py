"""
Main Entry Point for Cactus Desktop Operator.
Run interactively via terminal or run automated self-test.
"""

import sys
from desktop_agent import DesktopOperator


def print_banner():
    print("=" * 65)
    print(" 🌵 CACTUS MULTIMODAL DESKTOP OPERATOR")
    print(" [Whistle ~16.9MB] + [Mirage ~22MB] + [Needle 3 ~29MB]")
    print(" 100% Offline Edge Intelligence | < 70MB Total Footprint")
    print("=" * 65)


def run_self_test(operator: DesktopOperator):
    """Verifies screen capture, context grounder, and tool dispatch."""
    print("\n--- RUNNING SELF-TEST DIAGNOSTIC ---")
    
    # 1. Screen capture test
    screen = operator.capture_screen()
    print(f"[TEST 1] Screen capture: {'SUCCESS (' + screen + ')' if screen else 'FAILED / MISSING LIBS'}")

    # 2. Simulated perception-action turn with powershell tool
    print("\n[TEST 2] Testing Tool Execution: 'Show directory files via PowerShell'")
    res = operator.perceive_and_act(text_override="List files in current directory")
    print(f"Result: {res.get('execution')}")

    # 3. Simulated safety fallback test
    print("\n[TEST 3] Testing Safety Fallback: 'Who was Julius Caesar?' (Out of domain)")
    res_fallback = operator.perceive_and_act(text_override="Who was Julius Caesar?")
    print(f"Result: {res_fallback.get('execution')}")
    print("\n--- DIAGNOSTIC COMPLETE ---\n")


def interactive_loop():
    print_banner()
    operator = DesktopOperator()

    print("\nOPTIONS:")
    print("  [v] Voice Command   - Record 4s audio clip (Whistle -> Mirage -> Needle)")
    print("  [t] Text Command    - Type a command manually (Bypasses mic)")
    print("  [d] Diagnostic      - Run automated self-test")
    print("  [q] Quit")

    while True:
        try:
            choice = input("\nSelect [v/t/d/q] > ").strip().lower()
        except (KeyboardInterrupt, EOFError):
            print("\nExiting.")
            break

        if choice == 'q':
            print("Shutting down.")
            break
        elif choice == 'v':
            audio_path = operator.record_voice(duration_sec=4)
            if audio_path:
                operator.perceive_and_act(voice_audio_path=audio_path)
        elif choice == 't':
            cmd_text = input("Enter command: ").strip()
            if cmd_text:
                operator.perceive_and_act(text_override=cmd_text)
        elif choice == 'd':
            run_self_test(operator)
        else:
            print("Invalid option. Enter 'v' for voice, 't' for text, 'd' for diagnostic, or 'q' to quit.")


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--test":
        operator = DesktopOperator()
        run_self_test(operator)
    else:
        interactive_loop()

