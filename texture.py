from PIL import Image
import cv2
import numpy as np
import m9_grain

def source_iso(path):
    try:
        with Image.open(path) as image:
            exif=image.getexif();sub=exif.get_ifd(34665)
            for tag in (34855,34867,34866):
                value=sub.get(tag,exif.get(tag));value=value[0] if isinstance(value,(list,tuple)) and value else value
                if value and 0<float(value)<65535:return round(float(value))
    except (OSError,ValueError,KeyError,IndexError,TypeError,OverflowError,SyntaxError):pass
    return 400

def chroma(linear,amount,speed=None):
    if not amount:return linear
    encoded=np.where(linear<=.0031308,linear*12.92,1.055*np.maximum(linear,0)**(1/2.4)-.055);luma=encoded@np.array([.2126,.7152,.0722],'f')
    cb=(encoded[:,:,2]-luma)/1.8556;cr=(encoded[:,:,0]-luma)/1.5748;uv=np.stack((cb,cr),axis=2);codes=np.rint(np.clip(uv+.5,0,1)*65535).astype('uint16')
    strength=[float(20*amount)];smooth=speed.denoise(codes,strength) if speed else cv2.fastNlMeansDenoising(codes,strength,None,3,9,cv2.NORM_L1);change=(smooth.astype('f')-codes)/65535
    red=1.5748*change[:,:,1];blue=1.8556*change[:,:,0];delta=np.stack((red,-(.2126*red+.0722*blue)/.7152,blue),axis=2)
    factor=np.min(np.where(delta<0,encoded/np.maximum(-delta,1e-8),np.where(delta>0,np.maximum(1-encoded,0)/np.maximum(delta,1e-8),1)),axis=2).clip(0,1)
    rgb=encoded+delta*factor[:,:,None];return np.where(rgb<=.04045,rgb/12.92,((rgb+.055)/1.055).clip(0)**2.4)

def grain_strips(image,grade,iso):return m9_grain.strips(image,grade.grain_iso or iso,grade.grain/100.,73129)

def grain_preview(linear,grade,iso,full_scale):
    rgb=np.clip(np.where(linear<=.0031308,linear*12.92,1.055*np.maximum(linear,0)**(1/2.4)-.055),0,1)
    if grade.grain:
        pixels=np.rint(rgb*65535).astype('uint16');grain=np.concatenate(tuple(grain_strips(pixels,grade,iso)))
        rgb+=(grain.astype('f')-pixels)/(65535*max(1.,full_scale/1.7))
    return np.ascontiguousarray(np.rint(rgb*255).clip(0,255).astype('uint8'))

def preview_codes(codes,grade,iso,full_scale):
    if not grade.grain:return np.rint(codes/np.float32(257)).astype('uint8')
    result=np.empty(codes.shape,'uint8');top=0;attenuation=1/max(1.,full_scale/1.7)
    for grain in grain_strips(codes,grade,iso):
        bottom=top+len(grain);base=codes[top:bottom];result[top:bottom]=np.rint((base+(grain.astype('f')-base)*attenuation)/257).clip(0,255).astype('uint8');top=bottom
    return result
