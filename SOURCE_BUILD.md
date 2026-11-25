# Jiangtherapee to Leica 1.0.3 · 源码交付

Windows 建议解压到短路径（如 `C:\JTL-src`），避免路径过长导致部分解压工具报错。

`app.py` 是桌面程序入口。`assets/` 提供原生组件、字体和图标，`assets/*-src/` 提供 LibRaw 桥、darktable 调色和 RawTherapee 高光恢复的 C/C++ 源码。第三方许可在 `notices/` 及各组件目录，开发工具和测试在 `tools/`。

直接使用 Windows 程序请从[本版 Release](https://github.com/y-g-jiang/Jiangtherapee-To-Leica/releases/tag/v1.0.3) 下载 EXE。若要从源码运行完整显影或打包，请先准备有权使用的 1.0.3 推理资源。将 `assets/model.json` 中 `models` 所列文件放入 `assets/`，将 `assets/vivid/model.json` 所列文件放入 `assets/vivid/`，逐个核对清单中的 SHA-256。Bayer RAW 解马赛克还需 `assets/bayer.onnx`，SHA-256 为 `0cb885f67d8d1fac3dc1ccc93b748275a7962ef22cd95259c6207a98b9e09e2f`。公开源码包保留两份风格资源清单。

## 运行、验证和构建

在解压后的本目录，以 64 位 Python 3.10 创建并激活虚拟环境：

```text
python -m pip install -r requirements.txt
python app.py --self-test self-test.json
python app.py
```

高光修订单独提供可重复的原片回归。若持有 Issue #1 附件，在 PowerShell 中设置 `$env:JTL_WINDOW_DNG` 为其中 DNG 的绝对路径，再运行 `python -m unittest discover -s tools -p "test_*.py"`。测试会检查原片哈希、两种风格的四档预览、全尺寸 TIFF/JPEG 的窗外天空；文件在临时目录生成，不会覆盖原片。未提供附件时只跳过这一项，合成亮度渐变、彩灯、曝光和 Bayer 饱和判断仍会测试。

Windows x64 单文件构建（发布环境：CPython 3.10.11，PyInstaller 6.16.0）：

```text
python -m pip install pyinstaller==6.16.0
python -m PyInstaller --noconfirm tools/windows_release.spec
python tools/make_update_signal.py dist
```

成品在 `dist/`。Windows 自检：运行 `dist\Jiangtherapee-to-Leica-1.0.3-Windows-x64.exe --self-test exe-test.json`，待报告写完后确认 `ok` 为 `true`。重打包的二进制文件不保证与官方发布具有相同哈希。macOS 使用目标芯片的 Python 安装桌面依赖及上述版本的 PyInstaller 后执行 `python tools/build_native.py`。本次正式发布和真机验收仅针对 Windows x64。

`assets/vivid/model.json` 和 `assets/model.json` 记录推理网络的文件 SHA-256。`SHA256SUMS.txt` 列出包内各文件的 SHA-256（清单自身除外）。

本项目自有代码按 PolyForm Noncommercial License 1.0.0 授权并附加署名条件；第三方组件按其各自许可。使用、修改或再分发前请先读 `LICENSE.md`。
