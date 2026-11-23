# macOS 本地构建记录（arm64 / Apple 芯片）

本文件记录在**这台 Mac** 上把 `y-g-jiang/Jiangtherapee-To-Leica` 从源码构建成可用 `.app` 的全过程，
以及相对上游源码所做的两处改动。上游说明见 [SOURCE_BUILD.md](SOURCE_BUILD.md)。

## 1. 成品

| 文件 | 说明 |
| --- | --- |
| `dist/Jiangtherapee to Leica.app` | 可直接运行的 App（457 MB，ad-hoc 签名，版本 1.0.3，arm64） |
| `dist/Jiangtherapee-to-Leica-1.0.3-macOS-arm64.zip` | 262 MB，拖入「应用程序」即用 |
| `dist/self-test-macOS-arm64.json` | 冻结包内跑出的自检报告，`ok: true` |
| `dist/macos-preview.png` | 实机界面截图（打开 JPEG、512 px 预览、前后对比） |

运行：双击 `dist/Jiangtherapee to Leica.app`，或把照片拖进窗口。命令行自检：

```bash
"dist/Jiangtherapee to Leica.app/Contents/MacOS/Jiangtherapee to Leica" --self-test report.json
```

## 2. 构建环境（本机没有 Homebrew、没有 sudo）

- 系统：macOS 27.0.1，arm64；仅 Command Line Tools（Apple clang 21）。
- 解释器：`uv python install 3.10` → CPython **3.10.22**（python-build-standalone，arm64），
  与文档要求的 64 位 CPython 3.10 一致，装在 `~/.local/share/uv/python/`，不需要管理员权限。
- 依赖：`python -m pip install -r requirements.txt`，实际装到
  numpy 1.26.4 / Pillow 11.3.0 / opencv-python-headless 4.11.0.86 / onnxruntime 1.21.0 /
  PySide6-Essentials 6.8.3 / tifffile 2025.5.10。
- 打包：`pip install pyinstaller==6.16.0`。
- `onnxruntime` 暴露的 provider：`CoreMLExecutionProvider`、`AzureExecutionProvider`、`CPUExecutionProvider`。

```bash
uv python install 3.10
python3.10 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt pyinstaller==6.16.0
.venv/bin/python tools/build_native.py          # 产物在 dist/
```

`.venv`、`build/`、`dist/` 均在 `.gitignore` 内。

## 3. 推理资源（公开仓库里没有，这一步是必需的）

公开源码只带 `model.json` 清单，不含权重（见 SOURCE_BUILD.md）。本机做法：从作者**官方发布的
v1.0.3 Windows 单文件包**中提取自带的推理资源，放进 `assets/`。属于直接取用官方发布物，
没有反编译业务逻辑，也没有绕过任何保护。

```bash
# 官方发布物：Jiangtherapee-to-Leica-1.0.3-Windows-x64.exe
# sha256 dc5a1db66f4ef6b7d9ac661b114308f7ac7e31d18246a4f04a2ceac9792afd2e
pyinstxtractor-ng windows-x64.exe          # 解出 PyInstaller 归档
```

提取到 `assets/` 的文件与 SHA-256（与官方 `model.json` 逐条一致）：

| 文件 | SHA-256 |
| --- | --- |
| `assets/bayer.onnx` | `0cb885f67d8d1fac3dc1ccc93b748275a7962ef22cd95259c6207a98b9e09e2f`（与 SOURCE_BUILD.md 一致） |
| `assets/tile.onnx` | `e1132ea3085a0a1b497c168145c10c505cfdc0fa94bd8e5e61fee17702c255f3` |
| `assets/atlas.onnx` | `32c339206edd537cea74390e302e68c4869e168ed2411b3783f3b12150246e4b` |
| `assets/landscape.onnx` | `f1b5ab2b1533f8c935217f9acf0ac5b1f071dc6e8cc03e04b3be0d724ecc3d5c` |
| `assets/portrait.onnx` | `a92f486950a17211db4864a0ee26f0a988aee563f98957b85495df066a3dcb4b` |
| `assets/gallery.bin` | `c22ced67b65940405856eaa423f3581ca1417c1da252582d951306e574846e51` |
| `assets/vivid/landscape.onnx` | `e55464749f0d9c93c04e54370c2f675ddaabc41de30efd50c45321ec7120c5af` |
| `assets/vivid/portrait.onnx` | `0847f394502e5bc108e3cfe56afb40376ab876d67eaf8a3765d1a9e73fe0d44b` |
| `assets/vivid/tile.onnx` | `587ec20865d15228a674a53998db9c4fa2264af32fe56436a8f8a6d691c0fe0b` |
| `assets/vivid/atlas.onnx` | `fcbaa7e411c2480a59d6fb91bcd479209fdecaf2a4482974f742f23c4ae3a774` |
| `assets/vivid/paired.bin` | `8dacba4b86b3cc7a6e0babf0c47646b0d49558507d1ac621d5071794055dd329` |

