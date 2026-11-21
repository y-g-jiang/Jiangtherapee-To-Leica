import hashlib
import json
from pathlib import Path

import onnx
from onnx import TensorProto, helper


def expose(folder):
    manifest_path=folder/'model.json'
    manifest=json.loads(manifest_path.read_text(encoding='utf-8'))
    for name in ('landscape','portrait'):
        path=folder/(name+'.onnx');model=onnx.load(path,load_external_data=False);graph=model.graph
        nodes={node.name:node for node in graph.node};outputs={item.name for item in graph.output}
        decoder=nodes['/decoder/Softmax'];assert decoder.input[0]==nodes['/decoder/ranges/ranges.1/Conv'].output[0]
        height,width=(384,512) if name=='landscape' else (512,384)
        taps=[('regions',decoder.output[0],[1,4,height//4,width//4])]
        for idx,depth in enumerate((3,6,9,12)):
            feature=nodes[f'/decoder/proj.{idx}/proj.{idx}.0/Reshape'].input[0]
            taps.append((f'features_{depth}',feature,[1,384,height*manifest['analysis']//512//14,width*manifest['analysis']//512//14]))
        for idx in range(3):
            taps.append((f'routing_{idx}',nodes[f'/fusion.{idx}/Softmax'].output[0],[1,16,16]))
        for alias,source,shape in taps:
            if alias in outputs:continue
            graph.node.append(helper.make_node('Identity',[source],[alias],name='studio_'+alias))
            graph.output.append(helper.make_tensor_value_info(alias,TensorProto.FLOAT,shape))
        onnx.save(model,path)
        manifest['models'][path.name]=hashlib.sha256(path.read_bytes()).hexdigest()
    manifest['inspection']='ranges4-dino4-routing3-v1'
    manifest_path.write_text(json.dumps(manifest,indent=2),encoding='utf-8')


if __name__=='__main__':
    import sys
    expose(Path(sys.argv[1]))
