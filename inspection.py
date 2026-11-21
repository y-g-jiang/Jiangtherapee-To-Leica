import cv2
import numpy as np

PALETTE=np.array([(66,218,193),(250,173,78),(176,139,252),(245,107,131)],np.float32)
AQUA=PALETTE[0];GOLD=PALETTE[1];BLUE=np.array([89,164,255],np.float32)
MODES={
    'regions':('调色分区',['四色合看','分区 A · 青','分区 B · 金','分区 C · 紫','分区 D · 红'],'四种颜色随调色权重混合，不代表物体类别。拖动中线，对照右侧成片。'),
    'features':('特征回声',[f'第 {depth} 层' for depth in (3,6,9,12)],'点照片取样。越青，表示这一层的特征越像取样处；不表示同一种物体。'),
    'guide':('局部引导',[f'通道 {number:02d}' for number in range(1,14)],'蓝为负、金为正：语义分支怎样偏移查色位置，不代表压暗或提亮。'),
    'routing':('通道交互',['第一阶段','第二阶段','第三阶段'],'每行是一个语义通道，每列是一个图像通道。悬停读权重；方格不对应照片位置。'),
    'portrait':('人物与边界',['人物响应','边界响应'],'显示细化前的人物或边界响应。颜色越亮，响应越强。'),
    'light':('明暗变化',[],'金色提亮，蓝色压暗。比较调节后的输入与成片，这是结果差值，不是网络层。')}


MASK_CYCLE=(('regions',1),('portrait',1),('features',0),('guide',0),('regions',2),('guide',1),('features',1),('guide',2),('portrait',0),('guide',3),('regions',3),('guide',4),('features',2),('guide',5),('regions',4),('guide',6),('features',3),*(('guide',idx) for idx in range(7,13)))

def byte_image(value):return np.ascontiguousarray(np.rint(value).clip(0,255).astype(np.uint8))


def projected(field,photo):
    height,width=photo.proxy.shape[:2]
    return cv2.resize(field,(width,height),interpolation=cv2.INTER_LINEAR)[photo.crop]


def echo(features,photo,anchor):
    rows,cols=photo.crop;height,width=photo.proxy.shape[:2];channels,grid_h,grid_w=features.shape
    col=min(grid_w-1,int((cols.start+.5+anchor[0]*(cols.stop-cols.start-1))*grid_w/width))
    row=min(grid_h-1,int((rows.start+.5+anchor[1]*(rows.stop-rows.start-1))*grid_h/height))
    vector=features[:,row,col];dots=np.einsum('chw,c->hw',features,vector)
    return dots/np.maximum(np.linalg.norm(features,axis=0)*np.linalg.norm(vector),1e-8)


def draw_layer(photo,cache,mode,index,anchor):
    _,preview,controls,source,fields=cache
    if mode=='routing':
        weight=fields[f'routing_{index}'][0];alpha=np.clip(weight/.20,0,1)[...,None]
        return byte_image(np.array([24,37,44])*(1-alpha)+AQUA*alpha)
    ground=(cv2.cvtColor(preview,cv2.COLOR_RGB2GRAY).astype(np.float32)*.66+9)[:,:,None]
    if mode=='regions':
        weights=projected(fields['regions'][0].transpose(1,2,0),photo)
        if index==0:
            tint=weights**3;color=(tint @ PALETTE)/np.maximum(tint.sum(axis=2,keepdims=True),1e-8);strength=np.sqrt(np.clip((weights.max(axis=2)-.25)/.75,0,1))
        else:color=PALETTE[index-1];strength=weights[:,:,index-1]
    elif mode=='features':
        values=echo(fields[f'features_{(3,6,9,12)[index]}'][0],photo,anchor)
        strength=projected(np.clip(values,0,1)**1.5,photo);color=AQUA
    elif mode=='portrait':
        logits=projected(controls[0][:,:,8+index],photo)
        strength=1/(1+np.exp(-np.clip(logits,-20,20)));color=AQUA if index==0 else GOLD
    elif mode=='guide':
        signal=projected(controls[0][:,:,10+index],photo);strength=np.sqrt(np.clip(np.abs(signal)/.15,0,1));color=np.where(signal[:,:,None]>=0,GOLD,BLUE)
    elif mode=='light':
        signal=(fields.get('clean',preview).astype(np.float32)-source) @ np.array([.2126,.7152,.0722],np.float32)
        strength=np.clip(np.abs(signal)/48,0,1);color=np.where(signal[:,:,None]>=0,GOLD,BLUE)
    else:raise ValueError(mode)
    alpha=strength[:,:,None]*.9
    return byte_image(ground*(1-alpha)+color*alpha)