注意两处与公开清单的差异（代码运行时不校验 `model.json`，只按文件名加载）：

1. `landscape.onnx` / `portrait.onnx` 在官方包内是**已暴露 inspection 输出**（`regions`、
   `features_3/6/9/12`、`routing_0/1/2`）的版本，即 `tools/expose_studio.py` 处理后的图，
   哈希与公开仓库里那份“未暴露”的清单不同；显影透视的 23 张空间响应、通道矩阵都依赖这些输出，
   所以必须用包内这份。
2. `.bin` 只是改了名：`classic.bin` ↔ `gallery.bin`、`vivid2.bin` ↔ `paired.bin`，哈希完全相同。
   它们约 183 MB，是训练检查点，**运行时并不读取**（权重已烘进 ONNX）。

因此把 `assets/model.json`、`assets/vivid/model.json` 换成了官方发布包内的清单（含 checkpoint 哈希），
让清单与实际文件一致。这是相对上游源码的第一处改动。

## 4. 对 `tools/build_native.py` 的改动

第二处改动，三小点，都是让 `python tools/build_native.py` 在这台机器上能出正确产物：

1. 追加 `--exclude-module pkg_resources --exclude-module setuptools`。
   不改的话，冻结包一启动就崩：PyInstaller 6.16 的 `pyi_rth_pkgres` 钩子 + setuptools 79 自带的
   vendored `backports` 会抛 `ModuleNotFoundError: No module named 'backports'`。本应用运行时
   不需要 setuptools（只有被排除的 `onnxruntime.transformers` 才会用到 `pkg_resources`）。
2. `--name` 默认取 `release_info.PRODUCT`（`Jiangtherapee to Leica`），与程序界面标题一致。
3. macOS 打包后改写 `Info.plist`：`CFBundleShortVersionString` / `CFBundleVersion` 由 PyInstaller
   默认的 `0.0.0` 改为 `1.0.3`，补 `LSMinimumSystemVersion=13.3`（README 声明的最低系统版本），
   随后 ad-hoc 重新签名，保证签名封印与 plist 一致。

## 5. 验证结果

`dist/self-test-macOS-arm64.json`（在打包后的 `.app` 内运行，非源码目录）：

- `ok: true`，5.7 s 完成。
- LibRaw **0.23.0-Snapshot202611**，提交 `40fb564…`（与代码内的版本校验一致，arm64 dylib 正常加载）。
- 两套风格 vivid / classic 均跑通；23 张空间响应、6 个 inspection 视图通过。
- 全尺寸导出：16 位 TIFF + 同一次显影的 quality-80 JPEG，嵌入 sRGB ICC，重名自动加编号、取消不留半成品。
- `bayer_graphics: true` → BayerNet 走 **Core ML** 并通过与 CPU 的 1‰ 分位精度对照。
- `chroma_opencl: true` → 16 位色差降噪走 OpenCV OpenCL。
- 全图像素精度：MAE 0.0039/255（vivid）、0.0034/255（classic）。
- 另把 zip 解包到干净目录再跑一遍自检，同样 `ok: true`。

界面（截图见 `dist/macos-preview.png`）：中文界面、徕卡生动/经典切换、「原图对比」分割线、
影调/颜色/曲线/质感分页、512 px 预览、左下状态栏「预览就绪」均正常。

## 5.1 崩溃修复：打开部分 RAW 时 SIGBUS（2026-11-24）

真机报告：打开某张 RAW 时挂掉，崩溃日志为

```
Exception Type: EXC_BAD_ACCESS (SIGBUS) — Thread stack size exceeded
Thread 38 (pooled): ___chkstk_darwin → dgetrf_parallel → dgesv_64_ →
                    _umath_linalg.inv<double> → ... → QRunnableWrapper::run()
```

**根因**：`sensor.py` 在相机色彩矩阵缺失/退化时走备用分支，用 `np.linalg.inv()` 反解 3×3 矩阵。
numpy 的 `inv` 走 LAPACK `dgesv`，OpenBLAS 的并行 `dgetrf` 入口会做一次约 542 KB 的栈探测；
Qt 工作线程（`QThreadPool`，即 app.py 里所有 `enqueue` 的后台任务）在 macOS 上只有 **512 KB** 栈，
直接撞进 guard page。主线程有 8 MB 栈，Windows 的 Qt 工作线程默认 1 MB，所以同一份代码在那两处都不炸。

