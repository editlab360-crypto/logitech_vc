"""
Logitech Group PTZ via DirectShow IAMCameraControl (COM).
Binds to the camera filter through pygrabber, then QueryInterface -> IAMCameraControl.
No hardware read-back: we keep a software position cache.
"""
import ctypes, threading, logging
from ctypes import POINTER, c_long
from comtypes import GUID, COMMETHOD, HRESULT, IUnknown

log = logging.getLogger(__name__)

IID_IAMCameraControl = GUID('{C6E13370-30AC-11d0-A18C-00A0C9118956}')

# CameraControl_Property enum
PAN, TILT, ZOOM = 0, 1, 2
FLAG_AUTO, FLAG_MANUAL = 0x0001, 0x0002


class IAMCameraControl(IUnknown):
    _iid_ = IID_IAMCameraControl
    _methods_ = [
        COMMETHOD([], HRESULT, 'GetRange',
                  (['in'],  c_long, 'Property'),
                  (['out'], POINTER(c_long), 'pMin'),
                  (['out'], POINTER(c_long), 'pMax'),
                  (['out'], POINTER(c_long), 'pSteppingDelta'),
                  (['out'], POINTER(c_long), 'pDefault'),
                  (['out'], POINTER(c_long), 'pCapsFlags')),
        COMMETHOD([], HRESULT, 'Set',
                  (['in'], c_long, 'Property'),
                  (['in'], c_long, 'lValue'),
                  (['in'], c_long, 'Flags')),
        COMMETHOD([], HRESULT, 'Get',
                  (['in'],  c_long, 'Property'),
                  (['out'], POINTER(c_long), 'lValue'),
                  (['out'], POINTER(c_long), 'Flags')),
    ]


class PTZController:
    def __init__(self, device_name="Logitech"):
        self._lock = threading.Lock()
        self._ctrl = None
        self._device_match = device_name
        self._ranges = {"pan": (-1, 1), "tilt": (-1, 1), "zoom": (0, 10)}
        self._current = {"pan": 0, "tilt": 0, "zoom": 0}
        self._graph = None
        self._connect()

    def _connect(self):
        try:
            from pygrabber.dshow_graph import FilterGraph
            graph = FilterGraph()
            names = graph.get_input_devices()
            idx = next((i for i, n in enumerate(names)
                        if self._device_match.lower() in n.lower()), None)
            if idx is None:
                raise RuntimeError(f"Device '{self._device_match}' not found in {names}")
            graph.add_video_input_device(idx)
            base_filter = graph.get_input_device().instance
            self._ctrl = base_filter.QueryInterface(IAMCameraControl)
            self._graph = graph       # keep alive
            log.info(f"PTZ bound to: {names[idx]}")
            self._read_ranges()
        except Exception as e:
            log.error(f"PTZ connection failed: {e}. Hardware PTZ disabled.")
            self._ctrl = None

    def _read_ranges(self):
        if not self._ctrl: return
        for key, prop in (("pan", PAN), ("tilt", TILT), ("zoom", ZOOM)):
            try:
                mn, mx, step, df, caps = self._ctrl.GetRange(prop)
                self._ranges[key] = (mn, mx)
                self._current[key] = df
            except Exception as e:
                log.warning(f"GetRange({key}) failed: {e}")

    @property
    def available(self): return self._ctrl is not None

    def _set(self, prop, key, value, flags=FLAG_MANUAL):
        if not self._ctrl: return False
        with self._lock:
            mn, mx = self._ranges[key]
            value = max(mn, min(mx, value))
            try:
                self._ctrl.Set(prop, value, flags)
                self._current[key] = value
                return True
            except Exception as e:
                log.warning(f"Set({key}={value}) failed: {e}")
                return False

    def step_pan(self, delta):  return self._set(PAN, "pan", self._current["pan"] + delta)
    def step_tilt(self, delta): return self._set(TILT, "tilt", self._current["tilt"] + delta)
    def step_zoom(self, delta): return self._set(ZOOM, "zoom", self._current["zoom"] + delta)

    def absolute(self, pan=None, tilt=None, zoom=None):
        if pan  is not None: self._set(PAN, "pan", int(pan))
        if tilt is not None: self._set(TILT, "tilt", int(tilt))
        if zoom is not None: self._set(ZOOM, "zoom", int(zoom))

    def center(self):
        self.absolute(pan=0, tilt=0, zoom=0)

    def snapshot(self) -> dict: return dict(self._current)

    def recall(self, snap: dict):
        self.absolute(snap.get("pan"), snap.get("tilt"), snap.get("zoom"))
