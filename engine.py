import io
import os
import shutil
import tempfile
from pathlib import Path
from dataclasses import dataclass

import cv2
import numpy as np
import onnxruntime as ort
import raw_core
import tifffile
from PIL import Image, ImageCms, ImageOps
import darkroom
from full_speed import FullSpeed
import sensor
import texture

ASSETS = Path(__file__).resolve().parent / 'assets'
RAW = set('dng arw nef nrw cr2 cr3 raf rw2 orf pef srw iiq 3fr erf'.split())
RASTER = set('jpg jpeg png tif tiff'.split())
LUMA = np.array([.2126, .7152, .0722], np.float32)
cv2.setNumThreads(min(4,os.cpu_count() or 1))

def encode(rgb):
    return np.where(rgb <= .0031308, 12.92*rgb, 1.055*np.maximum(rgb,0)**(1/2.4)-.055)

def decode(rgb):
    return np.where(rgb <= .04045, rgb/12.92, ((rgb+.055)/1.055)**2.4)

def display(rgb):
    return np.ascontiguousarray(np.rint(255*np.clip(encode(rgb),0,1)).astype('uint8'))

def signature(path):
    stat=path.stat()
    return stat.st_size,stat.st_mtime_ns

def orientation(arr,value):
    return {2:lambda v:v[:,::-1],3:lambda v:v[::-1,::-1],4:lambda v:v[::-1],5:lambda v:v.swapaxes(0,1),6:lambda v:np.rot90(v,-1),7:lambda v:v.swapaxes(0,1)[::-1,::-1],8:lambda v:np.rot90(v,1)}.get(value,lambda v:v)(arr)

def profile16(rgb,profile):
    if not profile:return rgb
    from PySide6.QtGui import QImage,QColorSpace
    source=QColorSpace.fromIccProfile(profile)
    if not source.isValid():raise ValueError('无法识别这张照片的色彩配置。')
    dest=QColorSpace(QColorSpace.SRgb)
    if source==dest:return rgb
    rgba=np.empty((*rgb.shape[:2],4),dtype='uint16');rgba[:,:,:3]=rgb;rgba[:,:,3]=65535
    image=QImage(rgba.data,rgba.shape[1],rgba.shape[0],rgba.strides[0],QImage.Format_RGBA64);image.setColorSpace(source)
    result=image.convertedToColorSpace(dest,QImage.Format_RGBA64)
    if result.isNull():raise ValueError('无法转换这张照片的色彩配置。')
    return np.asarray(result.constBits()).view('uint16').reshape(rgba.shape)[:,:,:3].copy()

def cache_camera(image,cancelled):
    if image.nbytes<=48*1024**2:return image
    try:
        if shutil.disk_usage(tempfile.gettempdir()).free<image.nbytes+128*1024**2:return None
        with tempfile.TemporaryFile() as store:
            for top in range(0,len(image),128):
                if cancelled():raise InterruptedError('已取消')
                store.write(memoryview(image[top:top+128]).cast('B'))
            store.flush();return np.memmap(store,dtype='f',mode='r',shape=image.shape)
    except InterruptedError:raise
    except OSError:return None

