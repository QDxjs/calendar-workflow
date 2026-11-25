# Windows 便携版构建与发布

当前应用版本为 **0.5.4**，以 `generate.APP_VERSION` 为准。普通用户通过 [Releases](https://github.com/QDxjs/calendar-workflow/releases) 下载 `CalendarWorkflow-版本号-windows-x64.zip`。完整解包后双击 `CalendarWorkflow.exe`；不要单独复制 EXE。

## 推荐：由 GitHub Actions 发布

将代码推送到 `main`，等待 CI 通过，再创建与程序版本一致的 `vX.Y.Z` 标签并推送。`.github/workflows/release.yml` 将：

1. 确认标签存在、版本号匹配，且提交属于 `main`。
2. 在 Windows、Python 3.12 下安装固定的构建依赖。
3. 检查公开文件、资源哈希和回归测试。
4. 构建完整 onedir 应用，收集许可及依赖版本；执行单页桌面生成、清单恢复、取消清理和重试自检。
5. 核对包清单，导出 ZIP 和 SHA-256 文件，创建对应 GitHub Release。

工作流只在发布任务中取得写入 Releases 的权限；常规 CI 只有仓库读取权限。所有外部 Actions 固定到提交 SHA。不要移动已发布标签或自动覆盖现有发行文件。

## 本地构建

需要 Windows x64 和 Python，建议使用 Python 3.12 虚拟环境：

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements-build.txt
$env:PATH = "$PWD\.venv\Scripts;$env:PATH"
$env:QT_QPA_PLATFORM = 'offscreen'
.\build_portable.ps1
.\export_portable.ps1 -PackageDirectory .\dist\CalendarWorkflow -ArchivePath .\dist\CalendarWorkflow-0.5.4-windows-x64.zip
Get-FileHash .\dist\CalendarWorkflow-0.5.4-windows-x64.zip -Algorithm SHA256
```

构建脚本会在临时目录打包，缺少锁定依赖时尝试安装；首次安装需要联网。通过自检后才发布到 `dist/CalendarWorkflow/`。如果目标目录已存在，先另行保留旧版或指定新的 `CALENDAR_RELEASE_DIR`，不会覆盖。

## 包内容与检查

包顶层为 `CalendarWorkflow.exe`、`_internal/`、简明 `README.md`、`Documentation/` 以及运行时生成的 `calendar_runs/`。许可、来源、手册和构建依赖记录位于 `Documentation/`。原始 MIT 许可、Hitokoto AGPL 文本、resvg 声明、Qt/PySide 许可与 Python 许可应完整保留。

运行 `CalendarWorkflow.exe --verify-package` 可检查随包文件清单及哈希；`calendar_runs/` 是应用生成的用户数据，不在软件包清单内。哈希清单用于发现复制遗漏或版本混用，不是数字签名。

日常构建只执行单页验收。日期、模板、渲染或批次发布逻辑发生重要变化，或大版本交付时，在最终解包副本运行一次 `CalendarWorkflow.exe --verify-portable --full-year`，验证 366 页。未安装 Python 的干净 Windows、实际离线环境和真实缩放比例仍需在相应目标机按需验证，不能以 CI 冒烟代替。
