import os
from functools import lru_cache
from pathlib import Path

import cv2
import numpy as np
import onnxruntime as ort
import highlights

SRGB_XYZ=np.array([[.4124564,.3575761,.1804375],[.2126729,.7151522,.0721750],[.0193339,.1191920,.9503041]])
GRBG=np.array([[1,0],[2,1]])

@lru_cache(maxsize=1)
def network():
    options=ort.SessionOptions();options.intra_op_num_threads=min(4,os.cpu_count() or 1);options.inter_op_num_threads=1;options.add_session_config_entry('session.intra_op.allow_spinning','0')
    return ort.InferenceSession(str(Path(__file__).resolve().parent/'assets/bayer.onnx'),options,providers=['CPUExecutionProvider'])

def demosaic(plane,pattern,gain,cancelled,core=384,progress=None,speed=None):
    height,width=plane.shape;halo=36 if speed else 48
    dy,dx=next((row,col) for row in range(2) for col in range(2) if np.array_equal(np.roll(pattern,(row,col),(0,1)),GRBG))
    canonical=np.pad(plane,((dy,dy+height%2),(dx,dx+width%2)),mode='reflect')
    padded=np.pad(canonical,halo,mode='reflect');del canonical
    model_path=Path(__file__).resolve().parent/'assets/bayer.onnx'
    rows,cols=np.subtract(padded.shape,2*halo);image=np.empty((rows,cols,3),'f');count=0;total=((rows+core-1)//core)*((cols+core-1)//core)
    for top in range(0,rows,core):
        for left in range(0,cols,core):
            if cancelled():raise InterruptedError('已取消')
            block=padded[top:min(top+core,rows)+2*halo,left:min(left+core,cols)+2*halo];hh,ww=block.shape
            shape=(core+2*halo,core+2*halo) if speed and speed.apple and speed.available(model_path) else (hh,ww);sparse=np.zeros((1,3,*shape),'f')
            for row in range(2):
                for col in range(2):sparse[0,GRBG[row,col],row:hh:2,col:ww:2]=block[row::2,col::2]
            inputs={'mosaic':sparse};result=speed.run(model_path,inputs) if speed else None
            if result is None:result=network().run(None,inputs)[0]
            result=result[0,:,halo:hh-halo,halo:ww-halo].transpose(1,2,0)
            rgb=np.maximum(result,0)**2.2*gain;image[top:top+rgb.shape[0],left:left+rgb.shape[1]]=rgb;count+=1
            if progress:progress(count,total)
    return image[dy:dy+height,dx:dx+width]

def camera_mosaic(plane,pat,colors,black,white,wb,gain,cancelled):
    result=np.empty(plane.shape,'f');observed=np.zeros(3,'f')
    for row,col in np.ndindex(2,2):
        if cancelled():raise InterruptedError('已取消')
        index=pat[row,col];color=colors[row,col];site=plane[row::2,col::2];dest=result[row::2,col::2];span=white[index]-black[index]
        if not np.isfinite(span) or span<=0:raise ValueError('无效的 RAW 黑白电平。')
        observed[color]=max(observed[color],(float(site.max())-black[index])/span*wb[color]*65535)
        np.subtract(site,black[index],out=dest,dtype='f');dest*=wb[index]/(span*gain)
    np.maximum(result,0,out=result);np.power(result,1/2.2,out=result);np.minimum(result,1,out=result)
    return result,observed

def read(raw,quick,cancelled,progress=None,quick_edge=640,speed=None,retain=None):
    sizes=raw.sizes;pattern=raw.raw_pattern;desc=raw.color_desc.rstrip(b'\0')
    if pattern is None or pattern.shape!=(2,2) or desc not in (b'RGBG',b'RGB') or abs(sizes.pixel_aspect-1)>1e-4 or (sizes.iheight,sizes.iwidth)!=(sizes.height,sizes.width):return None
    plane=raw.raw_image_visible
    if plane.ndim!=2:return None
    pat=np.array([[raw.raw_color(sizes.top_margin+row,sizes.left_margin+col) for col in range(2)] for row in range(2)])
    colors=np.array([b'RGB'.index(desc[item]) for item in pat.ravel()]).reshape(2,2)
    if not any(np.array_equal(np.roll(colors,(row,col),(0,1)),GRBG) for row in range(2) for col in range(2)):return None
    black=np.asarray(raw.black_level_per_channel,'f');white=np.asarray(raw.camera_white_level_per_channel or [raw.white_level]*4,'f');wb=np.asarray(raw.camera_whitebalance,'f')
    if not np.all(np.isfinite(wb[:3]) & (wb[:3]>0)):wb=np.asarray(raw.daylight_whitebalance,'f')
    if not np.all(np.isfinite(wb[:3]) & (wb[:3]>0)):raise ValueError('缺少可用的相机白平衡。')
    wb=wb/wb[1];wb[3]=wb[3] if np.isfinite(wb[3]) and wb[3]>0 else 1.;gain=float(wb.max());matrix=raw.color_matrix[:,:3].copy()
    if not np.isfinite(matrix).all() or abs(np.linalg.det(matrix))<1e-6:
        converted=raw.rgb_xyz_matrix[:3].astype('d')@SRGB_XYZ;normalized=converted/np.where(abs(converted.sum(1,keepdims=True))>1e-8,converted.sum(1,keepdims=True),1)
        if not np.isfinite(normalized).all() or abs(np.linalg.det(normalized))<1e-6:raise ValueError('缺少可用的相机色彩矩阵。')
        matrix=np.linalg.inv(normalized).astype('f')
    signal,observed=camera_mosaic(plane,pat,colors,black,white,wb,gain,cancelled)
    image=demosaic(signal,colors,gain,cancelled,progress=progress,speed=speed);del signal
    left,top,width,height=raw.visible_crop;left-=sizes.left_margin;top-=sizes.top_margin
    if width>0 and height>0 and 0<=left<=sizes.width-width and 0<=top<=sizes.height-height:image=image[top:top+height,left:left+width]
    flip=int(sizes.flip)
    if flip&4:image=image.transpose(1,0,2)
    if (flip & (1 if flip&4 else 2)):image=image[::-1]
    if (flip & (2 if flip&4 else 1)):image=image[:,::-1]
    image=np.ascontiguousarray(image);highlights.recover(image,wb,observed,cancelled)
    if retain:retain(image,matrix)
    return to_working(image,matrix,quick_edge if quick else None,cancelled,inplace=retain is None)

def to_working(image,matrix,edge,cancelled,inplace=False):
    if edge and max(image.shape[:2])>edge:
        scale=edge/max(image.shape[:2]);image=cv2.resize(image,(max(1,round(image.shape[1]*scale)),max(1,round(image.shape[0]*scale))),interpolation=cv2.INTER_AREA);inplace=True
    output=image if inplace else np.empty_like(image)
    for top in range(0,len(image),128):
        if cancelled():raise InterruptedError('已取消')
        rows=image[top:top+128];np.maximum(rows@matrix.T,0,out=output[top:top+len(rows)])
    return output
