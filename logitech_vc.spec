# logitech_vc.spec  — build: pyinstaller logitech_vc.spec --clean --noconfirm
from pathlib import Path
import os
import mediapipe

mp_dir = Path(mediapipe.__file__).parent

datas = [
    (str(mp_dir / "modules"), "mediapipe/modules"),
    ("reference_images", "reference_images"),
]
binaries = []
if os.path.exists("ffmpeg.exe"):
    binaries.append(("ffmpeg.exe", "."))

hiddenimports = [
    "mediapipe.python._framework_bindings",
    "pyaudio", "comtypes.stream", "comtypes.gen", "PIL._tkinter_finder",
    "pygrabber.dshow_graph",
]

a = Analysis(["main.py"], pathex=[], binaries=binaries, datas=datas,
             hiddenimports=hiddenimports, hookspath=[], runtime_hooks=[],
             excludes=[], noarchive=False)
pyz = PYZ(a.pure)

exe = EXE(pyz, a.scripts, [], exclude_binaries=True, name="LogitechVC",
          console=False, debug=False, strip=False, upx=False)
coll = COLLECT(exe, a.binaries, a.zipfiles, a.datas, strip=False, upx=False,
               name="LogitechVC")
