from pathlib import Path
import hashlib
import json

import numpy as np
import onnx
from onnx import helper, numpy_helper


def convert(path):
    model=onnx.load(path);graph=model.graph;nodes=[];counter=0
    model.opset_import.append(helper.make_opsetid('com.microsoft',1))
    for axis in ('x','y'):
        graph.input.append(helper.make_tensor_value_info('uv_'+axis,1,['width' if axis=='x' else 'height']))
    for source in ('fine','prior'):
        desc=next(inp for inp in graph.input if inp.name==source);desc.name=source+'_grid'
        desc.type.tensor_type.shape.dim[2].dim_param=source+'_h';desc.type.tensor_type.shape.dim[3].dim_param=source+'_w'
        stream=desc.name
        def emit(code,name,*inputs,**attrs):
            key=source+'_'+name;nodes.append(helper.make_node(code,inputs,[key],name=key,**attrs));return key
        def literal(name,value,dtype):
            key=source+'_'+name;graph.initializer.append(numpy_helper.from_array(np.asarray(value,dtype=dtype),key));return key
        shape=emit('Shape','shape',stream);one=literal('one',1,'f');half=literal('half',.5,'f');zero=literal('zero',0,'f')
        for dim,axis in ((3,'x'),(2,'y')):
            span=emit('Cast',axis+'span',emit('Gather',axis+'dim',shape,literal(axis+'index',dim,'int64'),axis=0),to=1);limit=emit('Sub',axis+'last',span,one)
            loc=emit('Clip',axis+'loc',emit('Sub',axis+'center',emit('Mul',axis+'mul','uv_'+axis,span),half),zero,limit);lo=emit('Floor',axis+'lo',loc)
            hi=emit('Min',axis+'hi',emit('Add',axis+'next',lo,one),limit);weight=emit('Sub',axis+'frac',loc,lo)
            if axis=='y':weight=emit('Unsqueeze',axis+'column',weight,literal('expand',[1],'int64'))
            left=emit('Gather',axis+'lower',stream,emit('Cast',axis+'loweri',lo,to=6),axis=dim);right=emit('Gather',axis+'upper',stream,emit('Cast',axis+'upperi',hi,to=6),axis=dim)
            stream=emit('Add',axis+'result',emit('Mul',axis+'a',left,emit('Sub',axis+'inv',one,weight)),emit('Mul',axis+'b',right,weight))
        nodes.append(helper.make_node('Identity',[stream],[source],name=source+'_sampled'))
    for node in graph.node:
        if node.op_type=='Gelu':
            assert all(attr.name=='approximate' and attr.s==b'none' for attr in node.attribute)
            del node.attribute[:]
            node.domain='com.microsoft'
        if node.op_type!='GridSample':
            nodes.append(node);continue
        prefix=f'atlas{counter}_';counter+=1
        def constant(name,value,dtype):
            key=prefix+name;graph.initializer.append(numpy_helper.from_array(np.asarray(value,dtype=dtype),key));return key
        def op(code,name,*inputs,**attrs):
            key=prefix+name;nodes.append(helper.make_node(code,inputs,[key],name=key,**attrs));return key
        zero=constant('zero',0,'f');one=constant('one',1,'f');half=constant('half',.5,'f')
        axis1=constant('axis1',[1],'int64');axis2=constant('axis2',[2],'int64');axis3=constant('axis3',[3],'int64')
        grid,coordinates=node.input;shape=op('Shape','shape',grid)
        groups,channels=((4,8),(9,3))[counter-1]
        atlas=op('Reshape','flat',op('Transpose','channels_last',grid,perm=[0,2,3,4,1]),constant('flatshape',[-1,channels],'int64'))
        coords=op('Squeeze','coords',coordinates,axis1);offset=constant('groups',np.arange(groups).reshape(groups,1,1),'f');fractions=[];steps=[]
        for idx,key in ((2,'z'),(1,'y'),(0,'x')):
            span=op('Cast',key+'size',op('Gather',key+'len',shape,constant(key+'dim',4-idx,'int64'),axis=0),to=1)
            axis=op('Gather',key+'coord',coords,constant(key+'index',idx,'int64'),axis=3);last=op('Sub',key+'last',span,one)
            location=op('Clip',key+'clip',op('Sub',key+'shift',op('Mul',key+'scale',op('Add',key+'pos',axis,one),op('Mul',key+'half',span,half)),half),zero,last)
            low=op('Floor',key+'low',location);offset=op('Add',key+'offset',op('Mul',key+'stride',offset,span),low)
            steps=[op('Mul',key+'step'+str(si),step,span) for si,step in enumerate(steps)]+[op('Sub',key+'step',op('Min',key+'upper',last,op('Add',key+'next',low,one)),low)]
            fractions.append(op('Unsqueeze',key+'frac',op('Sub',key+'weight',location,low),axis3))
        def fetch(index,depth):
            if depth==3:
                return op('Gather','g'+str(len(nodes)),atlas,op('Cast','i'+str(len(nodes)),index,to=6),axis=0)
            low=fetch(index,depth+1);high=fetch(op('Add','p'+str(len(nodes)),index,steps[depth]),depth+1)
            return op('Add','lerp'+str(len(nodes)),low,op('Mul','mul'+str(len(nodes)),fractions[depth],op('Sub','sub'+str(len(nodes)),high,low)))
        blended=op('Transpose','nchw',fetch(offset,0),perm=[0,3,1,2]);nodes.append(helper.make_node('Unsqueeze',[blended,axis2],list(node.output),name=prefix+'restore'))
    assert counter==2
    del graph.node[:];graph.node.extend(nodes);onnx.checker.check_model(model);target=path.with_name('atlas.onnx');onnx.save(model,target)
    manifest=path.with_name('model.json');info=json.loads(manifest.read_text('utf8'));assert info['models'][path.name]==hashlib.sha256(path.read_bytes()).hexdigest()
    info['models'][target.name]=hashlib.sha256(target.read_bytes()).hexdigest();manifest.write_text(json.dumps(info,indent=2)+'\n',encoding='utf8')


if __name__=='__main__':
    root=Path(__file__).resolve().parents[1]/'assets'
    for folder in (root,root/'vivid'):convert(folder/'tile.onnx')
