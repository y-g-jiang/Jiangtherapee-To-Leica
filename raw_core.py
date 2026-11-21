import ctypes as ct
import os
import platform
import sys
from functools import lru_cache
from pathlib import Path
from types import SimpleNamespace
import numpy as np

COMMIT='40fb564486681a04eba0318058b0519f4f69eba8'
VERSION='0.23.0-Snapshot202611'
UInt=ct.c_uint;Float=ct.c_float;Handle=ct.c_void_p;Pixels=ct.POINTER(ct.c_ushort)

class Metadata(ct.Structure):
    _fields_=[(field,UInt) for field in ('raw_height','raw_width','height','width','top','left','iheight','iwidth','pitch')]+[('flip',ct.c_int),('bayer',ct.c_int*4),('aspect',ct.c_double),('desc',ct.c_char*5),('black',UInt*4),('white',UInt*4),('maximum',UInt),('camera',Float*4),('daylight',Float*4),('matrix',Float*12),('xyz',Float*12)]

@lru_cache(maxsize=1)
def library():
    windows=sys.platform=='win32';filename='jtl-libraw-win.dll' if windows else 'jtl-libraw-'+platform.machine()+'.dylib';lib=ct.CDLL(str(Path(__file__).resolve().parent/'assets'/filename));ptr=ct.POINTER
    for name,inputs,output in [('jtl_version',[],ct.c_char_p),('jtl_commit',[],ct.c_char_p),('jtl_error',[ct.c_int],ct.c_char_p),('jtl_close',[Handle],None),('jtl_open',[ct.c_wchar_p if windows else ct.c_char_p,ptr(Handle)],ct.c_int),('jtl_info',[Handle,ptr(Metadata)],Pixels),('jtl_process',[Handle,ct.c_int,ptr(Handle),ptr(Pixels),ptr(UInt),ptr(UInt)],ct.c_int),('jtl_free_image',[Handle],None)]:
        fn=getattr(lib,name);fn.argtypes=inputs;fn.restype=output
    if (lib.jtl_version().decode(),lib.jtl_commit().decode())!=(VERSION,COMMIT):raise RuntimeError('LibRaw 版本不匹配。')
    lib.jtl_crop.argtypes=[Handle,ptr(UInt)];lib.jtl_crop.restype=None
    return lib

class Reader:
    def __init__(self,path):self.path=path;self.handle=Handle()
    def check(self,status):
        if status:raise ValueError('LibRaw: '+self.lib.jtl_error(status).decode('utf-8',errors='replace'))
    def __enter__(self):
        self.lib=library();self.check(self.lib.jtl_open(str(self.path) if sys.platform=='win32' else os.fsencode(self.path),ct.byref(self.handle)))
        try:
            info=Metadata();pixels=self.lib.jtl_info(self.handle,ct.byref(info));self.sizes=SimpleNamespace(height=info.height,width=info.width,iheight=info.iheight,iwidth=info.iwidth,left_margin=info.left,top_margin=info.top,flip=info.flip,pixel_aspect=info.aspect)
            crop=(UInt*4)();self.lib.jtl_crop(self.handle,crop);self.visible_crop=tuple(crop)
            self.color_desc=info.desc;self.raw_pattern=None;self.raw_image_visible=None
            if pixels:
                full=np.ctypeslib.as_array(pixels,shape=(info.raw_height,info.pitch//2));self.raw_image_visible=full[info.top:info.top+info.height,info.left:info.left+info.width]
                self.raw_pattern=np.array(info.bayer).reshape(2,2)
            self.black_level_per_channel=list(info.black);self.white_level=info.maximum;self.camera_white_level_per_channel=list(info.white) if all(info.white) else None
            self.camera_whitebalance=list(info.camera);self.daylight_whitebalance=list(info.daylight);self.color_matrix=np.array(info.matrix).reshape(3,4);self.rgb_xyz_matrix=np.array(info.xyz).reshape(4,3)
            return self
        except BaseException:self.__exit__(None,None,None);raise
    def raw_color(self,row,col):return self.raw_pattern[(row-self.sizes.top_margin)%2,(col-self.sizes.left_margin)%2]
    def process(self,half):
        image=Handle();pixels=Pixels();height=UInt();width=UInt();self.check(self.lib.jtl_process(self.handle,int(half),ct.byref(image),ct.byref(pixels),ct.byref(height),ct.byref(width)))
        try:return np.ctypeslib.as_array(pixels,shape=(height.value,width.value,3)).copy()
        finally:self.lib.jtl_free_image(image)
    def __exit__(self,*args):self.raw_image_visible=None;self.lib.jtl_close(self.handle);self.handle=Handle()