def pixels(path,quick,cancelled=lambda:False,progress=None,info=None,quick_edge=640,speed=None):
    kind=path.suffix.lower().lstrip('.')
    if kind in RAW:
        with raw_core.Reader(path) as raw:
            def retain(image,matrix):
                info['edge']=max(image.shape[:2]);cached=cache_camera(image,cancelled);info['camera']=(cached,matrix) if cached is not None else None
            arr=sensor.read(raw,quick,cancelled,progress,quick_edge,speed,retain if info is not None else None);bayer=arr is not None
            if not bayer:arr=raw.process(quick and max(raw.sizes.height,raw.sizes.width)//2>=quick_edge)
            if info is not None:info.setdefault('edge',max(raw.sizes.height,raw.sizes.width));info['method']='BayerNet' if bayer else 'LibRaw'
        return arr,True
    if kind not in RASTER:raise ValueError('请选择 JPEG、PNG、TIFF 或相机 RAW 文件。')
    if kind in ('tif','tiff'):
        with tifffile.TiffFile(path) as doc:
            page=doc.pages[0]
            if page.dtype==np.uint16 and page.photometric.name=='RGB' and page.samplesperpixel==3:
                try:arr=page.asarray()
                except ValueError:arr=None
                if arr is not None:
                    arr=np.moveaxis(arr,0,-1) if page.planarconfig==2 else arr
                    arr=profile16(arr,page.tags[34675].value if 34675 in page.tags else None)
                    return orientation(arr,int(page.tags[274].value) if 274 in page.tags else 1),False
    with Image.open(path) as opened:
        if info is not None:info['edge']=max(opened.size)
        if kind=='png':
            with path.open('rb') as stream:signature_bytes=stream.read(26)
            if len(signature_bytes)==26 and signature_bytes[24]==16:
                arr=cv2.imdecode(np.fromfile(path,dtype='uint8'),cv2.IMREAD_UNCHANGED)
                if arr is None:raise ValueError('无法解码这张 PNG。')
                if arr.ndim==2:arr=np.repeat(arr[:,:,None],3,axis=2)
                rgb=profile16(np.ascontiguousarray(arr[:,:,:3][:,:,::-1]),opened.info.get('icc_profile'))
                if arr.shape[2]==4:
                    alpha=arr[:,:,3:4].astype('f')/65535;rgb=np.rint(rgb*alpha+65535*(1-alpha)).astype('uint16')
                return orientation(rgb,opened.getexif().get(274,1)),False
        if quick and kind in ('jpg','jpeg'):opened.draft('RGB',(max(1024,quick_edge),)*2)
        prepared=ImageOps.exif_transpose(opened)
        if quick:prepared.thumbnail((max(1280,quick_edge),)*2,Image.Resampling.LANCZOS)
        profile=prepared.info.get('icc_profile')
        if 'A' in prepared.getbands() or 'transparency' in prepared.info:
            rgba=prepared.convert('RGBA'); background=Image.new('RGB',rgba.size,'white');background.paste(rgba,mask=rgba.getchannel('A'));prepared=background
        if profile:
            prepared=ImageCms.profileToProfile(prepared,ImageCms.ImageCmsProfile(io.BytesIO(profile)),ImageCms.createProfile('sRGB'),outputMode='RGB')
        return np.asarray(prepared.convert('RGB')),False

def linear(arr,already):
    if already and arr.dtype==np.float32:return arr
    rgb=arr.astype(np.float32)/np.iinfo(arr.dtype).max
    return rgb if already else decode(rgb)

@dataclass
class Photo:
    path: Path
    stamp: tuple
    proxy: np.ndarray
    crop: tuple
    iso:int=400
    full_scale:float=1.
    method:str='RGB'
    detail:tuple=None
    camera:tuple=None
    preview_master:np.ndarray=None

def load(path,cancelled=lambda:False):
    path=Path(path);stamp=signature(path);info={};raw=path.suffix.lower().lstrip('.') in RAW
    arr,already=pixels(path,True,cancelled,info=info,quick_edge=1600 if raw else 640,speed=FullSpeed() if raw else None)
    height,width=arr.shape[:2];tw,th=(512,384) if width>=height else (384,512)
    scale=min(tw/width,th/height);sw,sh=max(1,round(width*scale)),max(1,round(height*scale))
    if max(width,height)>1600:
        scale=min(1,1600/max(width,height));arr=cv2.resize(arr,(max(1,round(width*scale)),max(1,round(height*scale))),interpolation=cv2.INTER_AREA)
    small=cv2.resize(linear(arr,already),(sw,sh),interpolation=cv2.INTER_AREA)
    left,top=(tw-sw)//2,(th-sh)//2
    image=cv2.copyMakeBorder(small,top,th-sh-top,left,tw-sw-left,cv2.BORDER_REPLICATE)
    if signature(path)!=stamp:raise ValueError('照片在读取时已改变，请重新打开。')
    master=arr if info.get('method')=='BayerNet' else None
    return Photo(path,stamp,image,(slice(top,top+sh),slice(left,left+sw)),texture.source_iso(path),info.get('edge',max(height,width))/max(sw,sh),info.get('method','RGB'),camera=info.get('camera'),preview_master=master)

def prepare(rgb,grade,speed=None):return darkroom.apply(texture.chroma(rgb,grade.chroma,speed),grade)

PREVIEW_EDGES=(256,512,1024,1600)

def fit_edge(image,edge):
    height,width=image.shape[:2];scale=min(1.,edge/max(height,width))
    if scale==1.:return image
    return cv2.resize(image,(max(1,round(width*scale)),max(1,round(height*scale))),interpolation=cv2.INTER_AREA)

def preview_input(photo,edge,cancelled):
    if edge not in PREVIEW_EDGES:raise ValueError('无效的预览分辨率。')
    if signature(photo.path)!=photo.stamp:raise ValueError('原文件已改变，请重新打开。')
    base=photo.proxy[photo.crop];native_edge=round(photo.full_scale*max(base.shape[:2]));edge=min(edge,native_edge)
    if native_edge>=max(base.shape[:2]) and edge<=max(base.shape[:2]):return fit_edge(base,edge)
    if photo.detail is not None and photo.detail[0]==edge:return photo.detail[1]
    if photo.preview_master is not None:return fit_edge(photo.preview_master,edge)
    image,already=pixels(photo.path,True,cancelled,quick_edge=edge)
    if cancelled():raise InterruptedError('已取消')
    detail=np.ascontiguousarray(linear(fit_edge(image,edge),already))
    if signature(photo.path)!=photo.stamp:raise ValueError('原文件已改变，请重新打开。')
    photo.detail=(edge,detail);return detail

def nchw(arr):return np.ascontiguousarray(arr.transpose(2,0,1)[None],dtype=np.float32)

def hwc(arr):return np.ascontiguousarray(arr[0].transpose(1,2,0))

PROFILES={'vivid':'徕卡生动','classic':'徕卡经典'}
DEFAULT_PROFILE='vivid'
SIGNALS=['regions',*(f'features_{depth}' for depth in (3,6,9,12)),*(f'routing_{idx}' for idx in range(3))]

class Engine:
    def __init__(self,profile=DEFAULT_PROFILE):
        if profile not in PROFILES:raise ValueError(profile)
        self.profile=profile
        self.folder=ASSETS/'vivid' if profile=='vivid' else ASSETS
        self.sessions={}

    def session(self,key):
        if key not in self.sessions:
            if key in ('portrait','landscape'):self.sessions.pop('portrait' if key=='landscape' else 'landscape',None)
            opts=ort.SessionOptions();opts.intra_op_num_threads=min(4,os.cpu_count() or 1);opts.inter_op_num_threads=1
            opts.add_session_config_entry('session.intra_op.allow_spinning','0')
            self.sessions[key]=ort.InferenceSession(str(self.folder/(key+'.onnx')),opts,providers=['CPUExecutionProvider'])
        return self.sessions[key]

    def predict(self,photo,grade):
        preview,controls,_=self.preview_pass(photo,grade,False)
        return preview,controls

    def preview_pass(self,photo,grade,inspect,rgb=None):
        if rgb is None:rgb=prepare(photo.proxy,grade)
        key='landscape' if photo.proxy.shape[1]==512 else 'portrait'
        names=['graded_rgb','fine','prior','grid1','grid2'];extra=SIGNALS if inspect else []
        out,fine,prior,grid1,grid2,*fields=self.session(key).run(names+extra,{'linear_rgb':nchw(rgb)})
        clean=hwc(out)[photo.crop];signals=dict(zip(extra,fields)) if inspect else None
        if inspect:signals['clean']=display(clean)
        return texture.grain_preview(clean,grade,photo.iso,photo.full_scale),(hwc(fine),hwc(prior),grid1,grid2),signals

    def analyze_preview(self,photo,grade,options=None):
        if options is not None and options.terminate:raise InterruptedError('已取消')
        rgb=prepare(photo.proxy,grade);key='landscape' if rgb.shape[1]==512 else 'portrait'
        if options is not None and options.terminate:raise InterruptedError('已取消')
        rendered,fine,prior,grid1,grid2,*fields=self.session(key).run(['graded_rgb','fine','prior','grid1','grid2',*SIGNALS],{'linear_rgb':nchw(rgb)},options)
        source=display(rgb[photo.crop]);codes=np.rint(np.clip(encode(hwc(rendered)[photo.crop]),0,1)*65535).astype('uint16')
        small=np.rint(codes/np.float32(257)).astype('uint8');return grade,small,(hwc(fine),hwc(prior),grid1,grid2),source,dict(zip(SIGNALS,fields),proxy_codes=codes)

    def render_preview(self,photo,scan,edge,cancelled,options=None):
        if cancelled():raise InterruptedError('已取消')
        grade,_,controls,source,fields=scan;image=preview_input(photo,edge,cancelled);height,width=image.shape[:2];base_size=source.shape[1::-1];native_edge=photo.full_scale*max(base_size)
        if native_edge>=max(base_size) and edge<=max(base_size):codes=fit_edge(fields['proxy_codes'],edge)
        else:
            codes=np.empty((height,width,3),'uint16');self.tiles(photo,grade,controls,image,True,codes,lambda *counts:None,cancelled,options=options)
        if cancelled():raise InterruptedError('已取消')
        method=cv2.INTER_AREA if max(height,width)>=max(base_size) else cv2.INTER_LINEAR
        clean=cv2.resize(codes,base_size,interpolation=method)
        view=texture.preview_codes(codes,grade,photo.iso,native_edge/max(height,width));small=cv2.resize(view,base_size,interpolation=method)
        return (grade,small,controls,source,dict(fields,clean=np.rint(clean/257.).astype('uint8'))),edge,view,display(image)

    def tiles(self,photo,grade,controls,image,already,dest,progress,cancelled,tile=384,options=None,speed=None):
        fine,prior,grid1,grid2=controls
        height,width=image.shape[:2];ph,pw=photo.proxy.shape[:2];ys,xs=photo.crop
        sx=(xs.stop-xs.start)/width;sy=(ys.stop-ys.start)/height
        xmin=-round(xs.start/sx);ymin=-round(ys.start/sy)
        xmax=width+round((pw-xs.stop)/sx);ymax=height+round((ph-ys.stop)/sy)
        total=((width+tile-1)//tile)*((height+tile-1)//tile);count=0
        halo=(16 if self.profile=='vivid' else 28) if speed else 32
        atlas=self.folder/'atlas.onnx';maps=dict(fine_grid=nchw(fine),prior_grid=nchw(prior)) if speed and speed.available(atlas) else None
        for top in range(0,height,tile):
            for left in range(0,width,tile):
                if cancelled():raise InterruptedError('已取消')
                bottom,right=min(height,top+tile),min(width,left+tile)
                first=max(xmin,left-halo);last=min(xmax,right+halo);upper=max(ymin,top-halo);lower=min(ymax,bottom+halo)
                xx=np.arange(first,last,dtype=np.int32);yy=np.arange(upper,lower,dtype=np.int32)
                sample=image[upper:lower,first:last] if 0<=first and last<=width and 0<=upper and lower<=height else image[yy.clip(0,height-1)[:,None],xx.clip(0,width-1)[None,:]]
                source=prepare(linear(sample,already),grade,speed)
                px=(xs.start+(xx.astype('f')+.5)*sx)/pw;py=(ys.start+(yy.astype('f')+.5)*sy)/ph
                pos=np.empty((1,len(yy),len(xx),2),dtype='f');pos[0,:,:,0]=2*(px-.5*sx/pw)-1;pos[0,:,:,1]=(2*(py-.5*sy/ph)-1)[:,None]
                inputs=dict(source=nchw(source),grid1=grid1,grid2=grid2,position=pos);result=None
                if maps and speed.available(atlas):result=speed.run(atlas,dict(inputs,**maps,uv_x=px,uv_y=py))
                if result is None:result=self.session('tile').run(None,dict(inputs,fine=nchw(sample_map(fine,px,py)),prior=nchw(sample_map(prior,px,py))),options)[0]
                central=result[0,:,top-upper:bottom-upper,left-first:right-first].transpose(1,2,0)
                dest[top:bottom,left:right]=np.rint(np.clip(encode(central),0,1)*65535).astype('uint16')
                count+=1;progress(count,total)

def sample_map(field,px,py):
    height,width=field.shape[:2];xx=np.clip(px*width-.5,0,width-1);yy=np.clip(py*height-.5,0,height-1)
    base_x=xx.astype('i');base_y=yy.astype('i');nx=np.minimum(base_x+1,width-1);ny=np.minimum(base_y+1,height-1)
    dx=(xx-base_x).astype('f')[None,:,None];dy=(yy-base_y).astype('f')[:,None,None]
    first=int(base_y[0]);last=int(ny[-1]);slab=field[first:last+1]
    rows=slab[:,base_x]*(1-dx)+slab[:,nx]*dx
    return rows[base_y-first]*(1-dy)+rows[ny-first]*dy

def export(engine,photo,grade,controls,directory,progress,cancelled):
    if signature(photo.path)!=photo.stamp:raise ValueError('原文件已改变，请重新打开后再导出。')
    if cancelled():raise InterruptedError('已取消')
    raw=photo.path.suffix.lower().lstrip('.') in RAW;front=45 if raw else 0;finish=92 if grade.grain else 95
    speed=FullSpeed()
    if photo.camera is None:image,already=pixels(photo.path,False,cancelled,lambda done,total:progress(round(front*done/total),100),speed=speed)
    else:image=sensor.to_working(*photo.camera,None,cancelled);already=True;front=0
    height,width=image.shape[:2];speed.sessions.clear()
    profile=ImageCms.ImageCmsProfile(ImageCms.createProfile('sRGB')).tobytes()
    with tempfile.TemporaryDirectory(prefix='.jtl-',dir=directory) as scratch:
        temp=Path(scratch)/'render.tif';jpeg=temp.with_suffix('.jpg')
        dest=tifffile.memmap(temp,shape=(height,width,3),dtype='uint16',photometric='rgb',metadata=None,extratags=[(34675,7,len(profile),profile,False)])
        try:
            engine.tiles(photo,grade,controls,image,already,dest,lambda done,total:progress(front+round((finish-front)*done/total),100),cancelled,speed=speed)
            del image
            if grade.grain:
                top=0
                for strip in texture.grain_strips(dest,grade,photo.iso):
                    if cancelled():raise InterruptedError('已取消')
                    dest[top:top+len(strip)]=strip;top+=len(strip);progress(finish+round((95-finish)*top/height),100)
            dest.flush()
            with Image.new('RGB',(width,height)) as companion:
                for top in range(0,height,128):
                    if cancelled():raise InterruptedError('已取消')
                    band=((dest[top:top+128].astype('uint32')+128)//257).astype('uint8');companion.paste(Image.fromarray(band),(0,top))
                progress(97,100);companion.save(jpeg,'JPEG',quality=80,icc_profile=profile)
        finally:dest._mmap.close();del dest
        if cancelled():raise InterruptedError('已取消')
        if signature(photo.path)!=photo.stamp:raise ValueError('原文件已改变，未保存成片。')
        for index in range(1,10001):
            suffix='' if index==1 else f'-{index}'
            target=Path(directory)/(photo.path.stem+'-Leica-'+engine.profile.title()+suffix+'.tif')
            other=target.with_suffix('.jpg');reserved=[]
            try:
                for name in (target,other):
                    try:handle=os.open(name,os.O_CREAT|os.O_EXCL|os.O_WRONLY)
                    except FileExistsError:break
                    reserved.append(name);os.close(handle)
                if len(reserved)!=2:continue
                if cancelled():raise InterruptedError('已取消')
                os.replace(temp,target);os.replace(jpeg,other);reserved.clear();progress(100,100);return target
            finally:
                for name in reserved:name.unlink(missing_ok=True)
        raise OSError('输出目录中同名成片太多，请选择其他目录。')
