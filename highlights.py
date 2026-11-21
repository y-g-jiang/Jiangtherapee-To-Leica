import ctypes
import platform
import sys
from functools import lru_cache
from pathlib import Path

import numpy as np


@lru_cache(maxsize=1)
def library():
    name='rt_highlights.dll' if sys.platform=='win32' else f'rt-highlights-{platform.machine()}.dylib'
    lib=ctypes.CDLL(str(Path(__file__).resolve().parent/'assets'/name))
    floats=np.ctypeslib.ndpointer(np.float32,flags='C_CONTIGUOUS')
    lib.recover.argtypes=[floats,ctypes.c_int,ctypes.c_int,ctypes.c_int,floats,floats,ctypes.c_float];lib.recover.restype=ctypes.c_int
    return lib


def recover(camera,wb,observed,cancelled):
    height,width=camera.shape[:2]
    if min(height,width)<32:raise ValueError('RAW 高光恢复需要至少 32 × 32 像素。')
    if cancelled():raise InterruptedError('已取消')
    if not observed.any():return camera
    camera*=65535
    status=library().recover(camera,width,height,1,np.ascontiguousarray(wb[:3],'f'),observed,1.)
    if status:raise RuntimeError(f'RawTherapee 高光恢复失败（{status}）。')
    if cancelled():raise InterruptedError('已取消')
    camera/=65535
    return camera
