"""
Siri-Style Multimodal Desktop Orb
Powered by Cactus Compute (Whistle + Needle 3 + SAPI Voice Synthesis)
- Iconic glowing Siri orb with multi-layer animated gradient ripples
- Voice-reactive waveform animation
- Speaks back with native voice synthesis (TTS)
- Translucent Siri response cards
- Draggable anywhere on screen
"""

import math
import os
import queue
import tempfile
import threading
import time
import tkinter as tk
from typing import Optional

import asyncio
import numpy as np
import sounddevice as sd
import soundfile as sf
import cactus

# Neural Voice Synthesis (Edge-TTS)
try:
    import edge_tts
    HAS_EDGE_TTS = True
except ImportError:
    HAS_EDGE_TTS = False

# Native Windows Speech Synthesis (SAPI fallback)
try:
    import win32com.client
    HAS_TTS = True
except ImportError:
    HAS_TTS = False

from tools import OPERATOR_TOOLS

HALLUCINATED_WORDS = {
    "thank you", "thank you.", "thank you!", "thanks", "thanks.", "thanks!",
    "vielen dank", "vielen dank.", "you", "you.", "bye", "bye.", "okay",
    "hey", "hey.", "hi", "so"
}


class VoiceSynthesizer:
    """High-Fidelity Neural Voice Engine (Edge-TTS) with SAPI fallback & echo suppression."""
    def __init__(self, voice: str = "en-US-JennyNeural"):
        self.voice = voice
        self.is_speaking = False
        self.mute_mic_until = 0.0
        self.temp_dir = tempfile.gettempdir()
        self.sapi_speaker = None
        if HAS_TTS:
            try:
                self.sapi_speaker = win32com.client.Dispatch("SAPI.SpVoice")
                self.sapi_speaker.Rate = 1
            except Exception as e:
                print(f"[TTS] SAPI init warning: {e}")

    def set_voice(self, voice_name: str):
        self.voice = voice_name
        print(f"[TTS] Selected neural voice: {self.voice}")

    def speak(self, text: str, on_done_callback=None):
        if not text:
            return

        def _speak_worker():
            try:
                self.is_speaking = True
                self.mute_mic_until = time.time() + 999.0
                played = False

                # 1. Try High-Fidelity Neural Edge-TTS
                if HAS_EDGE_TTS:
                    try:
                        mp3_path = os.path.join(self.temp_dir, f"siri_{int(time.time()*1000)}.mp3")
                        async def _generate():
                            comm = edge_tts.Communicate(text, self.voice)
                            await comm.save(mp3_path)
                        asyncio.run(_generate())

                        if os.path.exists(mp3_path):
                            audio_data, sr = sf.read(mp3_path)
                            duration = len(audio_data) / float(sr)
                            # Mute mic for exact audio duration + 0.6s echo absorption
                            self.mute_mic_until = time.time() + duration + 0.6
                            sd.play(audio_data, sr)
                            sd.wait()
                            played = True
                            try:
                                os.remove(mp3_path)
                            except Exception:
                                pass
                    except Exception as e:
                        print(f"[TTS] Neural generation fallback: {e}")

                # 2. SAPI Fallback if offline
                if not played and self.sapi_speaker:
                    self.sapi_speaker.Speak(text, 0)

            except Exception as e:
                print(f"[TTS] Speech error: {e}")
            finally:
                self.mute_mic_until = max(self.mute_mic_until, time.time() + 0.6)
                self.is_speaking = False
                if on_done_callback:
                    on_done_callback()

        threading.Thread(target=_speak_worker, daemon=True).start()


