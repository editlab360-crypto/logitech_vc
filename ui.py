"""Tkinter UI with the dark dashboard aesthetic."""
import tkinter as tk
from tkinter import ttk
from PIL import Image, ImageTk
import queue, logging

log = logging.getLogger(__name__)

BG, PANEL, ACCENT = "#121212", "#1e1e1e", "#0078d4"
ACCENT_HOVER, DANGER, TEXT, MUTED = "#0086f0", "#d83b01", "#e0e0e0", "#b0b0b0"
SINHALA = ("Iskoola Pota", 11)


class DashboardUI:
    def __init__(self, root, controller):
        self.root = root
        self.ctrl = controller
        self.display_q = controller.display_q
        self._build()

    def _btn(self, parent, text, cmd, danger=False, **kw):
        return tk.Button(parent, text=text, command=cmd,
                         bg=DANGER if danger else ACCENT, fg="white",
                         activebackground="#ea4300" if danger else ACCENT_HOVER,
                         activeforeground="white", relief="flat",
                         font=("Segoe UI", 10, "bold"), cursor="hand2",
                         padx=12, pady=8, **kw)

    def _label(self, parent, text, muted=False):
        return tk.Label(parent, text=text, bg=PANEL,
                        fg=MUTED if muted else TEXT, font=SINHALA, anchor="w")

    def _build(self):
        self.root.configure(bg=BG)
        self.root.title("Logitech Group — Control & Recording")
        self.root.geometry("1200x760")

        tk.Label(self.root, text="Logitech Group · Control & Recording Dashboard",
                 bg=BG, fg="#00bcd4", font=("Segoe UI", 18, "bold")).pack(pady=(16, 8))

        body = tk.Frame(self.root, bg=BG)
        body.pack(fill="both", expand=True, padx=20, pady=10)

        left = tk.Frame(body, bg=PANEL, padx=16, pady=16)
        left.pack(side="left", fill="both", expand=True, padx=(0, 10))
        self.video_label = tk.Label(left, bg="black", width=80, height=30)
        self.video_label.pack()
        self.status = tk.Label(left, text="තත්ත්වය: උපාංග සොයමින් පවතී...",
                               bg=PANEL, fg="#4caf50", font=SINHALA)
        self.status.pack(pady=6)

        right = tk.Frame(body, bg=PANEL, padx=16, pady=16, width=340)
        right.pack(side="right", fill="y")
        right.pack_propagate(False)

        self._label(right, "කැමරාව (Camera):").pack(fill="x", pady=(4, 2))
        self.camera_var = tk.StringVar()
        self.camera_cb = ttk.Combobox(right, textvariable=self.camera_var,
                                      state="readonly", font=SINHALA)
        self.camera_cb.pack(fill="x")
        self.camera_cb.bind("<<ComboboxSelected>>",
                            lambda e: self.ctrl.on_camera_change(self.camera_cb.current()))

        self._label(right, "මයික්‍රෆෝනය (Microphone):").pack(fill="x", pady=(10, 2))
        self.audio_var = tk.StringVar()
        self.audio_cb = ttk.Combobox(right, textvariable=self.audio_var,
                                     state="readonly", font=SINHALA)
        self.audio_cb.pack(fill="x")
        self.audio_cb.bind("<<ComboboxSelected>>",
                           lambda e: self.ctrl.on_audio_change(self.audio_cb.current()))

        ttk.Separator(right).pack(fill="x", pady=12)

        self._label(right, "PTZ පාලනය (Manual):").pack(fill="x")
        ptz = tk.Frame(right, bg=PANEL); ptz.pack(pady=6)
        for txt, cmd in [("◀", lambda: self.ctrl.ptz_step("pan", -1)),
                         ("▶", lambda: self.ctrl.ptz_step("pan",  1)),
                         ("▲", lambda: self.ctrl.ptz_step("tilt", 1)),
                         ("▼", lambda: self.ctrl.ptz_step("tilt", -1))]:
            self._btn(ptz, txt, cmd, width=3).pack(side="left", padx=2)

        zoomf = tk.Frame(right, bg=PANEL); zoomf.pack(pady=4)
        self._btn(zoomf, "Zoom +", lambda: self.ctrl.ptz_step("zoom",  1)).pack(side="left", padx=2)
        self._btn(zoomf, "Zoom −", lambda: self.ctrl.ptz_step("zoom", -1)).pack(side="left", padx=2)
        self._btn(zoomf, "Home", self.ctrl.ptz_home, danger=True).pack(side="left", padx=2)

        self._label(right, "Presets (1-5):").pack(fill="x", pady=(10, 2))
        presetf = tk.Frame(right, bg=PANEL); presetf.pack(fill="x")
        for i in range(1, 6):
            self._btn(presetf, f"S{i}", lambda i=i: self.ctrl.ptz_recall(i), width=3
                      ).pack(side="left", padx=1)
        saveF = tk.Frame(right, bg=PANEL); saveF.pack(fill="x", pady=4)
        self._label(saveF, "Save to:").pack(side="left")
        self.save_slot = tk.StringVar(value="1")
        ttk.Combobox(saveF, textvariable=self.save_slot, values=["1","2","3","4","5"],
                     width=3, state="readonly").pack(side="left", padx=4)
        self._btn(saveF, "Save current",
                  lambda: self.ctrl.ptz_save_current(int(self.save_slot.get()))
                  ).pack(side="left", fill="x", expand=True)

        ttk.Separator(right).pack(fill="x", pady=12)

        self._label(right, "Recording:").pack(fill="x")
        recf = tk.Frame(right, bg=PANEL); recf.pack(fill="x", pady=4)
        self.rec_start = self._btn(recf, "Start Record", self.ctrl.start_recording)
        self.rec_start.pack(side="left", fill="x", expand=True, padx=(0, 4))
        self.rec_stop = self._btn(recf, "Stop & Save", self.ctrl.stop_recording, danger=True)
        self.rec_stop.pack(side="left", fill="x", expand=True)

        self._btn(right, "Send to TV (Fullscreen)",
                  self.ctrl.open_tv_window).pack(fill="x", pady=(12, 2))
        self._btn(right, "Exit TV", self.ctrl.close_tv_window, danger=True).pack(fill="x")

        self.footer = tk.Label(self.root, text="Ready", bg=BG, fg=MUTED, font=("Segoe UI", 9))
        self.footer.pack(side="bottom", fill="x", pady=4)

        self._update_frame()

    def _update_frame(self):
        try:
            frame = self.display_q.get_nowait()
            self.ctrl.latest_frame = frame          # shared with TV window
            img = Image.fromarray(frame[:, :, ::-1])
            self.imgtk = ImageTk.PhotoImage(image=img)
            self.video_label.configure(image=self.imgtk, width=0, height=0)
        except queue.Empty:
            pass
        except Exception as e:
            log.debug(f"UI frame skip: {e}")
        self.root.after(30, self._update_frame)

    def set_status(self, text, color="#4caf50"):
        self.status.config(text=text, fg=color)
        self.footer.config(text=text)
