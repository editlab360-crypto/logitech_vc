"""Application controller + main entrypoint."""
import tkinter as tk
from tkinter import filedialog, messagebox
import queue, threading, logging, os, sys
from pathlib import Path

from config import SecureConfig
from camera import CameraWorker, list_cameras
from ptz_control import PTZController
from tracking import TrackingWorker
from audio import AudioWorker
from recorder import Recorder
from streaming import RTMPStreamer
import tv_output
from ui import DashboardUI

logging.basicConfig(level=logging.INFO,
                    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
log = logging.getLogger("app")


def resource_dir() -> Path:
    return Path(getattr(sys, "_MEIPASS", Path(__file__).parent))

def resolve_ffmpeg() -> str:
    bundled = resource_dir() / "ffmpeg.exe"
    return str(bundled) if bundled.exists() else "ffmpeg"


class AppController:
    def __init__(self):
        self.config = SecureConfig()
        self.ffmpeg = resolve_ffmpeg()

        self.display_q = queue.Queue(maxsize=2)
        self.action_q = queue.Queue(maxsize=10)
        self.latest_frame = None

        self.camera = CameraWorker(self.config.get("camera_index", 0))
        self.audio = AudioWorker()
        self.ptz = PTZController("Logitech")
        self.tracker = TrackingWorker(
            in_queue=self.camera.frame_queue,
            out_queue=self.display_q,
            action_queue=self.action_q,
            ref_dir=str(resource_dir() / "reference_images"),
            mapping=self.config.get("reference_map", {}))
        self.recorder = Recorder(self.ffmpeg)
        self.streamer = RTMPStreamer(self.ffmpeg)

        self._recording = False
        self._rec_q = None
        self._tmp_wav = None
        self._tv_window = None

        self.camera.start()
        self.tracker.start()
        threading.Thread(target=self._consume_actions, daemon=True).start()

    # ---- devices ----
    def on_camera_change(self, idx):
        self.config.set("camera_index", idx)
        self.camera.stop()
        self.camera = CameraWorker(idx)
        self.tracker.in_q = self.camera.frame_queue
        self.camera.start()

    def on_audio_change(self, idx):
        devs = self.audio.list_devices()
        self.config.set("audio_index", devs[idx]["index"] if 0 <= idx < len(devs) else None)

    # ---- PTZ ----
    def ptz_step(self, axis, delta):
        if not self.ptz.available: return
        if axis == "pan":  self.ptz.step_pan(delta * 20)
        if axis == "tilt": self.ptz.step_tilt(delta * 20)
        if axis == "zoom": self.ptz.step_zoom(delta * 50)

    def ptz_home(self):
        self.ptz.center()

    def ptz_save_current(self, slot=1):
        self.config.set(f"preset_{slot}", self.ptz.snapshot())

    def ptz_recall(self, idx):
        snap = self.config.get(f"preset_{idx}")
        if snap: self.ptz.recall(snap)

    def _consume_actions(self):
        while True:
            try: evt = self.action_q.get(timeout=0.5)
            except queue.Empty: continue
            if "preset" in evt:
                try: self.ptz_recall(int(str(evt["preset"]).strip("Ss")))
                except ValueError: pass
            elif "move" in evt and self.ptz.available:
                dx, dy = evt["move"]
                self.ptz.step_pan(int(dx * 40))
                self.ptz.step_tilt(int(-dy * 40))

    # ---- recording ----
    def start_recording(self):
        if self._recording: return
        idx = self.config.get("audio_index")
        try:
            self._tmp_wav = str(Path(os.getenv("TEMP", ".")) / "lvc_audio.wav")
            self._rec_q = queue.Queue(maxsize=90)
            self.audio.start(idx)
            self.recorder.start(self._rec_q, (1920, 1080), fps=30, fmt="mp4")
            self.tracker.rec_q = self._rec_q
            self._recording = True
        except Exception as e:
            messagebox.showerror("Recording", str(e))

    def stop_recording(self):
        if not self._recording: return
        self.tracker.rec_q = None
        out = filedialog.asksaveasfilename(
            defaultextension=".mp4",
            filetypes=[("MP4 Video", "*.mp4"), ("WebM Video", "*.webm")])
        self.audio.stop(self._tmp_wav)
        if not out:
            self.recorder._stop.set()
            self._recording = False
            return
        self.recorder._out_format = "webm" if out.lower().endswith(".webm") else "mp4"
        try:
            self.recorder.stop(self._tmp_wav, out)
            messagebox.showinfo("Recording", f"සුරකින ලදී:\n{out}")
        except Exception as e:
            messagebox.showerror("Recording", str(e))
        finally:
            self._recording = False
            try: os.remove(self._tmp_wav)
            except OSError: pass

    # ---- TV ----
    def open_tv_window(self):
        mons = tv_output.get_monitors()
        if len(mons) < 2:
            messagebox.showinfo("TV", "දෙවන මොනිටරයක් හමු නොවිණි.")
            return
        self.close_tv_window()
        tv = tk.Toplevel()
        tv.configure(bg="black")
        lbl = tk.Label(tv, bg="black"); lbl.pack(fill="both", expand=True)
        tv_output.place_fullscreen(tv, mons[1])
        self._tv_window = (tv, lbl)

        def refresh():
            frame = self.latest_frame
            if frame is not None and self._tv_window:
                import cv2
                from PIL import Image, ImageTk
                big = cv2.resize(frame, (mons[1]["w"], mons[1]["h"]))
                self._tv_img = ImageTk.PhotoImage(Image.fromarray(big[:, :, ::-1]))
                lbl.configure(image=self._tv_img)
            if self._tv_window:
                tv.after(33, refresh)
        refresh()

    def close_tv_window(self):
        if self._tv_window:
            tv = self._tv_window[0]
            self._tv_window = None
            try: tv.destroy()
            except Exception: pass


def main():
    root = tk.Tk()
    controller = AppController()
    ui = DashboardUI(root, controller)

    cams = list_cameras()
    ui.camera_cb["values"] = [c["name"] for c in cams] or ["— none —"]
    if cams: ui.camera_cb.current(min(controller.config.get("camera_index", 0), len(cams) - 1))
    auds = controller.audio.list_devices()
    ui.audio_cb["values"] = [a["name"] for a in auds] or ["— none —"]
    if auds: ui.audio_cb.current(0)

    def on_close():
        for fn in (controller.camera.stop, controller.tracker.stop,
                   controller.streamer.stop, controller.audio.close):
            try: fn()
            except Exception: pass
        root.destroy()

    root.protocol("WM_DELETE_WINDOW", on_close)
    root.mainloop()


if __name__ == "__main__":
    main()
