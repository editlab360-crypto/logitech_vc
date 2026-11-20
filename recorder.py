"""Video (OpenCV) + audio (PyAudio) + FFmpeg mux -> MP4 or WebM."""
import cv2, threading, queue, subprocess, os, tempfile, logging

log = logging.getLogger(__name__)


class Recorder:
    def __init__(self, ffmpeg_path="ffmpeg"):
        self.ffmpeg = ffmpeg_path
        self._video_thread = None
        self._stop = threading.Event()
        self._vid_path = None
        self._writer = None
        self._size = (1920, 1080)
        self._out_format = "mp4"

    def start(self, frame_source_queue: queue.Queue, size, fps=30, fmt="mp4"):
        self._out_format = fmt
        self._size = size
        self._stop.clear()
        tmp = tempfile.mkdtemp(prefix="lvc_")
        self._vid_path = os.path.join(tmp, "video.avi")
        fourcc = cv2.VideoWriter_fourcc(*"MJPG")
        self._writer = cv2.VideoWriter(self._vid_path, fourcc, fps, size)
        self._video_thread = threading.Thread(
            target=self._video_loop, args=(frame_source_queue,),
            daemon=True, name="VideoRec")
        self._video_thread.start()

    def _video_loop(self, src_q):
        while not self._stop.is_set():
            try:
                frame = src_q.get(timeout=0.2)
            except queue.Empty:
                continue
            if (frame.shape[1], frame.shape[0]) != self._size:
                frame = cv2.resize(frame, self._size)
            self._writer.write(frame)

    def stop(self, audio_wav_path: str, output_path: str) -> str:
        self._stop.set()
        if self._video_thread: self._video_thread.join(timeout=3.0)
        self._writer.release()

        if self._out_format == "mp4":
            codec = ["-c:v", "libx264", "-preset", "veryfast", "-crf", "23",
                     "-c:a", "aac", "-b:a", "192k"]
        else:
            codec = ["-c:v", "libvpx-vp9", "-b:v", "2M",
                     "-c:a", "libopus", "-b:a", "128k"]

        cmd = [self.ffmpeg, "-y", "-i", self._vid_path, "-i", audio_wav_path,
               *codec, "-af", "aresample=async=1", "-shortest"]
        if self._out_format == "mp4":
            cmd += ["-movflags", "+faststart"]
        cmd.append(output_path)
        log.info("Muxing: " + " ".join(cmd))
        res = subprocess.run(cmd, capture_output=True, text=True)
        if res.returncode != 0:
            log.error(f"FFmpeg mux failed: {res.stderr}")
            raise RuntimeError("Mux failed — see logs")
        log.info(f"Saved -> {output_path}")
        return output_path
