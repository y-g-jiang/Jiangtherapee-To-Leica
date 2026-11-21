import ctypes
import platform
import sys
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

import numpy as np

KNOTS=(0,156,625,1842,4000,7200,10000)
NEUTRAL=(KNOTS,)*4

@dataclass(frozen=True)
class Grade:
    ev:int=0
    brightness:int=0
    contrast:int=0
    saturation:int=0
    vibrance:int=0
    shoulder:int=0
    curves:tuple=NEUTRAL
    chroma:int=30
    grain:int=100
    grain_iso:int=0

DEFAULT=Grade()
fp=ctypes.POINTER(ctypes.c_float);up=ctypes.POINTER(ctypes.c_uint16)
def ptr(array,kind=fp):return array.ctypes.data_as(kind)

@lru_cache(maxsize=1)
def native():
    if sys.platform=='win32':name='win.dll'
    elif sys.platform=='darwin':name=platform.machine()+'.dylib'
    else:raise RuntimeError('此预构建版本支持 Windows 和 macOS。')
    lib=ctypes.CDLL(str(Path(__file__).resolve().parent/'assets'/('jtl-darkroom-'+name)))
    lib.make_curve.argtypes=[fp,fp,ctypes.c_int,up,fp];lib.make_curve.restype=ctypes.c_int
    lib.make_gamma.argtypes=[ctypes.c_float,fp];lib.make_gamma.restype=None
    lib.process_rgb.argtypes=[fp,fp,ctypes.c_size_t,fp,fp,up,fp,ctypes.c_int];lib.process_rgb.restype=None
    return lib

@lru_cache(maxsize=16)
def curve(values):
    if len(values)!=len(KNOTS) or values[0]!=0 or values[-1]!=10000 or any(left>right for left,right in zip(values,values[1:])):raise ValueError('曲线控制点超出范围。')
    knots=np.asarray(KNOTS,'f')/10000;levels=np.asarray(values,'f')/10000
    table=np.empty(65536,'uint16');coeff=np.empty(3,'f');status=native().make_curve(ptr(knots),ptr(levels),len(knots),ptr(table,up),ptr(coeff))
    if status:raise ValueError('无法生成影调曲线。')
    return table,coeff

@lru_cache(maxsize=4)
def curves(values):
    parts=[curve(points) for points in values]
    return np.stack([item[0] for item in parts]),np.stack([item[1] for item in parts]),sum((points!=KNOTS)<<idx for idx,points in enumerate(values))

@lru_cache(maxsize=12)
def gamma(value):
    table=np.empty(65536,'f')
    if value:native().make_gamma(value/100,ptr(table))
    return table

def apply(image,grade):
    if not any((grade.ev,grade.brightness,grade.contrast,grade.saturation,grade.vibrance,grade.shoulder)) and grade.curves==NEUTRAL:return image
    image=np.ascontiguousarray(image,dtype=np.float32);out=np.empty_like(image)
    params=np.array((grade.ev/100,grade.brightness/100,grade.contrast/100,grade.saturation/100,grade.vibrance/100,grade.shoulder),'f')
    tables,coeff,mask=curves(grade.curves);lut=gamma(grade.brightness)
    native().process_rgb(ptr(image),ptr(out),image.size//3,ptr(params),ptr(lut),ptr(tables,up),ptr(coeff),mask)
    np.fmax(out,0,out=out);np.minimum(out,64,out=out)
    return out
