# 许可与使用条款 · Jiangtherapee-to-Leica

本文件适用于 Jiangtherapee to Leica（下称「本项目」）中由本项目作者编写的代码与文档。
本项目自有部分按 **PolyForm Noncommercial License 1.0.0** 授权（正文见文末），并附加第 1 节的署名条件。

- 项目主页：<https://y-g-jiang.github.io>
- 项目仓库：<https://github.com/y-g-jiang/Jiangtherapee-To-Leica>

## 0. 中文要点（便于理解，不具独立法律效力）

- **允许**：个人学习、研究、实验、测试、私人娱乐、爱好项目，以及慈善机构、教育机构、公共研究机构、公共安全与卫生机构、环境保护机构、政府机构的非商业使用。
- **禁止**：任何商业用途，包括但不限于企业内部生产使用、对外付费服务、随硬件或软件捆绑销售、以本项目为基础的收费产品或增值服务。
- **必须**：在与使用本项目相关的同一程序界面内，显著标注名称 **Jiangtherapee-to-Leica**，并提供指向本项目仓库的链接（见第 1 节）。
- **例外**：随包附带的第三方组件不适用上述非商业限制，按其各自许可执行（见第 2 节）。

## 1. 附加署名条件（适用于本项目自有部分）

1.1 任何使用、修改、再分发本项目（含衍生作品）的行为，均须在**与该使用行为相关的同一用户界面**内，以清晰可见的方式标注名称 **Jiangtherapee-to-Leica**，并提供**指向本项目仓库的链接**：<https://github.com/y-g-jiang/Jiangtherapee-To-Leica>。

1.2 标注位置可以是但不限于：程序「关于」页、启动页、主窗口标题栏或帮助菜单；只要使用者在使用过程中无需额外操作即可看到，即视为满足。

1.3 由本项目导出的照片（TIFF、JPEG 等）不要求嵌入该标注；但任何再分发或改编版本必须原样保留本条款与第 1.1 条要求。

1.4 未满足第 1.1 条的使用、修改或再分发，不在本许可的授权范围内。

1.5 本节不改变第 2 节所述第三方组件的许可。

## 2. 第三方组件（不适用本文件的非商业限制）

下列组件及其编译产物按其各自许可提供，其使用、复制、修改与再分发**不受**本文件第 0、1 节限制，也不受 PolyForm Noncommercial 1.0.0 约束：

| 组件 | 路径 | 许可 |
|---|---|---|
| darktable 派生源码及其编译库 | `assets/darkroom-src/`、`assets/*darkroom*.dll`、`assets/*darkroom*.dylib` | GPL-3.0（见 `assets/darkroom-src/COPYING`） |
| RawTherapee 5.12 派生源码及高光适配层 | `assets/rt-highlights-src/`、`assets/rt-highlights-*` | GPL-3.0-or-later（见 `assets/rt-highlights-src/rt_License.txt`） |
| LibRaw 桥接与构建素材 | `assets/raw-core-src/`、`assets/jtl-libraw-*` | LGPL-2.1 / CDDL / 各自许可 |
| PySide6 / Qt | 运行依赖 | LGPLv3 |
| ONNX Runtime | 运行依赖 | MIT |
| DINOv2 | 编码器来源 | Apache-2.0 |

其余第三方依赖的完整许可文本见 `notices/`。若本文件与上述任一许可冲突，以该第三方许可为准；本文件的非商业限制仅约束本项目作者拥有版权的部分。

## 3. 无担保

在适用法律允许的最大范围内，本项目按「现状」提供，不附任何明示或默示担保。因使用或无法使用本项目造成的任何损失，由使用者自行承担。

---

Required Notice: Copyright (c) 2026 姜尧耕 / Jiangtherapee-to-Leica <https://github.com/y-g-jiang/Jiangtherapee-To-Leica>

---

# PolyForm Noncommercial License 1.0.0

<https://polyformproject.org/licenses/noncommercial/1.0.0>

## Acceptance

In order to get any license under these terms, you must agree to them as both strict obligations and conditions to all your licenses.

## Copyright License

The licensor grants you a copyright license for the software to do everything you might do with the software that would otherwise infringe the licensor's copyright in it for any permitted purpose.  However, you may only distribute the software according to [Distribution License](#distribution-license) and make changes or new works based on the software according to [Changes and New Works License](#changes-and-new-works-license).

## Distribution License

The licensor grants you an additional copyright license to distribute copies of the software.  Your license to distribute covers distributing the software with changes and new works permitted by [Changes and New Works License](#changes-and-new-works-license).

## Notices

You must ensure that anyone who gets a copy of any part of the software from you also gets a copy of these terms or the URL for them above, as well as copies of any plain-text lines beginning with `Required Notice:` that the licensor provided with the software.  For example:

> Required Notice: Copyright Yoyodyne, Inc. (http://example.com)

## Changes and New Works License

The licensor grants you an additional copyright license to make changes and new works based on the software for any permitted purpose.

## Patent License

The licensor grants you a patent license for the software that covers patent claims the licensor can license, or becomes able to license, that you would infringe by using the software.

## Noncommercial Purposes

Any noncommercial purpose is a permitted purpose.

## Personal Uses

Personal use for research, experiment, and testing for the benefit of public knowledge, personal study, private entertainment, hobby projects, amateur pursuits, or religious observance, without any anticipated commercial application, is use for a permitted purpose.

## Noncommercial Organizations

Use by any charitable organization, educational institution, public research organization, public safety or health organization, environmental protection organization, or government institution is use for a permitted purpose regardless of the source of funding or obligations resulting from the funding.

## Fair Use

You may have "fair use" rights for the software under the law. These terms do not limit them.

## No Other Rights

These terms do not allow you to sublicense or transfer any of your licenses to anyone else, or prevent the licensor from granting licenses to anyone else.  These terms do not imply any other licenses.

## Patent Defense

If you make any written claim that the software infringes or contributes to infringement of any patent, your patent license for the software granted under these terms ends immediately. If your company makes such a claim, your patent license ends immediately for work on behalf of your company.

## Violations

The first time you are notified in writing that you have violated any of these terms, or done anything with the software not covered by your licenses, your licenses can nonetheless continue if you come into full compliance with these terms, and take practical steps to correct past violations, within 32 days of receiving notice.  Otherwise, all your licenses end immediately.

## No Liability

***As far as the law allows, the software comes as is, without any warranty or condition, and the licensor will not be liable to you for any damages arising out of these terms or the use or nature of the software, under any kind of legal claim.***

## Definitions

The **licensor** is the individual or entity offering these terms, and the **software** is the software the licensor makes available under these terms.

**You** refers to the individual or entity agreeing to these terms.

**Your company** is any legal entity, sole proprietorship, or other kind of organization that you work for, plus all organizations that have control over, are under the control of, or are under common control with that organization.  **Control** means ownership of substantially all the assets of an entity, or the power to direct its management and policies by vote, contract, or otherwise.  Control can be direct or indirect.

**Your licenses** are all the licenses granted to you for the software under these terms.

**Use** means anything you do with the software requiring one of your licenses.
