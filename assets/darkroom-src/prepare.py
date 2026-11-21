from pathlib import Path
import hashlib

root=Path(__file__).resolve().parent
def read(name,checksum):
    data=(root/'upstream'/name).read_bytes();assert hashlib.sha256(data).hexdigest()==checksum
    return data.decode('utf8')

def function(text,signature):
    start=text.index(signature);pos=text.index('{',start);depth=1
    while depth:
        pos+=1;depth+=(text[pos]=='{')-(text[pos]=='}')
    return text[start:pos+1]

basic=read('basicadj.c','07510ef0613d1f64d168dd60a2cf18147b634e5a287f4ec639833256fd9746c2')
curve=read('curve_tools.c','61c02e9dd5b887da96661fdb9c5e7dcb591d2c4c7d6f51b8aa336d3507a29e41')
math=read('imageop_math.h','1d745c6d1dde681c687feeab15a44fe3e9acd3d861ac54ecaff376fb53c4fb92')
header=(root/'upstream/curve_tools.h').read_text(encoding='utf8')
parts=[basic[:basic.index('*/')+2],curve[:curve.index('*/')+2],math[:math.index('*/')+2],header[header.index('typedef struct'):header.index('} CurveSample;')+len('} CurveSample;')]]
for signature in ('static inline float get_gamma(', 'static inline float get_lut_gamma(', 'static inline float hlcurve('):parts.append(function(basic,signature))
for signature in ('static inline void dt_iop_estimate_exp(', 'static inline float dt_iop_eval_exp('):parts.append(function(math,signature))
for signature in ('float *monotone_hermite_set(int n, float x[], float y[])\n','float catmull_rom_val(int n, float x[], float xval, float y[], float tangents[])\n','int CurveDataSample(CurveData *curve, CurveSample *sample)\n'):
    parts.append(function(curve,signature))
(root/'upstream.inc').write_text('\n\n'.join(parts),encoding='utf8')
pixel=basic.index('// saturation\n',basic.index('void process(dt_iop_module_t'))
(root/'saturation.inc').write_text(function(basic[pixel:],'if(process_saturation_vibrance)'),encoding='utf8')
