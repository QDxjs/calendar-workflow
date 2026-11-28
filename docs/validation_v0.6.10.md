# v0.6.10 发布验收

## 本机验证

- Windows 10 x64、Python 3.10.0、PySide6 6.8.3；公开文件检查通过，共 169 个文件及 5 个固定资源哈希。
- `python -m unittest discover -s tests -v`：142 项通过，包括 Windows PowerShell 更新安装与失败回滚检查。
- `python launcher.py --verify-portable --full-year`：366 页全年流程、九版首张预览一致性、清单恢复、取消重试、历史、手写和随机多版式验收通过。
- `python tools/verify_calendar_layouts.py`：21,591 个内置语录/版式 SVG 检查、九张原尺寸 PNG、恢复和截图回归通过。
- `python tools/verify_desktop_ui.py`：Qt 缩放 1、1.25、1.5、2 下的桌面布局通过。
- `python tools/verify_gallery_ui.py`：离线 Chromium 导航、筛选、灯箱、下载和同日多图交互检查通过。
- README 展示图由当前 0.6.10 实际 Qt 界面、预览对话框和日历渲染代码重新生成。
- 独立便携构建及 `--FullAcceptance` 通过；包内 285 文件清单与哈希检查通过，隔离环境全年验收 366 页。
- 单独导出的 Windows ZIP 为 47,891,269 字节，SHA-256：`24a105e28b7f5314aa5d38fec9efb3b66fd1ed29216d5ed26782f0a4ea4c9051`。解压副本再次通过包校验及 366 页全年验收。GitHub Actions 使用 Python 3.12 构建，公开发行附件哈希以发行页为准。

## GitHub 验收

- [CI run 46116647472](https://github.com/QDxjs/calendar-workflow/actions/runs/46116647472)：Windows/Python 3.10 与 3.12 均通过公开文件检查、回归测试、桌面流程、离线 Chromium、全语料版式及 4 种 Qt 缩放。
- [v0.6.10 Release run 46117001370](https://github.com/QDxjs/calendar-workflow/actions/runs/46117001370)：Windows/Python 3.12 便携构建、许可收集、发行包检查和 366 页全年验收通过，GitHub Release 上传成功。
- [公开 v0.6.10 发行页](https://github.com/QDxjs/calendar-workflow/releases/tag/v0.6.10) 的 `CalendarWorkflow-0.6.10-windows-x64.zip` 为 52,782,677 字节，SHA-256：`41f78db26a770137188fc9390725fb0f20d2cf8f35f46a343275a52f64b184fa`。下载后校验附件与 306 项包清单，并在隔离的 Python 3.12 便携环境再次完成 366 页全年自检。

模拟 Qt 缩放不代替目标电脑的实际显示器缩放；自动更新仍应在目标 Windows 设备和网络/代理环境中按需实际试用。
