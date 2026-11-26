from pathlib import Path
import sys

from PyInstaller.utils.hooks import collect_dynamic_libs

root = Path(SPECPATH).resolve().parent
sys.path.insert(0, str(root))
from release_info import VERSION, windows_asset
assets = root / 'assets'
inputs = ['app.ico', 'atlas.onnx', 'bayer.onnx', 'gallery.bin', 'Interface.ttf',
          'jtl-darkroom-win.dll', 'jtl-flat-win.dll', 'jtl-libraw-win.dll', 'landscape.onnx', 'model.json',
          'portrait.onnx', 'rt_highlights.dll', 'tile.onnx']
data = [(str(assets / name), 'assets') for name in inputs]
data += [(str(assets / 'vivid'), 'assets/vivid'), (str(root / 'notices'), 'notices')]
analysis = Analysis([str(root / 'app.py')], pathex=[], binaries=collect_dynamic_libs('onnxruntime'),
                    datas=data, hiddenimports=[], hookspath=[], hooksconfig={}, runtime_hooks=[],
                    excludes=['rawpy', 'onnx', 'onnxruntime.tools', 'onnxruntime.quantization',
                              'onnxruntime.transformers', 'sympy', 'pytest', 'tkinter', 'IPython'],
                    noarchive=False, optimize=0)
archive = PYZ(analysis.pure)
exe = EXE(archive, analysis.scripts, analysis.binaries, analysis.datas, [],
          name=Path(windows_asset(VERSION)).stem, debug=False, bootloader_ignore_signals=False,
          strip=False, upx=True, upx_exclude=[], runtime_tmpdir=None, console=False,
          disable_windowed_traceback=False, argv_emulation=False, target_arch=None, codesign_identity=None,
          entitlements_file=None, icon=[str(assets / 'app.ico')])
