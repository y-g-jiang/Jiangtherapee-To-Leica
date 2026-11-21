import ctypes
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path
import numpy as np

root=Path(__file__).resolve().parents[1];sys.path.insert(0,str(root))
import darkroom as dr

up=root/'assets/darkroom-src/upstream';basic=(up/'basicadj.c').read_text(encoding='utf-8')
def function(name):
    start=basic.index('static inline float '+name+'(');end=basic.index('\n}',start)+2;return basic[start:end]

pre=r'''
#include <math.h>
#include <stdint.h>
#include <stdlib.h>
#include "curve_tools.h"
#define API __declspec(dllexport)
#define CLAMP(v,a,b) ((v)<(a)?(a):(v)>(b)?(b):(v))
#define DT_OMP_FOR()
#define DT_RGB_NORM_NONE 0
#define exposure2white(x) exp2f(-(x))
#define dt_ioppr_get_rgb_matrix_luminance(rgb,...) fixed_profile_y(rgb)
#define dt_camera_rgb_luminance(rgb) fixed_profile_y(rgb)
#define dt_rgb_norm(rgb,...) fixed_profile_y(rgb)
static inline float fixed_profile_y(const float *rgb){return .2126f*rgb[0]+.7152f*rgb[1]+.0722f*rgb[2];}
API int reference_curve(float *knots,float *levels,uint16_t *table){
 CurveData curve={0};curve.m_spline_type=MONOTONE_HERMITE;curve.m_numAnchors=7;curve.m_max_x=curve.m_max_y=1;
 for(int idx=0;idx<7;idx++){curve.m_anchors[idx].x=knots[idx];curve.m_anchors[idx].y=levels[idx];}
 CurveSample sample={65536,65536,table};return CurveDataSample(&curve,&sample);
}
'''
params=r'''
API void reference_basic(const float *ivoid,float *ovoid,size_t count,const float *args){
 struct {float exposure,brightness,contrast,saturation,vibrance,hlcompr,black_point,middle_grey,hlcomprthresh;int preserve_colors;} settings={args[0],args[1],args[2],args[3],args[4],args[5],0,0,0,1},*p=&settings;
 struct {float lut_gamma[65536],lut_contrast[65536];} *d=calloc(1,sizeof(*d));
 const void *work_profile=NULL;const int ch=4;struct {size_t width,height;} roi={count,1},*roi_out=&roi;
'''
build_lut=basic[basic.index('  const float brightness',basic.index('void commit_params(')):basic.index('\n}',basic.index('void commit_params('))]
payload=basic[basic.index('  const float black_point = p->black_point;',basic.index('void process(')):basic.index('\n}',basic.index('  const float black_point = p->black_point;',basic.index('void process(')))]
src=pre+'\n'.join(function(name) for name in ('get_gamma','get_lut_gamma','get_contrast','get_lut_contrast','hlcurve'))+params+'{'+build_lut+'}\n'+payload+'\nfree(d);}\n'
def run(folder):
    folder=Path(folder);source=folder/'oracle.c';source.write_text(src,encoding='utf-8');dll=folder/'oracle.dll';compiler=os.getenv('CC',r'C:\Program Files\LLVM\bin\clang.exe')
    subprocess.run([compiler,'-O2','-ffp-contract=off','-shared','-I'+str(up),str(up/'curve_tools.c'),str(source),'-o',str(dll)],cwd=folder,check=True)
    oracle=ctypes.CDLL(str(dll));oracle.reference_basic.argtypes=[dr.fp,dr.fp,ctypes.c_size_t,dr.fp];oracle.reference_curve.argtypes=[dr.fp,dr.fp,dr.up];oracle.reference_basic.restype=None
    rng=np.random.default_rng(20261121);knots=np.array(dr.KNOTS,'f')/10000;maximum=0
    for idx in range(32):
        points=sorted(rng.integers(0,10001,5));levels=(0,*points,10000) if idx else (0,0,0,1842,4000,10000,10000);expected=np.empty(65536,'uint16');values=np.array(levels,'f')/10000
        assert oracle.reference_curve(dr.ptr(knots),dr.ptr(values),dr.ptr(expected,dr.up))==0
        table,_=dr.curve(tuple(levels));assert np.array_equal(expected,table) and np.diff(table.astype('i4')).min()>=-1
    pixels=rng.random((12000,4),dtype=np.float32)**3*2;pixels[:3000,:3]=np.linspace(0,2,3000,dtype='f')[:,None];pixels[:7,:3]=np.array([[0,0,0],[1,1,1],[1.01]*3,[.1842]*3,[1,0,0],[0,1,0],[0,0,1]])
    for grade in [dr.Grade(ev=100),dr.Grade(brightness=-50),dr.Grade(brightness=65),dr.Grade(contrast=-95),dr.Grade(saturation=-100),dr.Grade(vibrance=100),dr.Grade(shoulder=100),dr.Grade(111,-17,35,22,-36,45),dr.Grade(-80,35,-17,-18,51,0)]:
        args=np.array([grade.ev/100,grade.brightness/100,grade.contrast/100,grade.saturation/100,grade.vibrance/100,grade.shoulder],'f');expected=np.empty_like(pixels);oracle.reference_basic(dr.ptr(pixels),dr.ptr(expected),len(pixels),dr.ptr(args));actual=dr.apply(pixels[:,:3],grade);ref=np.maximum(0,expected[:,:3]);
        if grade.shoulder==100:
            base=ref@np.array([.2126,.7152,.0722],'f');bright=base>.3;ref[bright]*=((.3+np.log1p(18*(base[bright]-.3))/18)/base[bright])[:,None]
        maximum=max(maximum,float(np.abs(actual-ref).max()));assert np.allclose(actual,ref,rtol=5e-6,atol=3e-6)
    assert np.array_equal(dr.apply(pixels[:,:3],dr.DEFAULT),pixels[:,:3]);table,coeff=dr.curve((0,156,625,1842,4000,6400,10000));identity,_=dr.curve(dr.KNOTS);assert np.array_equal(identity[:4000],table[:4000]);grade=dr.Grade(curves=((0,156,625,1842,4000,6400,10000),*dr.NEUTRAL[1:]));high=np.array([[1.1,1.1,1.1],[2,2,2]],'f');actual=dr.apply(high,grade);assert np.allclose(actual,coeff[1]*(high*coeff[0])**coeff[2],rtol=1e-6) and actual[1,0]>actual[0,0]
    extreme=dr.Grade(300,-100,200,100,100,0,((0,0,0,0,0,0,10000),)*4);bounded=dr.apply(pixels[:,:3],extreme);assert np.isfinite(bounded).all() and bounded.max()==64
    print(json.dumps({'upstream_tag':'release-5.2.1','curve_tables':32,'samples_per_table':65536,'mismatching_curve_entries':0,'basic_settings':9,'rgb_samples_per_setting':len(pixels),'maximum_basic_abs_error':maximum,'hdr_extrapolation':'passed','extreme_model_input_guard':'passed'},indent=2));del oracle

if __name__=='__main__':
    if len(sys.argv)>1:run(sys.argv[1])
    else:
        with tempfile.TemporaryDirectory() as folder:subprocess.run([sys.executable,__file__,folder],check=True)
