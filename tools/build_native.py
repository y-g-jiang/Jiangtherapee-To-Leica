import argparse
import os
import subprocess
import sys
from pathlib import Path

root=Path(__file__).resolve().parents[1]
parser=argparse.ArgumentParser();parser.add_argument('--dist',type=Path,default=root/'dist');parser.add_argument('--work',type=Path,default=root/'build');args=parser.parse_args()
work=args.work.resolve();work.mkdir(parents=True,exist_ok=True)
cmd=[sys.executable,'-m','PyInstaller','--noconfirm','--windowed','--onedir','--name','Jiangtherapee To Leica','--icon',str(root/'assets'/('app.icns' if sys.platform=='darwin' else 'app.ico')),'--distpath',str(args.dist.resolve()),'--workpath',str(work),'--specpath',str(work),'--add-data',str(root/'assets')+os.pathsep+'assets','--add-data',str(root/'notices')+os.pathsep+'notices','--collect-binaries','onnxruntime','--exclude-module','rawpy','--exclude-module','onnx','--exclude-module','onnxruntime.tools','--exclude-module','onnxruntime.quantization','--exclude-module','onnxruntime.transformers','--exclude-module','sympy','--exclude-module','pytest','--exclude-module','tkinter','--exclude-module','IPython']
if sys.platform=='darwin':cmd+=['--osx-bundle-identifier','studio.jiangtherapee.toleica']
subprocess.run(cmd+[str(root/'app.py')],check=True,cwd=root)
