# Jiangtherapee to Leica 1.0.4 · 源码交付

Windows 建议解压到短路径（如 `C:\JTL-src`），避免路径过长导致部分解压工具报错。

`app.py` 是桌面程序入口。`assets/` 提供原生组件、字体和图标，`assets/*-src/` 提供 LibRaw 桥、darktable 调色和 RawTherapee 高光恢复的 C/C++ 源码。第三方许可在 `notices/` 及各组件目录，开发工具和测试在 `tools/`。

直接使用桌面程序请从[本版 Release](https://github.com/y-g-jiang/Jiangtherapee-To-Leica/releases/tag/v1.0.4) 下载对应平台的包。本次沿用 1.0.3 推理资源。将 `assets/model.json` 中 `models` 所列文件放入 `assets/`，将 `assets/vivid/model.json` 所列文件放入 `assets/vivid/`，逐个核对清单中的 SHA-256。Bayer RAW 解马赛克还需 `assets/bayer.onnx`，SHA-256 为 `0cb885f67d8d1fac3dc1ccc93b748275a7962ef22cd95259c6207a98b9e09e2f`。公开源码包保留两份风格资源清单。

## 运行、验证和构建

两种风格均在高光恢复之后、M9 颗粒之前处理。徕卡生动调用 `vivid_refinement.py`，在模型分析尺寸比较当前影调处理后的原图与网络输出，逐通道拟合局部反差增益，再提取与 16 像素模型周期同相的残差。原图中已有的周期纹理、明显结构、全分辨率细节以及高光保护区都会限制修正。默认允许部分网纹残留，每通道最大修正约为 8 位色阶的 1.5 级。每个 64 × 64 分析像素对应的成片区域内，颗粒前的 16 位 RGB 各通道总量分别守恒。两套主模型均使用基础包的权重。

徕卡经典通过 `flat_refinement.py` 从原片经当前影调处理后的 RGB 计算两种尺度的纹理强度，用轻量门控估计平坦程度。`tools/fit_flat_gate.py` 用固定随机种子生成带噪渐变和纹理样本，复现经典模式的门控参数。以下成对交换内核用于经典模式。

修正以成对交换的方式处理 16 位 sRGB 调色量，分别保存每个连通区域的 R、G、B 总和。全尺寸处理按有效预览区的比例调整采样距离，跨渲染分块连续计算。超过内存阈值的引导数据会写入临时文件，全图导出临时空间额外需要每像素 7 字节。区域守恒针对加颗粒和 JPEG 压缩之前的 16 位结果。可运行 `python -m unittest discover -s tools -p test_flat_refinement.py` 验证纯灰、渐变、纹理边界、预览及全图输出。

整数交换内核的完整源码在 `assets/flat-src/exchange.c`。Windows x64 可以用 `zig cc -O3 -shared -s -target x86_64-windows-gnu assets/flat-src/exchange.c -o assets/jtl-flat-win.dll` 重建。在 Mac 上可执行 `clang -O3 -dynamiclib assets/flat-src/exchange.c -o "assets/jtl-flat-$(uname -m).dylib"`。测试会逐值对比原生内核与 NumPy 参考实现。

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

成品在 `dist/`。Windows 自检：运行 `dist\Jiangtherapee-to-Leica-1.0.4-Windows-x64.exe --self-test exe-test.json`，待报告写完后确认 `ok` 为 `true`。重打包的二进制文件不保证与官方发布具有相同哈希。Apple 芯片 Mac 使用原生 arm64 Python 安装桌面依赖及上述版本的 PyInstaller 后执行 `python tools/build_native.py`；也可手动运行仓库的 `Package macOS arm64` 工作流，校验权重、签名和冻结版自检后生成 ZIP。

`assets/vivid/model.json` 和 `assets/model.json` 记录推理网络的文件 SHA-256。`SHA256SUMS.txt` 列出包内各文件的 SHA-256（清单自身除外）。

本项目自有代码按 PolyForm Noncommercial License 1.0.0 授权并附加署名条件；第三方组件按其各自许可。使用、修改或再分发前请先读 `LICENSE.md`。