class SiriOrbApp:
    def __init__(self, energy_threshold: float = 0.035):
        self.energy_threshold = energy_threshold
        self.is_listening = True
        self.is_recording = False
        self.is_processing = False
        self.audio_queue = queue.Queue()
        self.temp_dir = tempfile.gettempdir()
        
        # Audio energy visualization meter
        self.current_audio_level = 0.0
        self.animation_step = 0.0

        # State: "idle", "listening", "hearing", "thinking", "speaking"
        self.state = "idle"
        
        # Voice Synthesis
        self.tts = VoiceSynthesizer()

        # Needle 3 Agent
        print("[INIT] Loading Needle 3 Agent...")
        self.agent = cactus.Cactus(tools=OPERATOR_TOOLS, stateless=True)

        # Ambient Noise Calibration
        try:
            silence_sample = sd.rec(int(16000 * 0.4), samplerate=16000, channels=1, dtype=np.float32)
            sd.wait()
            ambient_noise = np.sqrt(np.mean(silence_sample**2))
            self.energy_threshold = max(0.026, float(ambient_noise * 2.6))
            print(f"[AUDIO] Siri calibrated ambient noise: {ambient_noise:.4f} -> Dynamic Threshold: {self.energy_threshold:.4f}")
        except Exception as e:
            print(f"[AUDIO] Calibration note: {e}")
            self.energy_threshold = 0.035

        # -------------------------------------------------------------
        # GUI: Frameless Transparent Siri Orb
        # -------------------------------------------------------------
        self.root = tk.Tk()
        self.root.title("Siri Desktop")
        self.root.overrideredirect(True)
        self.root.attributes("-topmost", True)

        self.size = 90  # 90x90 circular orb
        screen_w = self.root.winfo_screenwidth()
        screen_h = self.root.winfo_screenheight()
        x_pos = screen_w - self.size - 50
        y_pos = screen_h - self.size - 80
        self.root.geometry(f"{self.size}x{self.size}+{x_pos}+{y_pos}")

        # Transparency key
        self.trans_color = "#010101"
        self.root.configure(bg=self.trans_color)
        try:
            self.root.attributes("-transparentcolor", self.trans_color)
        except Exception:
            pass

        self.canvas = tk.Canvas(
            self.root,
            width=self.size,
            height=self.size,
            bg=self.trans_color,
            highlightthickness=0
        )
        self.canvas.pack(fill="both", expand=True)

        # Dragging & Clicking
        self.drag_start_x = 0
        self.drag_start_y = 0
        self.canvas.bind("<Button-1>", self.on_drag_start)
        self.canvas.bind("<B1-Motion>", self.on_drag_motion)
        self.canvas.bind("<ButtonRelease-1>", self.on_click_release)
        self.canvas.bind("<Button-3>", self.show_context_menu)

        # Context Menu
        self.menu = tk.Menu(self.root, tearoff=0, bg="#181825", fg="#cdd6f4")
        self.menu.add_command(label="Type Command (Manual)", command=self.prompt_text_command)
        self.menu.add_command(label="Toggle Mic (Mute/Unmute)", command=self.toggle_listening)
        
        # Voice Selection Submenu
        voice_menu = tk.Menu(self.menu, tearoff=0, bg="#181825", fg="#cdd6f4")
        voice_menu.add_command(label="Jenny (Warm Siri US)", command=lambda: self.tts.set_voice("en-US-JennyNeural"))
        voice_menu.add_command(label="Ava (Expressive US)", command=lambda: self.tts.set_voice("en-US-AvaNeural"))
        voice_menu.add_command(label="Sonia (British Siri UK)", command=lambda: self.tts.set_voice("en-GB-SoniaNeural"))
        voice_menu.add_command(label="Guy (Natural Male US)", command=lambda: self.tts.set_voice("en-US-GuyNeural"))
        self.menu.add_cascade(label="Select Neural Voice", menu=voice_menu)

        self.menu.add_separator()
        self.menu.add_command(label="Exit Siri", command=self.shutdown)

        # Active Siri Popover Card
        self.card_window = None

        # Start Background Threads
        self.audio_thread = threading.Thread(target=self.continuous_audio_listener, daemon=True)
        self.worker_thread = threading.Thread(target=self.task_worker, daemon=True)
        self.audio_thread.start()
        self.worker_thread.start()

        # Start Siri Animation Loop
        self.animate_siri_orb()
        self.state = "idle"

        # Welcome Chime
        self.root.after(800, lambda: self.tts.speak("Siri is ready."))

    # -------------------------------------------------------------
    # SIRI GRAPHIC RENDERING: Multi-Wave Fluid Gradient Orb
    # -------------------------------------------------------------
    def draw_siri_orb(self):
        self.canvas.delete("all")
        cx = self.size // 2
        cy = self.size // 2

        # Color palettes matching modern Siri
        # Electric Violet, Neon Cyan, Hot Magenta, Deep Indigo
        color_cyan = "#00f0ff"
        color_magenta = "#ff007f"
        color_purple = "#7928ca"
        color_blue = "#4361ee"

        step = self.animation_step

        if self.state == "hearing":
            # Audio-reactive swelling waveforms
            volume_scale = min(1.8, 1.0 + self.current_audio_level * 18.0)
            base_r = int(22 * volume_scale)
            
            # Outer magenta ripple
            r3 = base_r + int(7 * math.sin(step * 2.0))
            self.canvas.create_oval(cx - r3, cy - r3, cx + r3, cy + r3, fill="", outline=color_magenta, width=3)

            # Mid cyan wave
            r2 = base_r + int(4 * math.cos(step * 2.5))
            self.canvas.create_oval(cx - r2, cy - r2, cx + r2, cy + r2, fill="", outline=color_cyan, width=4)

            # Vibrant inner core
            r1 = max(12, base_r - 4)
            self.canvas.create_oval(cx - r1, cy - r1, cx + r1, cy + r1, fill=color_blue, outline=color_cyan, width=2)

        elif self.state == "thinking":
            # Swirling vortex / spinning satellite arcs
            base_r = 24
            self.canvas.create_oval(cx - base_r, cy - base_r, cx + base_r, cy + base_r, fill="#1e113a", outline=color_purple, width=3)
            
            # 3 orbiting glowing nodes
            for i, col in enumerate([color_cyan, color_magenta, "#ffbe0b"]):
                angle = step * 3.0 + i * (2 * math.pi / 3)
                orbit_r = 22
                nx = cx + int(orbit_r * math.cos(angle))
                ny = cy + int(orbit_r * math.sin(angle))
                self.canvas.create_oval(nx - 5, ny - 5, nx + 5, ny + 5, fill=col, outline="")

        elif self.state == "speaking":
            # Warm pulsating aura
            pulse = math.sin(step * 3.5)
            r = int(24 + 4 * pulse)
            self.canvas.create_oval(cx - r - 6, cy - r - 6, cx + r + 6, cy + r + 6, fill="", outline=color_cyan, width=2)
            self.canvas.create_oval(cx - r, cy - r, cx + r, cy + r, fill=color_purple, outline=color_magenta, width=3)
            self.canvas.create_oval(cx - 10, cy - 10, cx + 10, cy + 10, fill="#ffffff", outline="")

        else:
            # Idle gentle breathing
            pulse = math.sin(step)
            r = int(22 + 2.5 * pulse)

            # Outer subtle glow aura
            self.canvas.create_oval(cx - r - 6, cy - r - 6, cx + r + 6, cy + r + 6, fill="", outline="#2b1055", width=2)
            # Siri gradient simulation (layered circles)
            self.canvas.create_oval(cx - r - 2, cy - r - 2, cx + r + 2, cy + r + 2, fill=color_purple, outline=color_magenta, width=2)
            self.canvas.create_oval(cx - r + 4, cy - r + 4, cx + r - 4, cy + r - 4, fill=color_blue, outline=color_cyan, width=2)
            # Specular highlight
            self.canvas.create_oval(cx - 5, cy - 8, cx + 2, cy - 2, fill="#ffffff", outline="")

    def animate_siri_orb(self):
        self.animation_step += 0.1
        self.draw_siri_orb()
        self.root.after(35, self.animate_siri_orb)

    # -------------------------------------------------------------
    # DRAGGING & INTERACTIONS
    # -------------------------------------------------------------
    def on_drag_start(self, event):
        self.drag_start_x = event.x
        self.drag_start_y = event.y
        self.dragged = False

    def on_drag_motion(self, event):
        self.dragged = True
        dx = event.x - self.drag_start_x
        dy = event.y - self.drag_start_y
        x = self.root.winfo_x() + dx
        y = self.root.winfo_y() + dy
        self.root.geometry(f"+{x}+{y}")
        # Move active popover card with orb
        if self.card_window and self.card_window.winfo_exists():
            self.position_card()

    def on_click_release(self, event):
        if not getattr(self, "dragged", False):
            self.prompt_text_command()

    def show_context_menu(self, event):
        self.menu.post(event.x_root, event.y_root)

    def toggle_listening(self):
        self.is_listening = not self.is_listening
        if self.is_listening:
            self.tts.speak("Listening turned on.")
        else:
            self.tts.speak("Microphone muted.")

    def prompt_text_command(self):
        """Allows clicking the Siri orb to type directly."""
        dialog = tk.Toplevel(self.root)
        dialog.title("Siri Command")
        dialog.attributes("-topmost", True)
        dialog.geometry("350x120")
        dialog.configure(bg="#13111c")

        tk.Label(dialog, text="Ask Siri anything:", bg="#13111c", fg="#a5adcb", font=("Segoe UI", 10, "bold")).pack(pady=8)
        entry = tk.Entry(dialog, width=38, bg="#231f33", fg="#ffffff", insertbackground="#ffffff", font=("Segoe UI", 10))
        entry.pack(pady=4)
        entry.focus_set()

        def submit():
            cmd = entry.get().strip()
            if cmd:
                dialog.destroy()
                self.process_command(cmd)

        entry.bind("<Return>", lambda e: submit())
        tk.Button(dialog, text="Ask", command=submit, bg="#7928ca", fg="#ffffff", font=("Segoe UI", 9, "bold"), relief="flat").pack(pady=8)

    # -------------------------------------------------------------
    # SIRI RESPONSE CARD (POP-IN GLASS BUBBLE)
    # -------------------------------------------------------------
    def position_card(self):
        if not self.card_window or not self.card_window.winfo_exists():
            return
        # Position card to the left of the orb
        orb_x = self.root.winfo_x()
        orb_y = self.root.winfo_y()
        card_w = 320
        card_h = 110
        card_x = max(20, orb_x - card_w - 12)
        card_y = max(20, orb_y - 20)
        self.card_window.geometry(f"{card_w}x{card_h}+{card_x}+{card_y}")

    def show_siri_card(self, user_text: str, reply_text: str):
        if self.card_window and self.card_window.winfo_exists():
            self.card_window.destroy()

        self.card_window = tk.Toplevel(self.root)
        self.card_window.overrideredirect(True)
        self.card_window.attributes("-topmost", True)
        self.card_window.configure(bg="#0b0914")

        self.position_card()

        # Modern Siri Dark Glass Card
        card_frame = tk.Frame(
            self.card_window,
            bg="#181427",
            highlightbackground="#7928ca",
            highlightthickness=1
        )
        card_frame.pack(fill="both", expand=True, padx=2, pady=2)

        # User Query
        tk.Label(
            card_frame,
            text=f"“{user_text}”",
            font=("Segoe UI", 9, "italic"),
            fg="#828bb8",
            bg="#181427",
            anchor="w"
        ).pack(fill="x", padx=12, pady=(8, 2))

        # Siri Answer
        tk.Label(
            card_frame,
            text=reply_text[:160],
            font=("Segoe UI", 10, "bold"),
            fg="#ffffff",
            bg="#181427",
            justify="left",
            wraplength=290,
            anchor="w"
        ).pack(fill="x", padx=12, pady=(0, 8))

        # Auto-fade after 5.5 seconds
        self.root.after(5500, lambda: self.card_window.destroy() if self.card_window and self.card_window.winfo_exists() else None)

    # -------------------------------------------------------------
    # AUDIO LISTENER (Continuous VAD)
    # -------------------------------------------------------------
    def continuous_audio_listener(self):
        sample_rate = 16000
        block_duration = 0.05
        block_size = int(sample_rate * block_duration)
        silence_limit = 1.0
        max_duration = 7.0

        audio_buffer = []
        silence_duration = 0.0

        def audio_callback(indata, frames, time_info, status):
            # ACOUSTIC ECHO SUPPRESSION: If Siri is speaking or in echo cooldown, drop audio completely
            if self.tts.is_speaking or time.time() < self.tts.mute_mic_until or not self.is_listening or self.is_processing:
                if self.is_recording:
                    self.is_recording = False
                    audio_buffer.clear()
                    self.state = "idle"
                return

            rms = float(np.sqrt(np.mean(indata**2)))
            self.current_audio_level = rms

            if not self.is_recording:
                if rms > self.energy_threshold:
                    self.is_recording = True
                    self.state = "hearing"
                    audio_buffer.clear()
                    audio_buffer.append(indata.copy())
            else:
                audio_buffer.append(indata.copy())
                nonlocal silence_duration
                if rms < self.energy_threshold:
                    silence_duration += block_duration
                else:
                    silence_duration = 0.0

                current_len = len(audio_buffer) * block_duration
                if silence_duration >= silence_limit or current_len >= max_duration:
                    self.is_recording = False
                    silence_duration = 0.0
                    self.state = "thinking"

                    recording = np.concatenate(audio_buffer, axis=0)
                    temp_wav = os.path.join(self.temp_dir, f"siri_voice_{int(time.time()*1000)}.wav")
                    sf.write(temp_wav, recording, sample_rate)
                    self.audio_queue.put(temp_wav)

        with sd.InputStream(samplerate=sample_rate, channels=1, dtype=np.float32, blocksize=block_size, callback=audio_callback):
            while True:
                time.sleep(0.08)

    # -------------------------------------------------------------
    # TASK WORKER: WHISTLE -> NEEDLE 3 -> SIRI SPEAKS
    # -------------------------------------------------------------
    def task_worker(self):
        while True:
            audio_path = self.audio_queue.get()
            self.is_processing = True
            try:
                print(f"[WHISTLE] Transcribing speech from {audio_path}...")
                transcript_dict = cactus.transcribe(audio_path)
                query = transcript_dict.get("text", "").strip()
                print(f"[WHISTLE] Heard: \"{query}\"")

                clean_q = query.lower().strip()
                if not clean_q or clean_q in HALLUCINATED_WORDS or len(clean_q) < 4:
                    print(f"[FILTER] Ignored filler/noise: '{query}'")
                    self.state = "idle"
                else:
                    self.process_command(query)
            except Exception as e:
                print(f"[ERROR] Perception pipeline error: {e}")
                self.state = "idle"
            finally:
                if os.path.exists(audio_path):
                    try:
                        os.remove(audio_path)
                    except Exception:
                        pass
                self.is_processing = False
                self.audio_queue.task_done()

    def process_command(self, query: str):
        self.state = "thinking"

        # Clean conversational prefixes like "Hey Siri", "Hey Cactus", "Please"
        target_query = query.strip()
        for prefix in ["hey siri,", "hey siri.", "hey siri", "siri,", "siri.", "siri",
                       "hey cactus,", "hey cactus.", "hey cactus", "hey there,", "hey there.", "hey there", "please"]:
            if target_query.lower().startswith(prefix):
                target_query = target_query[len(prefix):].strip(" ,.")

        if not target_query:
            target_query = query.strip()

        print(f"[NEEDLE 3] Siri resolving intent: '{target_query}' (Raw: '{query}')")
        try:
            res = self.agent.run(target_query)
            results = res.get("results", [])

            # Format speech phrase and card message
            spoken_text = "Done."
            card_text = "Command executed."

            if results and isinstance(results, list):
                first_res = results[0]
                if isinstance(first_res, dict):
                    if "message" in first_res:
                        card_text = first_res["message"]
                        spoken_text = first_res["message"]
                    elif "output" in first_res:
                        card_text = first_res["output"]
                        spoken_text = "Here is the command output."
                    elif "installed" in first_res:
                        tool_n = first_res.get("tool", "tool")
                        is_inst = first_res.get("installed", False)
                        if is_inst:
                            card_text = f"{tool_n} is installed at: {first_res.get('path', '')}"
                            spoken_text = f"{tool_n} is installed on your computer."
                        else:
                            card_text = f"{tool_n} was not found."
                            spoken_text = f"{tool_n} is not installed."
                    else:
                        card_text = str(first_res)
                        spoken_text = "Action completed."
            elif res.get("reasoning"):
                card_text = res["reasoning"]
                spoken_text = "I've handled that."

            # Update UI Card
            self.root.after(0, lambda: self.show_siri_card(query, card_text))

            # Siri speaks reply with callback
            self.state = "speaking"
            self.tts.speak(spoken_text, on_done_callback=lambda: self.root.after(0, self.reset_state))

        except Exception as e:
            err_msg = f"Sorry, I ran into an issue: {e}"
            self.root.after(0, lambda: self.show_siri_card(query, err_msg))
            self.tts.speak("Sorry, I ran into an error.", on_done_callback=lambda: self.root.after(0, self.reset_state))

    def reset_state(self):
        if not self.is_recording and not self.is_processing:
            self.state = "idle"

    def shutdown(self):
        self.is_listening = False
        self.root.destroy()
        os._exit(0)

    def run(self):
        self.root.mainloop()


if __name__ == "__main__":
    print("=" * 60)
    print("🔮 LAUNCHING CACTUS SIRI ORB")
    print("• Iconic glowing multi-wave animated Siri orb")
    print("• SAPI Text-to-Speech voice responses")
    print("• Draggable & always-on-top")
    print("=" * 60)
    app = SiriOrbApp()
    app.run()

