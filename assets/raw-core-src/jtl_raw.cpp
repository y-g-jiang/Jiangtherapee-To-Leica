#include "libraw/libraw.h"
#include <cstring>
#include <new>

#ifdef _WIN32
#define JTL_API extern "C" __declspec(dllexport)
using PathChar=wchar_t;
#else
#define JTL_API extern "C" __attribute__((visibility("default")))
using PathChar=char;
#endif

struct Reader: LibRaw { using LibRaw::adjust_bl; };
struct Metadata {
    unsigned raw_height,raw_width,height,width,top,left,iheight,iwidth,pitch;
    int flip,bayer[4];double aspect;char desc[5];
    unsigned black[4],white[4],maximum;
    float camera[4],daylight[4],matrix[12],xyz[12];
};

JTL_API const char* jtl_version(){return LibRaw::version();}
JTL_API const char* jtl_commit(){return JTL_COMMIT;}
JTL_API void jtl_crop(Reader* reader,unsigned* out){
    const auto& crop=reader->imgdata.sizes.raw_inset_crops[0];
    out[0]=crop.cleft;out[1]=crop.ctop;out[2]=crop.cwidth;out[3]=crop.cheight;
}
JTL_API const char* jtl_error(int code){return libraw_strerror(code);}
JTL_API void jtl_close(Reader* reader){delete reader;}
JTL_API int jtl_open(const PathChar* path,Reader** result){
    *result=nullptr;Reader* reader=nullptr;
    try {
        reader=new Reader();int status=reader->open_file(path);
        if(!status)status=reader->unpack();
        if(status){delete reader;return status;}
        *result=reader;return 0;
    } catch(const std::bad_alloc&){delete reader;return LIBRAW_UNSUFFICIENT_MEMORY;}
    catch(...){delete reader;return LIBRAW_DATA_ERROR;}
}
JTL_API const unsigned short* jtl_info(Reader* reader,Metadata* meta){
    auto& data=reader->imgdata;auto& sizes=data.sizes;auto& color=data.rawdata.color;
    meta->raw_height=sizes.raw_height;meta->raw_width=sizes.raw_width;meta->height=sizes.height;meta->width=sizes.width;
    meta->top=sizes.top_margin;meta->left=sizes.left_margin;meta->iheight=sizes.iheight;meta->iwidth=sizes.iwidth;
    meta->pitch=sizes.raw_pitch;meta->flip=sizes.flip;meta->aspect=sizes.pixel_aspect;
    std::memcpy(meta->desc,data.idata.cdesc,4);meta->desc[4]=0;
    std::memcpy(meta->camera,color.cam_mul,sizeof(meta->camera));std::memcpy(meta->daylight,color.pre_mul,sizeof(meta->daylight));
    std::memcpy(meta->matrix,color.cmatrix,sizeof(meta->matrix));std::memcpy(meta->xyz,color.cam_xyz,sizeof(meta->xyz));
    std::memcpy(meta->white,color.linear_max,sizeof(meta->white));meta->maximum=color.maximum;
    if(!data.rawdata.raw_image || data.idata.filters<1000 || meta->pitch%2 || meta->pitch/2<meta->raw_width || meta->left+meta->width>meta->raw_width || meta->top+meta->height>meta->raw_height)return nullptr;
    for(int row=0;row<8;row++)for(int col=0;col<2;col++){
        int index=(row%2)*2+col,value=reader->COLOR(row,col);
        if(row<2)meta->bayer[index]=value;
        else if(value!=meta->bayer[index])return nullptr;
    }
    unsigned previous_black=data.color.black,previous_channels[LIBRAW_CBLACK_SIZE];
    std::memcpy(previous_channels,data.color.cblack,sizeof(previous_channels));reader->adjust_bl();
    std::memcpy(meta->black,data.color.cblack,sizeof(meta->black));data.color.black=previous_black;
    std::memcpy(data.color.cblack,previous_channels,sizeof(previous_channels));return data.rawdata.raw_image;
}
JTL_API int jtl_process(Reader* reader,int half,void** image,unsigned short** pixels,unsigned* height,unsigned* width){
    *image=nullptr;*pixels=nullptr;
    try {
        auto& params=reader->imgdata.params;params.half_size=half;params.use_camera_wb=1;params.no_auto_bright=1;
        params.output_bps=16;params.output_color=1;params.gamm[0]=params.gamm[1]=1.;
        int status=reader->dcraw_process();if(status)return status;
        libraw_processed_image_t* out=reader->dcraw_make_mem_image(&status);
        if(status || !out){if(out)LibRaw::dcraw_clear_mem(out);return status?status:LIBRAW_DATA_ERROR;}
        if(out->type!=LIBRAW_IMAGE_BITMAP || out->bits!=16 || out->colors!=3 || size_t(out->width)*out->height*6!=out->data_size){LibRaw::dcraw_clear_mem(out);return LIBRAW_DATA_ERROR;}
        *height=out->height;*width=out->width;*image=out;*pixels=reinterpret_cast<unsigned short*>(out->data);return 0;
    } catch(const std::bad_alloc&){return LIBRAW_UNSUFFICIENT_MEMORY;}catch(...){return LIBRAW_DATA_ERROR;}
}
JTL_API void jtl_free_image(void* image){LibRaw::dcraw_clear_mem(static_cast<libraw_processed_image_t*>(image));}
