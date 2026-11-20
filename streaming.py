"""Optional RTMP stream via bundled FFmpeg (requires internet)."""
import subprocess, logging
log = logging.getLogger(__name__)


class RTMPStreamer:
    def __init__(self, ffmpeg="ffmpeg"):
        self.ffmpeg = ffmpeg
        self._proc = None

    def start(self, rtmp_url: str, stream_key: str, video_device: str, audio_device: str):
        if not rtmp_url or not stream_key:
            raise ValueError("RTMP URL and key required")
        full = f"{rtmp_url.rstrip('/')}/{stream_key}"
        cmd = [self.ffmpeg,
               "-f", "dshow", "-rtbufsize", "100M", "-i", f"video={video_device}",
               "-f", "dshow", "-i", f"audio={audio_device}",
               "-c:v", "libx264", "-preset", "veryfast", "-tune", "zerolatency",
               "-b:v", "2500k", "-c:a", "aac", "-b:a", "128k", "-ar", "44100",
               "-f", "flv", full]
        log.info("RTMP start (key hidden)")
        self._proc = subprocess.Popen(cmd, stderr=subprocess.PIPE)

    def stop(self):
        if self._proc:
            self._proc.terminate()
            try: self._proc.wait(timeout=5)
            except subprocess.TimeoutExpired: self._proc.kill()
            self._proc = None

    @property
    def running(self):
        return self._proc is not None and self._proc.poll() is None