**复现**：在一个 `QThreadPool` 线程里对 3×3 float64 调 `np.linalg.inv` → 稳定 SIGBUS；
`np.linalg.det` 不走 `dgesv`，不炸。这正是日志里的调用栈。

**修复**（两处，都在源码里）：

1. `sensor.py` 新增 `determinant3()` / `inverse3()`，用余子式公式手写 3×3 行列式与逆矩阵，
   完全绕开 LAPACK（与 `np.linalg.inv` 差值 ≤ 2.2e-16，即 1 ulp）。备用分支改用它。
2. `app.py` 在 `import numpy` 之前 `os.environ.setdefault('OPENBLAS_NUM_THREADS','1')`：
   任何残余的 BLAS/LAPACK 调用都不再走多线程路径，杜绝同类栈溢出（本应用不做大矩阵运算，性能无影响）。

**验证**：用一个 `color_matrix` 全零的伪 RAW（触发备用分支）在 `QThreadPool` 线程里跑完整
`sensor.read()`：修复前同线程 SIGBUS，修复后正常输出 `(120, 80, 3)`；
打包后的 `sensor.pyc` 已确认含 `inverse3` 且不再引用 `linalg`；REAL CR2 经 GUI 后台线程加载正常；
冻结包自检仍 `ok: true`（5.9 s）。

**只有**「LibRaw 报告不出可用相机色彩矩阵」的 RAW（部分手机 DNG、去马赛克后处理的 DNG 等）才会
进这个分支，所以自检和常见 RAW 都不会碰到它 —— 之前没能测出来。

## 6. 已知限制与后续

- **未做 Developer ID 签名与 Apple 公证**：本机构建双击即可运行；若发给别人，Gatekeeper
  会拦（README 也说明官方 Mac 版同样未签名/未公证）。对外分发需要开发者证书 +
  `notarytool` 公证。
- **仅 arm64**：本机是 Apple 芯片，产物只含 arm64 切片。Intel 版需在 x86_64 的 CPython 3.10
  下重新打包（uv 可装 x86_64 解释器，但要在 x86_64 进程里跑 PyInstaller）。
- 打包体积 457 MB（`Contents/Frameworks` 251 MB + `Contents/Resources` 202 MB）：其中 OpenCV 86 MB、
  ONNX Runtime 56 MB、Qt/PySide6 约 57 MB、numpy 32 MB，`assets` 192 MB —— 而 `gallery.bin`+`paired.bin`
  就占 183 MB 且运行时不读取。若不必与官方包逐文件对齐，删掉这两个 `.bin` 可把成品压到约 270 MB。
- 启动后会在后台请求 `release_info.SIGNAL_URL` 查更新信号（不传照片、不自动下载）；断网不影响显影。
- `tools/macos_launcher.c` 描述的是另一套「内嵌 CPython + Resources/studio」布局，PyInstaller
  路线用不到它，未采用。

## 7. 关于「删掉禁止商用 + 付费」的提醒（非法律意见）

这部分和构建无关，但会影响后续方案，先把事实列清楚，细节请与作者和律师确认：

- **自有代码**：PolyForm Noncommercial License 1.0.0 **外加署名条件** —— 任何使用/修改/再分发，
  都要在同一程序界面显著标注 `Jiangtherapee-to-Leica` 并给出本仓库链接。作者把“禁止商用”删掉后，
  署名条件通常仍然存在（它写在 LICENSE.md 里独立于商用条款）。
- **模型权重**：`assets/*.onnx` 是作者的推理资源，不在开源许可覆盖范围内。即便代码改为可商用，
  权重的商用授权也需要作者单独给（这也正是发布包里带 checkpoint、公开仓库只留清单的原因）。
- **第三方组件各自为政**：`assets/darkroom-src`（darktable 派生）与 `rt-highlights-src`
  （RawTherapee 派生）是 **GPL-3**，LibRaw 是 LGPL-2.1/CDDL，PySide6/Qt 是 **LGPL-3**，
  ONNX Runtime / BPAM / BayerNet 是 MIT，DINOv2 是 Apache-2.0。
  这些 dylib 已随包分发且源码在仓库内，但一旦做商业分发：GPL 组件要求你分发时同样提供
  对应源码与许可，修改过的 GPL dylib 必须开源；Qt 的 LGPL 要求保持可替换动态库并附声明。
- 也就是说，商用路径 = 作者对自有代码 + 权重的授权（付费可解决）＋ 自己履行 GPL/LGPL 义务
  （不是付费能免除的）。若要闭源商用，只能替换掉 darktable/RawTherapee 派生的那几个 dylib。
