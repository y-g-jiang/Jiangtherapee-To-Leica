import os
import platform
import sys

import cv2
import numpy as np
import onnxruntime as ort


class FullSpeed:
    def __init__(self):
        enabled=os.environ.get('JTL_CPU_ONLY')!='1'
        providers=ort.get_available_providers() if enabled else ()
        self.gpu=sys.platform=='win32' and 'DmlExecutionProvider' in providers
        self.apple=sys.platform=='darwin' and platform.machine()=='arm64' and 'CoreMLExecutionProvider' in providers
        self.sessions={};self.failed=set();self.opencl=False
        if enabled:
            try:self.opencl=cv2.ocl.useOpenCL() and cv2.ocl.Device_getDefault().type()==cv2.ocl.Device_TYPE_GPU
            except (AttributeError,cv2.error):pass

    def available(self,path):return (self.gpu or self.apple and path.name=='bayer.onnx') and path not in self.failed

    def run(self,path,inputs):
        if not self.available(path):return None
        try:
            if path not in self.sessions:
                opts=ort.SessionOptions();opts.intra_op_num_threads=min(4,os.cpu_count() or 1);opts.inter_op_num_threads=1;opts.enable_mem_pattern=False;opts.log_severity_level=3
                opts.execution_mode=ort.ExecutionMode.ORT_SEQUENTIAL;opts.add_session_config_entry('session.intra_op.allow_spinning','0')
                provider='CoreMLExecutionProvider' if self.apple else 'DmlExecutionProvider'
                config={'performance_preference':'high_performance','device_filter':'gpu'}
                if self.apple:
                    height,width=inputs['mosaic'].shape[-2:];opts.add_free_dimension_override_by_name('height',height);opts.add_free_dimension_override_by_name('width',width)
                    config={'ModelFormat':'MLProgram','MLComputeUnits':'CPUAndGPU','RequireStaticInputShapes':'1','AllowLowPrecisionAccumulationOnGPU':'0'}
                session=ort.InferenceSession(str(path),opts,providers=[(provider,config),'CPUExecutionProvider'])
                if provider not in session.get_providers():raise RuntimeError('Graphics device unavailable')
                session.disable_fallback();self.sessions[path]=session
                if self.apple:
                    from sensor import network
                    sample=session.run(None,inputs)[0];reference=network().run(None,inputs)[0];error=np.abs(sample-reference)
                    if not np.isfinite(error).all() or np.quantile(error,.999)>.0005 or error.max()>.004:raise RuntimeError('Device precision check failed')
                    return sample
            return self.sessions[path].run(None,inputs)[0]
        except InterruptedError:raise
        except Exception:
            self.failed.add(path);self.sessions.pop(path,None);return None

    def denoise(self,codes,strength):
        if self.opencl:
            try:return cv2.fastNlMeansDenoising(cv2.UMat(codes),strength,None,3,9,cv2.NORM_L1).get()
            except cv2.error:self.opencl=False
        return cv2.fastNlMeansDenoising(codes,strength,None,3,9,cv2.NORM_L1)
