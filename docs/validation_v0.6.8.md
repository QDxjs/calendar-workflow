# v0.6.8 发布验收记录

发布日：2026-11-28。公开仓库提交：`604650890b5b2837ad7f10422e620aa640ebe9c2`；标签：`v0.6.8`。

## 源码与自动检查

- Windows 10 x64、Python 3.10.0、PySide6 6.8.3：127 项 unittest 通过；公开文件检查通过（165 个文件，5 项固定资源哈希）。
- 源码便携自检通过，包括随机制作、按日张数、语录挑选、版式示意、整批预览、历史和清单恢复、取消与重试。
- 全语料排版检查通过：2,399 条符合规则的内置语录 × 9 种版式，共 21,591 次 SVG 检查；九种 PNG 均为 1122 × 1402，并通过清单恢复和示例页检查。
- Qt 缩放 1、1.25、1.5、2 下的桌面界面检查通过；离线 Chromium 网页检查通过，包括灯箱键盘操作、筛选、下载、坏图和同日同版式多张页面。
- 本机便携包包含 283 个清单文件，通过包哈希校验及 366 页全年 PNG/SVG 全量验收。
- GitHub Actions CI 的 Python 3.10 与 3.12 作业均成功：<https://github.com/QDxjs/calendar-workflow/actions/runs/46099902545>。

## 公开发行包

- Release：<https://github.com/QDxjs/calendar-workflow/releases/tag/v0.6.8>
- 发布工作流成功，包括 Windows Python 3.12 构建、完整回归、366 页全年验收、ZIP 导出及 GitHub Release 上传：<https://github.com/QDxjs/calendar-workflow/actions/runs/46100287006>。
- 下载后的公开 ZIP 包含 304 个清单文件；运行 `CalendarWorkflow.exe --verify-package` 及 `CalendarWorkflow.exe --verify-portable --full-year` 均通过。后者在隔离临时目录及系统 Python 路径之外完成，报告 366 页及新增工作流检查通过。
- 公开 ZIP SHA-256：`da0256d57e79beca6b7bae7b38941121638e9a2d9dccfda822a572dc69935f2b`。校验文件随 GitHub Release 附件提供。

公开包由 GitHub 的 Python 3.12 环境构建；本机单独构建由 Python 3.10 完成，因此两个环境生成的 ZIP 大小和 SHA-256 不同。验收以各自包清单、官方发布校验值和公开包实测为准。

界面缩放是在 Qt 离屏模式下模拟，不能替代真实显示器上的系统缩放；没有在干净的实体目标电脑上验证不同 Windows 版本。发行包没有代码签名。
