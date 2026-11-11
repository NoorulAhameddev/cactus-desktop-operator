"""
Desktop Operator: Core multimodal perception-action orchestrator
integrating Whistle, Mirage, and Needle 3.
"""

import os
import sys
import tempfile
import time
from typing import Any, Dict, Optional

# Screen capture dependencies
try:
    import mss
    from PIL import Image
    HAS_SCREEN_CAPTURE = True
except ImportError:
    HAS_SCREEN_CAPTURE = False

# Audio recording dependencies
try:
    import sounddevice as sd
    import soundfile as sf
    import numpy as np
    HAS_AUDIO_RECORD = True
except ImportError:
    HAS_AUDIO_RECORD = False

# Cactus SDK
try:
    import cactus
    HAS_CACTUS = True
except ImportError:
    HAS_CACTUS = False

from grounder import ContextGrounder
from tools import OPERATOR_TOOLS, trigger_fallback


class DesktopOperator:
    """
    Multimodal Desktop Agent:
    - Whistle: Listens to voice commands (16.9 MB ASR).
    - Mirage: Captures & inspects current screen frame (22 MB VLM).
    - Needle 3: Routes intent to local tools in ~30 ms (<29 MB Agent).
    """

    def __init__(self, confidence_threshold: float = 0.70, depth: int = 12):
        self.confidence_threshold = confidence_threshold
        self.depth = depth
        self.grounder = ContextGrounder()
        self.temp_dir = tempfile.gettempdir()
        
        print("[INIT] Desktop Operator initialized.")
        if HAS_CACTUS:
            print("[INIT] Cactus SDK loaded. Stateless agent engine initialized.")
        else:
            print("[WARN] 'cactus-compute' is not installed. Running in simulation mode.")

    def capture_screen(self) -> Optional[str]:
        """Captures primary monitor and saves to a lightweight temporary JPEG."""
        if not HAS_SCREEN_CAPTURE:
            return None

        try:
            with mss.mss() as sct:
                monitor = sct.monitors[1]  # Primary display
                screenshot = sct.grab(monitor)
                img = Image.frombytes("RGB", screenshot.size, screenshot.bgra, "raw", "BGRX")
                
                # Downscale to 1280x720 to preserve memory and speed up Mirage
                img.thumbnail((1280, 720))
                target_path = os.path.join(self.temp_dir, "operator_screen_snapshot.jpg")
                img.save(target_path, "JPEG", quality=80)
                return target_path
        except Exception:
            # When running in a headless or background session, BitBlt is unavailable
            return None

    def record_voice(self, duration_sec: int = 4, sample_rate: int = 16000) -> Optional[str]:
        """Records microphone audio as a 16kHz mono WAV file for Whistle."""
        if not HAS_AUDIO_RECORD:
            print("[AUDIO] Audio recording packages (sounddevice/soundfile) not available.")
            return None

        try:
            print(f"[AUDIO] 🎙️ Listening for {duration_sec}s... (Speak command)")
            audio_buffer = sd.rec(
                int(duration_sec * sample_rate),
                samplerate=sample_rate,
                channels=1,
                dtype=np.int16
            )
            sd.wait()
            target_path = os.path.join(self.temp_dir, "operator_audio_clip.wav")
            sf.write(target_path, audio_buffer, sample_rate)
            return target_path
        except Exception as e:
            print(f"[AUDIO] Audio recording error: {e}")
            return None

    def perceive_and_act(self, voice_audio_path: Optional[str] = None, text_override: Optional[str] = None) -> Dict[str, Any]:
        """
        Executes one full perception-action cycle:
        1. Ears: Transcribes speech with Whistle.
        2. Eyes: Inspects screen frame with Mirage and grounds context.
        3. Brain: Dispatches intent with Needle 3 to execute local desktop tools.
        """
        start_time = time.time()

        # ----------------------------------------------------
        # 1. AUDIO PERCEPTION (Whistle)
        # ----------------------------------------------------
        user_intent = ""
        if text_override:
            user_intent = text_override.strip()
            print(f"[INPUT] Direct command provided: \"{user_intent}\"")
        elif voice_audio_path and os.path.exists(voice_audio_path):
            if HAS_CACTUS:
                print("[WHISTLE] Transcribing speech with Whistle...")
                transcription = cactus.transcribe(voice_audio_path, word_timestamps=False)
                user_intent = transcription.get("text", "").strip() if isinstance(transcription, dict) else str(transcription).strip()
            else:
                user_intent = "restart proxy.mjs and run git status"  # Simulation default
            print(f"[WHISTLE] Heard: \"{user_intent}\"")
        else:
            return {"status": "aborted", "reason": "No audio or text input provided."}

        if not user_intent:
            return {"status": "aborted", "reason": "No speech detected."}

        # ----------------------------------------------------
        # 2. VISUAL PERCEPTION (Mirage + Grounder)
        # ----------------------------------------------------
        screen_path = self.capture_screen()
        grounded_context = "[SCENE: desktop_active]"

        if screen_path and os.path.exists(screen_path):
            if HAS_CACTUS:
                print("[MIRAGE] Inspecting screen snapshot...")
                try:
                    mirage = cactus.Mirage()
                    raw_vision = mirage.describe(screen_path)
                    grounded_context = self.grounder.ground_mirage_output(raw_vision)
                except Exception as e:
                    print(f"[MIRAGE] Vision inference note: {e}")
                    grounded_context = "[SCENE: active_code_editor]"
            else:
                grounded_context = "[SCENE: obj_0:powershell_window@top_left obj_1:vscode@mid_center] [OCR: 'proxy.mjs']"
        
        print(f"[GROUNDING] Token-compact context: {grounded_context}")

        # ----------------------------------------------------
        # 3. ACTION DISPATCH (Needle 3)
        # ----------------------------------------------------
        prompt = self.grounder.compose_prompt(user_intent=user_intent, grounded_scene=grounded_context)

        print("[NEEDLE 3] Routing intent with grammar constraints...")
        execution_result = None

        if HAS_CACTUS:
            # Wrap inside context manager to guarantee engram & state reset across turns
            with cactus.Cactus(tools=OPERATOR_TOOLS, stateless=True) as agent:
                response = agent.run(prompt)
                
                # Needle 3 populates response['results'] directly with tool execution outputs
                if response.get("results"):
                    print("[NEEDLE 3] Tool executed successfully.")
                    execution_result = response["results"]
                elif response.get("success") is False:
                    print(f"[SAFETY] Action failed or unmapped. Triggering fallback.")
                    execution_result = trigger_fallback(
                        reason=response.get("error") or "Intent could not be mapped to an executable action",
                        query=user_intent
                    )
                else:
                    execution_result = response.get("reasoning") or response
        else:
            # Deterministic simulation matching Needle's intent mapping
            lower_intent = user_intent.lower()
            if "restart" in lower_intent and "proxy" in lower_intent:
                from tools import restart_process
                execution_result = restart_process("proxy.mjs")
            elif "git" in lower_intent:
                from tools import run_powershell
                execution_result = run_powershell("git status")
            elif "log" in lower_intent:
                from tools import inspect_log
                execution_result = inspect_log("proxy.log", 15)
            else:
                execution_result = trigger_fallback("Intent did not match desktop tools", user_intent)

        elapsed_ms = int((time.time() - start_time) * 1000)
        print(f"[CYCLE COMPLETE] Total turn latency: {elapsed_ms}ms")
        
        return {
            "intent": user_intent,
            "grounding": grounded_context,
            "execution": execution_result,
            "latency_ms": elapsed_ms
        }

