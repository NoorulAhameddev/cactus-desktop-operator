"""
Floating Bubble Desktop Assistant
Always-listening on-device AI orb powered by Cactus Compute (Whistle + Needle 3).
- Always on top
- Draggable anywhere on the screen
- Listens continuously for voice commands
- Dispatches tools locally (PowerShell, file ops, process restarts)
"""

import math
import os
import queue
import tempfile
import threading
import time
import tkinter as tk
from tkinter import messagebox
from typing import Optional

import numpy as np
import sounddevice as sd
import soundfile as sf
import cactus

from tools import OPERATOR_TOOLS


HALLUCINATED_WORDS = {
    "thank you", "thank you.", "thank you!", "thanks", "thanks.", "thanks!",
    "vielen dank", "vielen dank.", "you", "you.", "bye", "bye.", "okay",
    "hey", "hey.", "hi", "so"
}


class FloatingBubbleApp:
    def __init__(self, energy_threshold: float = 0.035):
        self.energy_threshold = energy_threshold
        self.is_listening = True
        self.is_recording = False
        self.is_processing = False
        self.audio_queue = queue.Queue()
        self.temp_dir = tempfile.gettempdir()
        self.status_text = "Calibrating..."
        self.status_color = "#f9e2af"
        self.pulse_phase = 0.0

        # Needle 3 Agent
        print("[INIT] Loading Needle 3 Agent...")
        self.agent = cactus.Cactus(tools=OPERATOR_TOOLS, stateless=True)

        # Calibrate ambient room noise
        try:
            silence_sample = sd.rec(int(16000 * 0.4), samplerate=16000, channels=1, dtype=np.float32)
            sd.wait()
            ambient_noise = np.sqrt(np.mean(silence_sample**2))
            self.energy_threshold = max(0.028, float(ambient_noise * 2.8))
            print(f"[AUDIO] Calibrated ambient noise: {ambient_noise:.4f} -> Dynamic Threshold: {self.energy_threshold:.4f}")
        except Exception as e:
            print(f"[AUDIO] Ambient calibration note: {e}")
            self.energy_threshold = 0.035

        self.status_text = "Listening"
        self.status_color = "#00f5d4"

        # Build GUI
        self.root = tk.Tk()
        self.root.title("Cactus AI Orb")
        self.root.overrideredirect(True)  # Frameless
        self.root.attributes("-topmost", True)  # Always on top

        # Position at bottom-right of screen by default
        screen_w = self.root.winfo_screenwidth()
        screen_h = self.root.winfo_screenheight()
        self.width = 220
        self.height = 56
        x_pos = screen_w - self.width - 40
        y_pos = screen_h - self.height - 80
        self.root.geometry(f"{self.width}x{self.height}+{x_pos}+{y_pos}")

        # Set transparent or sleek dark background
        bg_color = "#181825"
        self.root.configure(bg=bg_color)
        try:
            self.root.attributes("-transparentcolor", bg_color)
        except Exception:
            pass  # Fallback for platforms that don't support transparentcolor

        # Canvas for drawing pill / glowing orb
        self.canvas = tk.Canvas(
            self.root,
            width=self.width,
            height=self.height,
            bg=bg_color,
            highlightthickness=0
        )
        self.canvas.pack(fill="both", expand=True)

        # Dragging support
        self.drag_start_x = 0
        self.drag_start_y = 0
        self.canvas.bind("<Button-1>", self.on_drag_start)
        self.canvas.bind("<B1-Motion>", self.on_drag_motion)
        self.canvas.bind("<ButtonRelease-1>", self.on_click_release)
        self.canvas.bind("<Button-3>", self.show_context_menu)

        # Context Menu
        self.menu = tk.Menu(self.root, tearoff=0, bg="#1e1e2e", fg="#cdd6f4")
        self.menu.add_command(label="Toggle Always-Listening", command=self.toggle_listening)
        self.menu.add_command(label="Type Command (Manual)", command=self.prompt_text_command)
        self.menu.add_separator()
        self.menu.add_command(label="Exit", command=self.shutdown)

        # Toast notification window for results
        self.toast_window = None

        # Start background threads
        self.stream = None
        self.audio_thread = threading.Thread(target=self.continuous_audio_listener, daemon=True)
        self.worker_thread = threading.Thread(target=self.task_worker, daemon=True)
        self.audio_thread.start()
        self.worker_thread.start()

        # UI Animation timer
        self.animate_ui()

    def draw_bubble(self):
        """Draws a sleek modern glassmorphism pill with glowing indicator."""
        self.canvas.delete("all")
        w, h = self.width, self.height
        r = h // 2

        # Draw outer rounded pill
        pill_fill = "#1e1e2e"
        border_color = self.status_color
        
        # Pill background
        self.canvas.create_oval(2, 2, h-2, h-2, fill=pill_fill, outline=border_color, width=2)
        self.canvas.create_oval(w-h+2, 2, w-2, h-2, fill=pill_fill, outline=border_color, width=2)
        self.canvas.create_rectangle(r, 2, w-r, h-2, fill=pill_fill, outline=border_color, width=2)
        # Fill center seam
        self.canvas.create_rectangle(r, 3, w-r, h-3, fill=pill_fill, outline="")

        # Pulsing Glowing Orb on the left
        glow_size = int(6 + 2 * math.sin(self.pulse_phase))
        cx = r
        cy = r
        self.canvas.create_oval(
            cx - glow_size, cy - glow_size,
            cx + glow_size, cy + glow_size,
            fill=self.status_color, outline=""
        )

        # Status text
        self.canvas.create_text(
            cx + 20, cy,
            text=self.status_text,
            fill="#ffffff",
            font=("Segoe UI", 10, "bold"),
            anchor="w"
        )

    def animate_ui(self):
        """Updates pulsing animations."""
        self.pulse_phase += 0.25
        self.draw_bubble()
        self.root.after(50, self.animate_ui)

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

    def on_click_release(self, event):
        if not getattr(self, "dragged", False):
            # Clicked without dragging -> manual trigger
            self.prompt_text_command()

    def show_context_menu(self, event):
        self.menu.post(event.x_root, event.y_root)

    def toggle_listening(self):
        self.is_listening = not self.is_listening
        if self.is_listening:
            self.status_text = "Listening"
            self.status_color = "#00f5d4"
        else:
            self.status_text = "Muted"
            self.status_color = "#6c7086"

    def prompt_text_command(self):
        """Allows clicking the bubble to type a command directly."""
        dialog = tk.Toplevel(self.root)
        dialog.title("Run Command")
        dialog.attributes("-topmost", True)
        dialog.geometry("340x110")
        dialog.configure(bg="#1e1e2e")

        tk.Label(dialog, text="Enter a command for Cactus:", bg="#1e1e2e", fg="#cdd6f4", font=("Segoe UI", 9)).pack(pady=6)
        entry = tk.Entry(dialog, width=38, bg="#313244", fg="#ffffff", insertbackground="#ffffff", font=("Segoe UI", 10))
        entry.pack(pady=4)
        entry.focus_set()

        def submit():
            cmd = entry.get().strip()
            if cmd:
                dialog.destroy()
                self.process_command(cmd)

        entry.bind("<Return>", lambda e: submit())
        tk.Button(dialog, text="Execute", command=submit, bg="#89b4fa", fg="#11111b", font=("Segoe UI", 9, "bold")).pack(pady=6)

    def show_toast(self, message: str, title: str = "Cactus Action"):
        """Displays a sleek floating toast notification next to the bubble."""
        if self.toast_window and self.toast_window.winfo_exists():
            self.toast_window.destroy()

        self.toast_window = tk.Toplevel(self.root)
        self.toast_window.overrideredirect(True)
        self.toast_window.attributes("-topmost", True)
        self.toast_window.configure(bg="#11111b")

        x = self.root.winfo_x() - 100
        y = self.root.winfo_y() - 90
        self.toast_window.geometry(f"340x80+{max(10, x)}+{max(10, y)}")

        frame = tk.Frame(self.toast_window, bg="#181825", highlightbackground="#89b4fa", highlightthickness=1)
        frame.pack(fill="both", expand=True, padx=2, pady=2)

        tk.Label(frame, text=f"⚡ {title}", font=("Segoe UI", 9, "bold"), fg="#89b4fa", bg="#181825").pack(anchor="w", padx=10, pady=(6, 2))
        msg_label = tk.Label(frame, text=message[:180], font=("Segoe UI", 9), fg="#cdd6f4", bg="#181825", justify="left", wraplength=310)
        msg_label.pack(anchor="w", padx=10, pady=(0, 6))

        # Auto-destroy toast after 4.5 seconds
        self.root.after(4500, lambda: self.toast_window.destroy() if self.toast_window and self.toast_window.winfo_exists() else None)

    # ------------------------------------------------------------------
    # CONTINUOUS VOICE LISTENER (VAD & SoundDevice)
    # ------------------------------------------------------------------
    def continuous_audio_listener(self):
        sample_rate = 16000
        block_duration = 0.05  # 50ms blocks
        block_size = int(sample_rate * block_duration)
        
        silence_limit = 1.0    # 1.0 second of silence ends utterance
        max_duration = 7.0     # 7 seconds max command length

        audio_buffer = []
        silence_duration = 0.0

        def audio_callback(indata, frames, time_info, status):
            if not self.is_listening or self.is_processing:
                return

            rms = np.sqrt(np.mean(indata**2))

            if not self.is_recording:
                # Trigger recording when speech energy rises above threshold
                if rms > self.energy_threshold:
                    self.is_recording = True
                    self.status_text = "Hearing..."
                    self.status_color = "#f38ba8"  # Soft Red/Pink
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
                # End of utterance reached
                if silence_duration >= silence_limit or current_len >= max_duration:
                    self.is_recording = False
                    silence_duration = 0.0
                    self.status_text = "Processing..."
                    self.status_color = "#f9e2af"  # Yellow

                    # Concatenate & queue audio clip
                    recording = np.concatenate(audio_buffer, axis=0)
                    temp_wav = os.path.join(self.temp_dir, f"voice_cmd_{int(time.time()*1000)}.wav")
                    sf.write(temp_wav, recording, sample_rate)
                    self.audio_queue.put(temp_wav)

        with sd.InputStream(samplerate=sample_rate, channels=1, dtype=np.float32, blocksize=block_size, callback=audio_callback):
            while True:
                time.sleep(0.1)

    # ------------------------------------------------------------------
    # WORKER THREAD: TRANSCRIPTION + NEEDLE 3 EXECUTION
    # ------------------------------------------------------------------
    def task_worker(self):
        while True:
            audio_path = self.audio_queue.get()
            self.is_processing = True
            try:
                # 1. Whistle Speech-to-Text
                print(f"[WHISTLE] Transcribing {audio_path}...")
                transcript_dict = cactus.transcribe(audio_path)
                query = transcript_dict.get("text", "").strip()
                print(f"[WHISTLE] Heard: \"{query}\"")

                clean_q = query.lower().strip()
                # Ignore silence hallucinations like 'Thank you.' or 'Vielen Dank'
                if not clean_q or clean_q in HALLUCINATED_WORDS or len(clean_q) < 4:
                    print(f"[FILTER] Ignored ambient noise/filler: '{query}'")
                    self.status_text = "Listening"
                    self.status_color = "#00f5d4"
                else:
                    self.process_command(query)
            except Exception as e:
                print(f"[ERROR] Perception pipeline error: {e}")
                self.status_text = "Listening"
                self.status_color = "#00f5d4"
            finally:
                if os.path.exists(audio_path):
                    try:
                        os.remove(audio_path)
                    except Exception:
                        pass
                self.is_processing = False
                self.audio_queue.task_done()

    def process_command(self, query: str):
        """Dispatches query through Needle 3 and updates UI with results."""
        self.status_text = "Thinking..."
        self.status_color = "#cba6f7"  # Lavender

        # Strip polite / wake prefixes that confuse tiny distilled models
        target_query = query.strip()
        for prefix in ["hey there.", "hey there,", "hey there", "hey cactus,", "hey cactus.", "hey cactus", "please", "can you"]:
            if target_query.lower().startswith(prefix):
                target_query = target_query[len(prefix):].strip(" ,.")

        if not target_query:
            target_query = query.strip()

        print(f"[NEEDLE 3] Cleaned query: '{target_query}' (Raw: '{query}')")
        try:
            res = self.agent.run(target_query)
            results = res.get("results", [])
            
            # Format display string for Toast
            if results and isinstance(results, list):
                first_res = results[0]
                if isinstance(first_res, dict):
                    if "output" in first_res:
                        msg = first_res["output"]
                    elif "message" in first_res:
                        msg = first_res["message"]
                    elif "installed" in first_res:
                        msg = f"{first_res['tool']} installed: {first_res['installed']} ({first_res.get('path', '')})"
                    else:
                        msg = str(first_res)
                else:
                    msg = str(first_res)
            elif res.get("reasoning"):
                msg = res["reasoning"]
            else:
                msg = "Command executed."

            self.root.after(0, lambda: self.show_toast(msg, title=query))
        except Exception as e:
            self.root.after(0, lambda: self.show_toast(f"Error: {e}", title="Execution Error"))

        # Return to listening state
        self.status_text = "Listening"
        self.status_color = "#00f5d4"

    def shutdown(self):
        self.is_listening = False
        self.root.destroy()
        os._exit(0)

    def run(self):
        self.root.mainloop()


if __name__ == "__main__":
    print("=" * 60)
    print("🌵 LAUNCHING CACTUS AI FLOATING BUBBLE")
    print("• Always-on-top draggable orb")
    print("• Continuously listens for voice commands")
    print("• Right-click for options | Left-click to type")
    print("=" * 60)
    app = FloatingBubbleApp()
    app.run()

