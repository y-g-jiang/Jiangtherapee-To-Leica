from contextlib import contextmanager
import ctypes
from functools import lru_cache
from pathlib import Path
import platform
import sys
import tempfile

import cv2
import numpy as np


def features(source):
    soft = cv2.GaussianBlur(source, (7, 7), 1.2)
    broad = cv2.GaussianBlur(source, (19, 19), 3.0)
    def magnitude(first,second):
        red,green,blue = cv2.split(cv2.absdiff(first,second))
        return cv2.max(cv2.max(red,green),blue)
    fine = magnitude(source,soft)
    coherent = magnitude(soft,broad)
    return np.stack([np.log1p(cv2.GaussianBlur(detail, (7, 7), 1.1))
                     for detail in (fine, coherent)], axis=-1)


GATE_WEIGHTS = (8.330923, -1.838407, -5.338299)


def flat_gate(source):
    signal = features(source)
    bias, fine, coherent = GATE_WEIGHTS
    logit = bias + fine*signal[..., 0] + coherent*signal[..., 1]
    confidence = np.clip((logit+2)/4, 0, 1)
    confidence = confidence*confidence*(3-2*confidence)
    gate = np.rint(confidence*255).astype(np.uint8)
    return cv2.erode(gate, np.ones((5, 5), np.uint8))


@contextmanager
def guides(shape, directory=None):
    height, width = shape
    count = height*width
    if count*7 <= 24*1024**2:
        yield np.empty((height,width,3),np.uint16), np.empty(shape,np.uint8)
        return
    with tempfile.TemporaryFile(dir=directory) as store:
        memory = np.memmap(store, mode='w+', shape=(7*count,), dtype=np.uint8)
        try:
            yield memory[:6*count].view(np.uint16).reshape(height,width,3), memory[6*count:].reshape(shape)
        finally:
            memory._mmap.close()


def check_cancelled(cancelled):
    if cancelled():
        raise InterruptedError('已取消')


@lru_cache(maxsize=1)
def native_exchange():
    suffix = 'win.dll' if sys.platform=='win32' else platform.machine()+'.dylib'
    try:
        library = ctypes.CDLL(str(Path(__file__).resolve().parent/'assets'/('jtl-flat-'+suffix)))
    except OSError:
        return None
    kernel = library.jtl_flat_exchange
    kernel.argtypes = [ctypes.c_void_p]*4 + [ctypes.c_int]*3
    kernel.restype = None
    return kernel


def exchange(output, source, gate, step):
    if not gate.any():
        return
    links = cv2.erode(np.ascontiguousarray(gate), np.ones((1,step+1),np.uint8), anchor=(0,0))[:, :-step]
    if not links.any():
        return
    kernel = native_exchange()
    if kernel is not None:
        values = np.ascontiguousarray(output)
        original = values.copy()
        guide = np.ascontiguousarray(source)
        weights = np.ascontiguousarray(links)
        kernel(original.ctypes.data,guide.ctypes.data,weights.ctypes.data,values.ctypes.data,*gate.shape,step)
        if values is not output:
            output[:] = values
        return
    values = output.astype(np.int32)
    original = source.astype(np.int32)
    left, right = values[:, :-step], values[:, step:]
    delta = (right-left) - (original[:, step:]-original[:, :-step])
    np.clip(delta, np.maximum(-left,right-65535), np.minimum(65535-left,right), out=delta)
    weighted = delta * links[..., None]
    flux = (np.abs(weighted)+510)//1020 * np.sign(weighted)
    left += flux
    right -= flux
    output[:] = values


def refine(output, source, gate, proxy_shape, cancelled, progress=None):
    height,width = gate.shape
    rows = max(1,131072//width)
    for start in range(0,height,rows):
        check_cancelled(cancelled)
        stop = min(height,start+rows)
        top,bottom = max(0,start-14),min(height,stop+14)
        encoded = source[top:bottom].astype(np.float32)/257
        confidence = flat_gate(encoded)[start-top:stop-top]
        np.minimum(confidence, gate[start:stop], out=gate[start:stop])
    previous = [0,0]
    for index,distance in enumerate((1,2,4,8,16)):
        for axis in (1,0):
            length = output.shape[axis]
            step = max(1, round(distance*length/proxy_shape[axis]))
            if step >= length or step == previous[axis]:
                continue
            previous[axis] = step
            view = output.swapaxes(1,axis)
            guide = source.swapaxes(1,axis)
            confidence = gate.swapaxes(1,axis)
            block = max(1,131072//length)
            for start in range(0,len(view),block):
                check_cancelled(cancelled)
                band = slice(start,start+block)
                exchange(view[band],guide[band],confidence[band],step)
        if progress is not None:
            progress(index+1,5)
