# Windows 便携版构建与发布

当前应用版本为 **0.6.2**。发行前确认 `generate.APP_VERSION` 与 `v0.6.2` 标签一致。普通用户通过 [Releases](https://github.com/QDxjs/calendar-workflow/releases) 下载 `CalendarWorkflow-版本号-windows-x64.zip`。完整解包后双击 `CalendarWorkflow.exe`；不要单独复制 EXE。

## 推荐：由 GitHub Actions 发布

将代码推送到 `main`，等待 CI 通过，再创建与程序版本一致的 `vX.Y.Z` 标签并推送，当前为 `v0.6.2`。`.github/workflows/release.yml` 将：

1. 确认标签存在、版本号匹配，且提交属于 `main`。
2. 在 Windows、Python 3.12 下安装固定的构建依赖。
3. 检查公开文件、资源哈希和回归测试。
4. 构建完整 onedir 应用，收集许可及依赖版本；执行九种版式示意、首张与导出一致性、单页桌面生成、清单恢复、取消清理和重试自检。
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
.\export_portable.ps1 -PackageDirectory .\dist\CalendarWorkflow -ArchivePath .\dist\CalendarWorkflow-0.6.2-windows-x64.zip
Get-FileHash .\dist\CalendarWorkflow-0.6.2-windows-x64.zip -Algorithm SHA256
```

构建脚本会在临时目录打包，缺少锁定依赖时尝试安装；首次安装需要联网。通过自检后才发布到 `dist/CalendarWorkflow/`。如果目标目录已存在，先另行保留旧版或指定新的 `CALENDAR_RELEASE_DIR`，不会覆盖。

## 包内容与检查

包顶层为 `CalendarWorkflow.exe`、`_internal/`、简明 `README.md`、`Documentation/` 以及运行时生成的 `calendar_runs/`。许可、来源、手册和构建依赖记录位于 `Documentation/`。EXE 内嵌应用图标，运行时必需的 `_internal/assets/calendar.ico` 随包保留，顶层无需额外图标文件。原始 MIT 许可、Hitokoto AGPL 文本、resvg 声明、Qt/PySide 许可与 Python 许可应完整保留。

运行 `CalendarWorkflow.exe --verify-package` 可检查随包文件清单及哈希；`calendar_runs/` 是应用生成的用户数据，不在软件包清单内。哈希清单用于发现复制遗漏或版本混用，不是数字签名。

## 0.6.2 空正文修订验收

单日手写正文与出处均允许为空，空白页和仅出处页须通过实际九版式 SVG/PNG 导出、预览一致性、清单恢复与历史识别。正文为空时省略正文元素及装饰引号，只显示出处时不创建空正文或多余出处分隔线。清单列不变，空白页不参与重复语录检查，带语料编号却没有正文仍视为损坏。

本次修改了共享排版与 B/G 版式，最终 ZIP 解包副本运行包校验和全年自检；新增空白页桌面流程与九版输出纳入便携自检。结果与限制记录在仓库 docs/validation_v0.6.2.md；本次保留所有旧便携包，不自动提交或发布。

## 0.6.1 历史验收要求

新增模块 `content_sources` 与 `manual_quote_panel` 通过正常导入由 PyInstaller 收集；便携自检实际运行手写桌面预览与生成，并检查九版空出处 PNG、换行清单恢复、随机版式过滤及全部版式溢出。无新增运行依赖，不改 CLI 内容参数或清单列。

运行全套 unittest、公开文件检查、源码 `--verify-portable` 和离线 Chromium 检查；网页样例包含多行手写、空出处及特殊字符安全显示。窄窗口需核对手写区域、字段错误、滚动及操作按钮可达性。历史详情核对本机“清单更新时间”，不作为生成时间。

本版小幅调整版式 B 空出处渲染，最终 ZIP 解包副本追加 `--verify-portable --full-year`，移除系统 Python PATH 并执行 `--verify-package`。本地验收结果与环境限制见仓库 `docs/validation_v0.6.1.md`；便携包随附文档为构建时快照，后续最终解包记录单独补充。未自动提交、推送或公开发布。

## 0.6.0 历史验收记录

本版修改了模板，最终解包副本必须运行 `CalendarWorkflow.exe --verify-portable --full-year`，核对 366 页、九版式、首张一致性、恢复/取消/重试及历史摘要。单页自检也包含历史发现及独立取消检查。

新增界面验收：便携版更改目录后重启、恢复默认、设置失效诊断；历史窗口选择位置、停止/刷新、缺网页仍可恢复、损坏清单不阻断其他记录。查看不得修改原文件，恢复始终写新目录。

新增网页验收：离线 `file://` 下的灯箱、方向键/Esc、焦点返回、比例切换、当前下载、跨年月份组合筛选及坏图。可运行 `python tools/verify_gallery_ui.py --screenshots output/validation-v0.6.0` 使用固定 PySide6 的 Chromium 引擎验证；此工具不引入应用运行依赖，也不能代替 Edge/Chrome 和真实系统缩放验收。

当前源码在 Windows 10 x64、Python 3.10.0 / PySide6 6.8.3 下通过 63 项测试、源码桌面自检及离线 Chromium 交互检查；另外实际运行历史扫描线程并检查主窗口窄布局及历史窗口的离屏截图。最终 ZIP 解包副本通过 283 项包文件校验及 366 页全年自检，验证时移除了系统 Python 路径。Python 3.12、干净无 Python 的 Windows 目标机、Edge/Chrome 与真实 125%/150% 缩放仍待相应环境验收，未标为通过。完整本地记录见仓库 `docs/validation_v0.6.0.md`；尚未推送或发布。

## 0.5.7 历史验收参考

以下是发行前需要按改动范围核对的检查项目。自动测试、离屏检查与实际桌面交互验收应分别记录，不能互相替代。

1. **版式示意和首张一致性**：桌面内实际查看 A–I 九张示意，确认使用同一段内置示例文字且标明“版式示意”。用多日范围比较“查看首张效果”和随后正式生成的首张，覆盖随机版式、种子留空。修改日期或范围、版式、种子、语料后确认旧预览失效；只改保存位置则不应改变计划。失败或取消后沿用原计划重试；成功后清除本批计划。下一批留空种子时重新抽选，固定种子在参数和语料相同的情况下可复现。
2. **预览与生成操作**：确认版式示意和首张效果都在后台渲染、可取消、清理临时目录，不创建正式批次或自动打开浏览器。正式生成后仍由用户点击“预览日历”打开批次网页；取消或失败不得影响上次成功批次。
3. **导入诊断**：用 JSON 数组、单对象和含空行的 JSONL 样例核对位置，JSONL 行号须按源文件物理行计数。检查只读虚拟表格的“可导入”“未导入原因”两个标签、正文和最终展示出处、选中行完整详情、无效具体原因与实际长度，以及重复项指向首次保留位置。无有效记录时确认按钮必须禁用；取消保留现有语料，确认才替换本次运行语料，源文件保持不变。语法错误仍应弹出错误提示。GUI 的空结果诊断不得改变 CLI `load_quotes` 无有效记录时抛错的行为。
4. **长度和排版**：确认桌面导入正文在去除首尾空白后按 4–58 字计数，标点和内部空白计入，正文不截断且出处独立。检查固定文本框的估算宽度换行、行长均衡和必要时缩字；用诗歌分行及特殊符号样例实际查看首张。该检查不代表字体精确测量或碰撞检测。同一长度筛选也用于内置语料和命令行 `--quotes` 的 JSON／JSONL 语料库，不得套成 CLI CSV 或既有 manifest 的 58 字统一限制。
5. **单页、清单恢复和取消重试**：运行打包后的单页桌面自检（`CalendarWorkflow.exe --verify-portable`）；从既有 manifest 恢复到新的空目录并核对内容；取消一批任务，确认未发布半成品，再重试并成功生成。随后核对包清单、归档文件及 SHA-256。
6. **窄窗口和缩放**：维护者在实际桌面环境完成窄窗口与系统缩放比例下的视觉验收，记录测试环境和观察结果。没有实际检查前不得标为通过。

0.5.7 在本地 Windows 10 x64 通过 39 项自动测试、源码桌面自检和便携包自检，后者移除了系统 Python 的环境路径。另在实际便携程序窗口中核对了九种版式的加载、滚动和选用，首张预览的适应窗口与原始尺寸显示，以及导入诊断的两个标签页、完整详情、确认导入和更换语料后旧预览失效。窄窗口、其他系统缩放比例及干净目标机仍需按需验收。最终发行以 GitHub Actions 检查及公开 ZIP 的实际校验结果为准；本次未执行全年验收。

后续若日期计算、模板、渲染或批次发布逻辑发生重要变化，或交付大版本，可在最终解包副本运行一次 `CalendarWorkflow.exe --verify-portable --full-year`，验证 366 页。未安装 Python 的干净 Windows、实际离线环境和真实缩放比例仍需在相应目标机按需验证，不能以 CI 冒烟代替。
