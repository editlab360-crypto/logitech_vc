"""Camera capture thread with graceful device selection and recovery."""
import cv2, threading, queue, time, logging

log = logging.getLogger(__name__)

class CameraWorker:
    """Captures 1080p@30fps into a bounded queue (size=2 -> auto-drop).
    Detects disconnect and auto-reconnects."""
    def __init__(self, device_index=0, width=1920, height=1080, fps=30):
        self.device_index = device_index
        self.width, self.height, self.fps = width, height, fps
        self.frame_queue: queue.Queue = queue.Queue(maxsize=2)
        self._stop = threading.Event()
        self._cap = None
        self._thread = None
        self.status = "idle"

    def start(self):
        self._stop.clear()
        self._thread = threading.Thread(target=self._loop, daemon=True, name="CamCapture")
        self._thread.start()

    def _open(self):
        # Force DirectShow to avoid MSMF latency on Windows
        cap = cv2.VideoCapture(self.device_index, cv2.CAP_DSHOW)
        cap.set(cv2.CAP_PROP_FRAME_WIDTH, self.width)
        cap.set(cv2.CAP_PROP_FRAME_HEIGHT, self.height)
        cap.set(cv2.CAP_PROP_FPS, self.fps)
        cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
        return cap

    def _loop(self):
        while not self._stop.is_set():
            if self._cap is None or not self._cap.isOpened():
                self.status = "reconnecting"
                self._cap = self._open()
                if not self._cap.isOpened():
                    time.sleep(1.0)
                    continue
                self.status = "live"

            ok, frame = self._cap.read()
            if not ok:
                log.warning("Camera read failed — reconnecting")
                self._cap.release()
                self._cap = None
                time.sleep(0.5)
                continue

            try:
                self.frame_queue.put_nowait(frame)
            except queue.Full:
                try: self.frame_queue.get_nowait()
                except queue.Empty: pass
                try: self.frame_queue.put_nowait(frame)
                except queue.Full: pass

    def stop(self):
        self._stop.set()
        if self._thread: self._thread.join(timeout=2.0)
        if self._cap: self._cap.release()

def list_cameras(max_index=6):
    """Enumerate DirectShow cameras using pygrabber (labels) + cv2 (probe)."""
    devices = []
    try:
        from pygrabber.dshow_graph import FilterGraph
        names = FilterGraph().get_input_devices()
        for i, name in enumerate(names):
            devices.append({"index": i, "name": name})
        return devices
    except Exception as e:
        log.warning(f"pygrabber unavailable ({e}); falling back to cv2 probe")
        for i in range(max_index):
            cap = cv2.VideoCapture(i, cv2.CAP_DSHOW)
            if cap.isOpened():
                devices.append({"index": i, "name": f"Camera {i}"})
                cap.release()
        return devices
