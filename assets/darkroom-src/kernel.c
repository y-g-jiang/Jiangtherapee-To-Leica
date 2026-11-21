#if defined(JTL_CROSS)
typedef __SIZE_TYPE__ size_t;
typedef unsigned char uint8_t;
typedef unsigned short uint16_t;
typedef unsigned int uint32_t;
extern void *calloc(size_t,size_t);
extern void free(void *);
extern float powf(float,float),exp2f(float),logf(float),log1pf(float),sqrtf(float),fabsf(float);
#define NULL ((void *)0)
#else
#include <stddef.h>
#include <stdint.h>
#include <stdlib.h>
#include <math.h>
#endif
#ifdef _WIN32
#define API __declspec(dllexport)
#else
#define API __attribute__((visibility("default")))
#endif
#define EPSILON (2 * __FLT_MIN__)
#define CT_ERROR 100
#define CT_SUCCESS 0
#define MAX_ANCHORS 20
#define CLAMP(value,low,high) ((value)<(low)?(low):((value)>(high)?(high):(value)))
#define interpolate_set(n,x,y,type) monotone_hermite_set(n,x,y)
#define interpolate_val(n,x,v,y,m,type) catmull_rom_val(n,x,v,y,m)
#include "upstream.inc"

API int make_curve(const float *knots,const float *values,int count,uint16_t *table,float *coeff){
    if(count<2 || count>20)return CT_ERROR;
    CurveData curve={0};curve.m_max_x=curve.m_max_y=1;curve.m_numAnchors=count;curve.m_spline_type=2;
    for(int index=0;index<count;index++){
        curve.m_anchors[index].x=knots[index];curve.m_anchors[index].y=values[index];
    }
    CurveSample sample={65536,65536,table};int status=CurveDataSample(&curve,&sample);
    if(status)return status;
    float fit_x[]={.7f,.8f,.9f,1.f},fit_y[4];
    for(int index=0;index<4;index++)fit_y[index]=table[CLAMP((int)(fit_x[index]*65536),0,65535)]*(1.f/65536);
    dt_iop_estimate_exp(fit_x,fit_y,4,coeff);return 0;
}

static inline float sample_curve(float value,const uint16_t *table,const float *coeff){
    if(value<=0)return table[0]*(1.f/65536);
    return value<1 ? table[CLAMP((int)(value*65536),0,65535)]*(1.f/65536) : dt_iop_eval_exp(coeff,value);
}

API void make_gamma(float brightness,float *table){
    float amount=brightness*2.f;float gamma=amount>=0 ? 1.f/(1.f+amount) : 1.f-amount;
    for(int index=0;index<65536;index++)table[index]=get_gamma(index*(1.f/65536),gamma);
}

API void process_rgb(const float *input,float *out,size_t count,const float *params,const float *lut,const uint16_t *tables,const float *coeff,int mask){
    const float scale=1.f/exp2f(-params[0]),brightness=params[1]*2.f,gamma=brightness>=0?1.f/(1.f+brightness):1.f-brightness;
    const float contrast=1.f+params[2],saturation=1.f+params[3],vibrance=params[4]/1.4f,hlcomp=params[5]/100.f;
    const int process_saturation_vibrance=params[3]!=0 || params[4]!=0;
    for(size_t k=0;k<count*3;k+=3){
        for(int channel=0;channel<3;channel++)out[k+channel]=input[k+channel]*scale;
        if(hlcomp>0){
            float lum=.2126f*out[k]+.7152f*out[k+1]+.0722f*out[k+2];
            if(lum>0){
                float gain=hlcurve(lum,hlcomp,.9f),base=lum*gain;
                if(hlcomp>.5f && base>.3f){
                    float amount=(hlcomp-.5f)*2.f,excess=base-.3f;
                    gain=(.3f+excess*hlcurve(excess,18.f*amount*amount,1.f))/lum;
                }
                for(int channel=0;channel<3;channel++)out[k+channel]*=gain;
            }
        }
        if(brightness)for(int channel=0;channel<3;channel++)if(out[k+channel]>0)out[k+channel]=get_lut_gamma(out[k+channel],gamma,lut);
        if(params[2]){
            float lum=.2126f*out[k]+.7152f*out[k+1]+.0722f*out[k+2];
            if(lum>0){float gain=powf(lum*(1.f/.1842f),contrast)*.1842f/lum;for(int channel=0;channel<3;channel++)out[k+channel]*=gain;}
        }
#include "saturation.inc"
        if(mask&1){
            float lum=.2126f*out[k]+.7152f*out[k+1]+.0722f*out[k+2];
            if(lum>0){float gain=sample_curve(lum,tables,coeff)/lum;for(int channel=0;channel<3;channel++)out[k+channel]*=gain;}
        }
        for(int channel=0;channel<3;channel++){
            if(mask&(2<<channel))out[k+channel]=sample_curve(out[k+channel],tables+(channel+1)*65536,coeff+(channel+1)*3);
            if(out[k+channel]<0)out[k+channel]=0;
        }
    }
}
