import cv2
import numpy as np


def smooth(value):
    value=np.clip(value,0,1)
    return value*value*(3-2*value)


def peak_channel(rgb):
    return np.maximum(np.maximum(rgb[...,0],rgb[...,1]),rgb[...,2])


def shoulder(peak):
    excess=np.maximum(peak-.8,0)
    return np.minimum(peak,.8)+.2*(excess/(.2+excess))


def model_input(scene,bayer):
    if scene.max()<=(.8 if bayer else 1):return scene,None
    peak=peak_channel(scene)
    top=shoulder(peak) if bayer else np.minimum(peak,1)
    factor=np.divide(top,peak,out=np.ones_like(peak),where=peak>0)
    return np.minimum(scene*factor[...,None],1),peak


def finish(style,scene,peak,confidence):
    if peak is None:
        if confidence is None or not confidence.any():return style
        peak=peak_channel(scene)
    over=smooth(peak-1)
    if confidence is not None:
        floor=np.minimum(np.minimum(scene[...,0],scene[...,1]),scene[...,2])
        saturation=(peak-floor)/np.maximum(peak,1e-8)
        neutral=confidence.astype('f',copy=False)*np.float32(1/255)*(1-smooth((saturation-.10)/.15))
        weight=np.maximum(over,neutral)
    else:
        neutral=None;weight=over
    if not np.any(weight):return style
    top=shoulder(peak)
    reference=scene*(top/np.maximum(peak,1e-8))[...,None]
    if neutral is not None:reference+=(top[...,None]-reference)*neutral[...,None]
    return style+(reference-style)*weight[...,None]


def preview_evidence(cells,size):
    if cells is None:return None
    return cv2.resize(cells,size,interpolation=cv2.INTER_AREA if size[0]<=cells.shape[1] and size[1]<=cells.shape[0] else cv2.INTER_LINEAR)


def tile_evidence(cells,width,height,left,top,right,bottom):
    if cells is None:return None
    if cells.shape==(height,width):return cells[top:bottom,left:right]
    def axis(first,last,source,target):
        coord=np.clip((np.arange(first,last,dtype='f')+.5)*(source/target)-.5,0,source-1)
        lower=coord.astype(np.int32)
        return lower,np.minimum(lower+1,source-1),coord-lower.astype('f')
    col,next_col,frac_x=axis(left,right,cells.shape[1],width)
    row,next_row,frac_y=axis(top,bottom,cells.shape[0],height)
    def horizontal(rows):return cells[rows[:,None],col]*(1-frac_x)+cells[rows[:,None],next_col]*frac_x
    return horizontal(row)*(1-frac_y[:,None])+horizontal(next_row)*frac_y[:,None]
