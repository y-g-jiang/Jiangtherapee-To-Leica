import json
import io
import tempfile
import time
from pathlib import Path
import numpy as np
import tifffile
from PIL import Image
import engine
import inspection
import darkroom

def run(report):
    report=Path(report);result={}
    try:
        start=time.perf_counter()
        core=engine.raw_core.library();result['libraw']={'version':core.jtl_version().decode(),'commit':core.jtl_commit().decode()}
        with tempfile.TemporaryDirectory(prefix='jtl-check-') as directory:
            directory=Path(directory);path=directory/'测试 image.png'
            yy,xx=np.mgrid[:385,:577];source=np.stack(((xx//3+yy//4)%256,(xx//2)%256,(yy//2)%256),axis=2).astype('uint8');Image.fromarray(source).save(path)
            grade=darkroom.Grade(ev=-18,brightness=7,contrast=11,saturation=13,vibrance=5,shoulder=17,curves=((0,156,820,1842,4000,6400,10000),*darkroom.NEUTRAL[1:]));photo=engine.load(path);model=engine.Engine();preview,controls=model.predict(photo,grade)
            inspected,actual,fields=model.preview_pass(photo,grade,True)
            assert np.array_equal(preview,inspected) and all(np.array_equal(left,right) for left,right in zip(controls,actual))
            assert np.allclose(fields['regions'].sum(axis=1),1,atol=1e-5)
            for idx in range(3):assert np.allclose(fields[f'routing_{idx}'].sum(axis=-1),1,atol=1e-5)
            adjusted=engine.display(engine.prepare(photo.proxy,grade)[photo.crop]);cache=(grade,inspected,actual,adjusted,fields)
            for mode,(_,variants,_) in inspection.MODES.items():
                for idx in range(max(1,len(variants))):
                    layer=inspection.draw_layer(photo,cache,mode,idx,(.2,.7));assert layer.dtype==np.uint8 and layer.shape==((16,16,3) if mode=='routing' else preview.shape)
            result['inspection_views']=len(inspection.MODES)
            scan=model.analyze_preview(photo,grade);assert len(inspection.MASK_CYCLE)==len(set(inspection.MASK_CYCLE))==23
            assert all(np.array_equal(old,new) for old,new in zip(controls,scan[2])) and all(np.array_equal(fields[key],scan[4][key]) for key in engine.SIGNALS)
            sizes=[]
            for edge in engine.PREVIEW_EDGES:
                frame,selected,view,original=model.render_preview(photo,scan,edge,lambda:False);assert selected==edge and view.shape==original.shape and max(view.shape[:2])==min(edge,577) and frame[1].shape==preview.shape
                sizes.append(max(view.shape[:2]))
            assert np.array_equal(original,source);result['preview_edges']=sizes;result['spatial_masks']=len(inspection.MASK_CYCLE)
            out=engine.export(model,photo,grade,controls,directory,lambda *counts:None,lambda:False)
            with tifffile.TiffFile(out) as doc:
                data=doc.asarray();assert data.shape==source.shape and data.dtype==np.uint16 and 34675 in doc.pages[0].tags;icc=doc.pages[0].tags[34675].value
            assert np.ptp(data)>4096 and np.array_equal(np.asarray(Image.open(path)),source)
            with Image.open(out.with_suffix('.jpg')) as companion,io.BytesIO() as buffer:
                Image.fromarray(((data.astype('uint32')+128)//257).astype('uint8')).save(buffer,'JPEG',quality=80);buffer.seek(0)
                with Image.open(buffer) as reference:assert companion.quantization==reference.quantization and np.array_equal(np.asarray(companion),np.asarray(reference))
                assert companion.size==source.shape[1::-1] and companion.info['icc_profile']==icc
            lonely=out.with_name(out.stem+'-2.jpg');lonely.write_bytes(b'keep');repeat=engine.export(model,photo,grade,scan[2],directory,lambda *counts:None,lambda:False)
            assert repeat.stem==out.stem+'-3' and not lonely.with_suffix('.tif').exists() and lonely.read_bytes()==b'keep' and np.array_equal(data,tifffile.imread(repeat))
            before=set(directory.iterdir());stage=[]
            try:engine.export(model,photo,grade,controls,directory,lambda value,total:stage.append(value),lambda:bool(stage and stage[-1]>=97))
            except InterruptedError:pass
            else:raise AssertionError('Export did not cancel')
            assert before==set(directory.iterdir());result['export_pair']='16-bit TIFF and matching Q80 JPEG with ICC; collision and cancellation passed'
            ramp=np.linspace(0,4,4001,dtype='f')[:,None].repeat(3,axis=1);compressed=darkroom.apply(ramp,darkroom.Grade(shoulder=100))[:,0];assert np.all(np.diff(compressed)>0) and .40<compressed[1000]<.43
            result['linear_white_at_full_compression']=float(compressed[1000])
            assert model.profile=='vivid' and out.name.endswith('-Leica-Vivid.tif') and fields['features_12'].shape[-2:]==(27,36)
            classic=engine.Engine('classic');other,ccontrols,cfields=classic.preview_pass(photo,grade,True)
            assert cfields['features_12'].shape[-2:]==(18,24) and not np.array_equal(other,preview)
            cout=engine.export(classic,photo,grade,ccontrols,directory,lambda *counts:None,lambda:False)
            assert cout.name.endswith('-Leica-Classic.tif') and not np.array_equal(tifffile.imread(cout),data)
            result['profiles']=['vivid','classic']
            precision={};once=lambda *counts:None;never=lambda:False
            for candidate,control in ((model,controls),(classic,ccontrols)):
                exact=np.empty(source.shape,'uint16');fast=np.empty_like(exact);speed=engine.FullSpeed()
                candidate.tiles(photo,grade,control,source,False,exact,once,never,tile=192)
                candidate.tiles(photo,grade,control,source,False,fast,once,never,tile=192,speed=speed)
                delta=np.abs(exact.astype('i')-fast.astype('i'))/257;mae=float(delta.mean());p999=float(np.quantile(delta,.999));assert mae<.05 and p999<.55,(candidate.profile,mae,p999)
                precision[candidate.profile]={'graphics':bool(speed.sessions),'chroma_opencl':speed.opencl,'mean_error_u8':mae,'p999_error_u8':p999}
            result['full_export_precision']=precision
            from sensor import GRBG,demosaic
            from texture import chroma,grain_strips
            rng=np.random.default_rng(13);sensor=rng.uniform(.1,.8,(113,141)).astype('f')
            for row in range(2):
                for col in range(2):
                    pattern=np.roll(GRBG,(row,col),(0,1));small=demosaic(sensor,pattern,1,lambda:False,64);large=demosaic(sensor,pattern,1,lambda:False,256);assert small.shape==(113,141,3) and np.max(abs(small-large))<5e-5
                    speed=engine.FullSpeed();optimized=demosaic(sensor,pattern,1,never,64,speed=speed);assert np.max(abs(large-optimized))<.005
            result['bayer_graphics']=bool(speed.sessions)
            import highlights
            wb=np.array([2.25,1,1.875],'f');rows,cols=np.mgrid[:224,:288].astype('f');intensity=.075+4*np.maximum(0,1-((cols-139)/90)**2-((rows-113)/78)**2)
            camera=np.minimum(intensity[...,None]*np.array([1.02,.95,.72],'f'),wb);restored=highlights.recover(camera,wb,wb*65535,never)
            assert np.allclose(restored[113,139],[2.3078513,2.1494691,1.6290716],atol=4e-5);result['highlight_recovery']='RawTherapee 5.12, native camera RGB, Color Propagation, blur 0'
            gray=np.full((128,128,3),.35,'f');gray[:,:,0]+=rng.normal(0,.018,gray.shape[:2]);gray[:,:,2]+=rng.normal(0,.018,gray.shape[:2]);filtered=chroma(gray,70)
            assert (filtered[:,:,0]-filtered[:,:,2]).std()<(gray[:,:,0]-gray[:,:,2]).std()*.85 and np.max(np.abs((engine.encode(gray)-engine.encode(filtered))@engine.LUMA))<1e-5
            blank=np.full((145,160,3),28000,'uint16');grain=np.concatenate(tuple(grain_strips(blank,grade,800)));assert np.array_equal(grain,np.concatenate(tuple(grain_strips(blank,grade,800)))) and np.array_equal(grain[:,:,0],grain[:,:,1]) and grain.std()>0
            result['texture']='BayerNet four phases / tiling; chroma-only; M9 repeatability'
            photo=engine.load(out);assert photo.proxy.shape==(384,512,3)
            result.update(ok=True,output=list(source.shape[:2][::-1]),preview=list(preview.shape[:2][::-1]),seconds=round(time.perf_counter()-start,3))
    except Exception as exc:
        import traceback
        result.update(ok=False,error=str(exc),detail=traceback.format_exc())
    report.write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8');return 0 if result['ok'] else 1
