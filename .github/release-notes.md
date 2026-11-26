0.5.7 新增以下桌面功能，同时包含 0.5.5 的日期输入、生成控件锁定及保存位置校验改进：

- **查看版式示意**：后台渲染 A–I 九种缩略图，滚动比较后直接选用。
- **查看首张效果**：在导出前核对真实首张；与随后生成共用整批内容计划，内容设置不变时首张一致。失败或取消可沿用计划重试。
- **导入诊断**：只读表格分别显示可导入记录与未导入原因，定位 JSON 记录或 JSONL 原始行号，完整查看正文、出处和重复来源。正文须为去除首尾空白后的 4–58 个字符。
- **原创应用图标**：Windows EXE、窗口和任务栏使用日历与展开书页图标。
- **新版介绍图片**：仓库 README 更新真实桌面界面、首张预览、导入诊断，以及九种版式的实际导出效果。

完整变更见 [CHANGELOG.md](https://github.com/QDxjs/calendar-workflow/blob/v0.5.7/CHANGELOG.md)。

Windows x64 用户请下载 `CalendarWorkflow-版本号-windows-x64.zip`，完整解压后双击 `CalendarWorkflow.exe`。保留 `_internal` 与 `Documentation`，无需安装 Python。GitHub 自动附带的 Source code 压缩包供开发者使用。

同页的 `.sha256` 文件可核对 ZIP 的 SHA-256。便携包内置文件完整性清单和第三方许可；应用未使用代码签名。维护及源码运行说明见仓库 README 和 MAINTENANCE.md。

原创代码采用 MIT；内置 Hitokoto 语料及 Qt/PySide、resvg 等组件保留各自许可。语料上游的许可声明不代表拥有每一句话的著作权；再次分发或商业使用时请核查对应权利。
