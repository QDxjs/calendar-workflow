## 每日文学日历 v0.6.10

0.6.10 修复 Windows 下 GitHub 更新检查与下载的 HTTPS 证书链验证，并继续使用 Windows 系统信任库；系统信任的 HTTPS 代理和缺失的中间证书可正常处理，未受信任的证书仍会被拒绝。

0.6.9 为 Windows 便携版增加手动检查更新、下载进度和确认后安装。程序会核对 GitHub Release 标签、固定附件名、SHA-256 和 ZIP 内容清单，拒绝路径越界及特殊文件；独立安装进程等待旧程序退出，保留 `calendar_runs/`，安装或重启失败时回滚旧版。

此前 0.6.3–0.6.8 增加个人署名、多版式与按日张数、语录搜索挑选和整批预览，并修复搜索框回车行为。完整说明见 [CHANGELOG.md](https://github.com/QDxjs/calendar-workflow/blob/main/CHANGELOG.md)。

Windows x64 用户下载 `CalendarWorkflow-0.6.10-windows-x64.zip`，完整解压后运行 `CalendarWorkflow.exe`。包内附 ZIP 的 SHA-256 校验文件与第三方许可资料。生成日历仍可离线使用；检查或安装更新需要网络及程序目录写入权限。
