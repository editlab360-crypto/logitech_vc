"""Encrypted config storage for stream keys and preferences."""
import json, os
from pathlib import Path
from cryptography.fernet import Fernet

CONFIG_DIR = Path(os.getenv("APPDATA", ".")) / "LogitechVC"
CONFIG_DIR.mkdir(parents=True, exist_ok=True)
KEY_FILE = CONFIG_DIR / ".key"
CONFIG_FILE = CONFIG_DIR / "config.enc"

def _get_key() -> bytes:
    if KEY_FILE.exists():
        return KEY_FILE.read_bytes()
    key = Fernet.generate_key()
    KEY_FILE.write_bytes(key)
    return key

class SecureConfig:
    def __init__(self):
        self._fernet = Fernet(_get_key())
        self._data = self._load()

    def _load(self) -> dict:
        default = {"rtmp_url": "", "rtmp_key": "", "camera_index": 0,
                   "audio_index": None, "presets": {}, "reference_map": {}}
        if not CONFIG_FILE.exists():
            return default
        try:
            return json.loads(self._fernet.decrypt(CONFIG_FILE.read_bytes()))
        except Exception:
            return default

    def save(self):
        CONFIG_FILE.write_bytes(self._fernet.encrypt(json.dumps(self._data).encode()))

    def get(self, key, default=None):
        return self._data.get(key, default)

    def set(self, key, value):
        self._data[key] = value
        self.save()
