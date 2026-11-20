"""Face detection + auto-framing + up to 5 reference-image recognition."""
import cv2, threading, queue, time, logging
from pathlib import Path
import mediapipe as mp

log = logging.getLogger(__name__)


class TrackingWorker:
    FACE_MATCH_INTERVAL = 0.5

    def __init__(self, in_queue, out_queue, action_queue, ref_dir="reference_images",
                 mapping=None, downscale=(640, 360)):
        self.in_q  = in_queue
        self.out_q = out_queue
        self.act_q = action_queue
        self.rec_q = None            # set by controller while recording (raw frames)
        self.ref_dir = Path(ref_dir)
        self.mapping = mapping or {}
        self.downscale = downscale
        self._stop = threading.Event()
        self._thread = None
        self._last_recognize = 0.0

        self.mp_face = mp.solutions.face_detection
        self.detector = self.mp_face.FaceDetection(model_selection=1,
                                                   min_detection_confidence=0.5)
        self._load_references()

        self.auto_frame_enabled = True
        self.recognize_enabled  = True
        self.last_action = "idle"

    def _load_references(self):
        self.refs = []
        if not self.ref_dir.exists():
            log.warning(f"Reference dir missing: {self.ref_dir}")
            return
        for path in sorted(self.ref_dir.iterdir())[:5]:
            if path.suffix.lower() not in (".jpg", ".jpeg", ".png"): continue
            img = cv2.imread(str(path), cv2.IMREAD_GRAYSCALE)
            if img is None: continue
            self.refs.append((path.stem, cv2.resize(img, (100, 100))))
        log.info(f"Loaded {len(self.refs)} reference image(s)")

    def _match_reference(self, face_crop_gray):
        if not self.refs or face_crop_gray.size == 0: return None
        probe = cv2.resize(face_crop_gray, (100, 100))
        best_name, best_score = None, 0.6
        for name, tmpl in self.refs:
            score = cv2.matchTemplate(probe, tmpl, cv2.TM_CCOEFF_NORMED)[0][0]
            if score > best_score:
                best_name, best_score = name, score
        return best_name

    def start(self):
        self._stop.clear()
        self._thread = threading.Thread(target=self._loop, daemon=True, name="Tracker")
        self._thread.start()

    def _loop(self):
        while not self._stop.is_set():
            try:
                frame = self.in_q.get(timeout=0.2)
            except queue.Empty:
                continue

            # hand a clean copy to the recorder (before annotations)
            rq = self.rec_q
            if rq is not None:
                try: rq.put_nowait(frame.copy())
                except queue.Full: pass

            h, w = frame.shape[:2]
            rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            results = self.detector.process(rgb)

            faces, cx, cy, hit = [], w // 2, h // 2, None
            if results.detections:
                boxes = []
                for d in results.detections:
                    bb = d.location_data.relative_bounding_box
                    x, y = max(0, int(bb.xmin * w)), max(0, int(bb.ymin * h))
                    bw, bh = int(bb.width * w), int(bb.height * h)
                    boxes.append((x, y, bw, bh))
                boxes.sort(key=lambda b: b[2] * b[3], reverse=True)
                faces = boxes
                x, y, bw, bh = boxes[0]
                cx, cy = x + bw // 2, y + bh // 2

                now = time.time()
                if self.recognize_enabled and now - self._last_recognize >= self.FACE_MATCH_INTERVAL:
                    self._last_recognize = now
                    crop = cv2.cvtColor(frame[y:y+bh, x:x+bw], cv2.COLOR_BGR2GRAY)
                    hit = self._match_reference(crop)

                cv2.rectangle(frame, (x, y), (x + bw, y + bh), (0, 200, 255), 3)
                if hit:
                    cv2.putText(frame, hit, (x, max(20, y - 10)),
                                cv2.FONT_HERSHEY_SIMPLEX, 1.2, (0, 255, 0), 3)

            if hit and hit in self.mapping:
                self._emit({"preset": self.mapping[hit]})
                self.last_action = f"preset:{self.mapping[hit]}"
            elif self.auto_frame_enabled and faces:
                dx = (cx - w // 2) / (w // 2)
                dy = (cy - h // 2) / (h // 2)
                if abs(dx) > 0.25 or abs(dy) > 0.25:
                    self._emit({"move": (dx, dy)})
                    self.last_action = f"frame dx={dx:.2f} dy={dy:.2f}"

            small = cv2.resize(frame, self.downscale, interpolation=cv2.INTER_AREA)
            try:
                self.out_q.put_nowait(small)
            except queue.Full:
                try: self.out_q.get_nowait()
                except queue.Empty: pass
                try: self.out_q.put_nowait(small)
                except queue.Full: pass

    def _emit(self, evt):
        try: self.act_q.put_nowait(evt)
        except queue.Full: pass

    def stop(self):
        self._stop.set()
        if self._thread: self._thread.join(timeout=2.0)
