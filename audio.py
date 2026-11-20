"""Threaded audio capture to WAV (muxed later by FFmpeg)."""
import pyaudio, wave, threading, logging

log = logging.getLogger(__name__)


class AudioWorker:
    RATE, CHANNELS, CHUNK = 44100, 2, 1024

    def __init__(self):
        self.pa = pyaudio.PyAudio()
        self.stream = None
        self._frames = []
        self._stop = threading.Event()
        self._thread = None
        self.device_index = None

    def list_devices(self):
        out = []
        for i in range(self.pa.get_device_count()):
            info = self.pa.get_device_info_by_index(i)
            if info["maxInputChannels"] > 0:
                out.append({"index": i, "name": info["name"]})
        return out

    def start(self, device_index=None):
        self.device_index = device_index
        self._frames.clear()
        self._stop.clear()
        self.stream = self.pa.open(
            format=pyaudio.paInt16, channels=self.CHANNELS, rate=self.RATE,
            input=True, input_device_index=device_index,
            frames_per_buffer=self.CHUNK)
        self._thread = threading.Thread(target=self._loop, daemon=True, name="AudioCap")
        self._thread.start()

    def _loop(self):
        while not self._stop.is_set():
            try:
                self._frames.append(self.stream.read(self.CHUNK, exception_on_overflow=False))
            except Exception as e:
                log.warning(f"Audio read: {e}")
                break

    def stop(self, path: str):
        self._stop.set()
        if self._thread: self._thread.join(timeout=2.0)
        if self.stream:
            self.stream.stop_stream(); self.stream.close()
        with wave.open(path, 'wb') as wf:
            wf.setnchannels(self.CHANNELS)
            wf.setsampwidth(2)
            wf.setframerate(self.RATE)
            wf.writeframes(b''.join(self._frames))

    def close(self):
        try: self.pa.terminate()
        except Exception: pass
