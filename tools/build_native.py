import argparse
import os
import plistlib
import subprocess
import sys
from pathlib import Path

root=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(root))
from release_info import PRODUCT,VERSION

parser=argparse.ArgumentParser();parser.add_argument('--dist',type=Path,default=root/'dist');parser.add_argument('--work',type=Path,default=root/'build');parser.add_argument('--name',default=PRODUCT);args=parser.parse_args()
work=args.work.resolve();work.mkdir(parents=True,exist_ok=True)
cmd=[sys.executable,'-m','PyInstaller','--noconfirm','--windowed','--onedir','--name',args.name,'--icon',str(root/'assets'/('app.icns' if sys.platform=='darwin' else 'app.ico')),'--distpath',str(args.dist.resolve()),'--workpath',str(work),'--specpath',str(work),'--add-data',str(root/'assets')+os.pathsep+'assets','--add-data',str(root/'notices')+os.pathsep+'notices','--collect-binaries','onnxruntime','--exclude-module','rawpy','--exclude-module','onnx','--exclude-module','onnxruntime.tools','--exclude-module','onnxruntime.quantization','--exclude-module','onnxruntime.transformers','--exclude-module','sympy','--exclude-module','pytest','--exclude-module','tkinter','--exclude-module','IPython','--exclude-module','pkg_resources','--exclude-module','setuptools']
if sys.platform=='darwin':cmd+=['--osx-bundle-identifier','studio.jiangtherapee.toleica']
subprocess.run(cmd+[str(root/'app.py')],check=True,cwd=root)

# PyInstaller leaves CFBundleShortVersionString at 0.0.0 and signs the bundle before
# we can adjust Info.plist; set the real version and re-sign ad-hoc so the seal matches.
if sys.platform=='darwin':
    app=args.dist.resolve()/(args.name+'.app');info=app/'Contents'/'Info.plist'
    data=plistlib.loads(info.read_bytes())
    data.update(CFBundleShortVersionString=VERSION,CFBundleVersion=VERSION,LSMinimumSystemVersion='13.3',CFBundleDisplayName=PRODUCT,CFBundleName=PRODUCT)
    info.write_bytes(plistlib.dumps(data))
    subprocess.run(['codesign','--force','--sign','-','--identifier','studio.jiangtherapee.toleica',str(app)],check=True)
    print('Bundle:',app)
