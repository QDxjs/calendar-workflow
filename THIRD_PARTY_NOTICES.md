# 第三方组件与许可边界

本项目原创 Python 代码和文档采用根目录的 [MIT 许可证](LICENSE)，版权人为青灯。以下组件保留各自的许可证；项目 MIT 不会替代第三方许可，也不会额外授予句子内容的著作权。

| 组件 | 固定版本或来源 | 许可及随附材料 |
| --- | --- | --- |
| Hitokoto 句子包 | `1ecfe5ac1550ac928396c80153efa3d342198b02` 的 b/d/h/k 分类 | 上游声明 AGPL-3.0；原始数据和许可在 `data/hitokoto/`，来源及单条内容权利提示见 [HITOKOTO_SOURCE.md](HITOKOTO_SOURCE.md)。 |
| resvg Windows x64 | 0.50.0 | MIT 或 Apache-2.0；二进制、许可及上游归档哈希在 `tools/resvg/`，本地文件哈希在 `third_party/manifest.json`。 |
| PySide6 / Shiboken / Qt | 6.8.3 | 使用开源分发许可；PySide6 与本应用使用的 Qt Core/Gui/Widgets 依 LGPL-3.0 分发。`third_party/qt/` 保留 Qt 6.8.3 上游 LICENSES 目录的许可文本，不代表所有许可均适用于每个组件。 |
| PyInstaller | 6.22.3 | GPL-2.0-or-later 及其允许分发所构建应用的例外；构建时从已安装软件包复制原始许可。 |
| CPython 及其他构建依赖 | 以每次发行记录为准 | 构建时收集 Python 原始许可、依赖包自带许可及版本清单。 |

Windows 发行包将这些材料放在 `Documentation/` 与 `Documentation/THIRD_PARTY_NOTICES/`。`tools/collect_licenses.py` 从构建环境复制许可，并写出 `BUILD_DEPENDENCIES.json`；自动构建使用的 Python 版本见 GitHub Actions 日志。请随完整便携目录一起分发这些文件。

Qt/PySide 使用动态库，不应删除或锁定 `_internal/PySide6/` 中的可替换库。MIT 代码没有禁止为调试 Qt/PySide 修改而进行的逆向工程；用户可修改本项目源码并重新构建，或以兼容的修改版动态库替换相应库。不要在再分发时添加阻止这些 LGPL 权利的限制。

对应组件的源码与构建说明：

- [Qt 6.8.3 源码归档](https://download.qt.io/archive/qt/6.8/6.8.3/single/) 与 [Qt 构建文档](https://doc.qt.io/qt-6.8/build-sources.html)。
- [PySide/Shiboken 6.8.3 源码](https://code.qt.io/cgit/pyside/pyside-setup.git/tree/?h=v6.8.3) 与 [构建文档](https://doc.qt.io/qtforpython-6.8/building_from_source/index.html)。
- [Qt 第三方组件说明](https://doc.qt.io/qt-6.8/licenses-used-in-qt.html)、[PyInstaller 许可](https://pyinstaller.org/en/stable/license.html) 与 [CPython 源码](https://github.com/python/cpython)。

语料文件的贡献者和来源元数据来自上游公开数据。旧的 `chinese-gushiwen-sentences.json` 不随本仓库或发行包分发。导入、发布或商业使用自己选择的句子时，仍需确认相应内容的使用权。
