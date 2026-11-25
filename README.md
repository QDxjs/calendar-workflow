# 每日文学日历 · Calendar Workflow

[![CI](https://github.com/QDxjs/calendar-workflow/actions/workflows/ci.yml/badge.svg)](https://github.com/QDxjs/calendar-workflow/actions/workflows/ci.yml)
[![Release](https://img.shields.io/github/v/release/QDxjs/calendar-workflow)](https://github.com/QDxjs/calendar-workflow/releases/latest)
[![Code license: MIT](https://img.shields.io/badge/code-MIT-blue.svg)](LICENSE)

离线生成每日文学日历的 Windows 桌面工具。选择单日、日期范围、周、月或年，使用九种版式导出 **1122 × 1402** 的 PNG、可编辑 SVG、离线网页预览和可恢复的批次清单。当前版本：**0.5.4**。

## 直接使用

1. 在 [Releases](https://github.com/QDxjs/calendar-workflow/releases/latest) 下载 `CalendarWorkflow-版本号-windows-x64.zip`。
2. 完整解压到可写入的目录，双击 `CalendarWorkflow.exe`。无需安装 Python，也无需联网。
3. 选择日期范围、版式与保存位置，点击“生成日历”。完成后点击“预览日历”。

请保留 EXE、`_internal/` 和 `Documentation/` 的完整结构。发行页的 **Source code** 是开发源码；普通 Windows 用户应下载上述便携 ZIP。详细操作见 [USER_GUIDE.md](USER_GUIDE.md)。

## 功能

- 九种 SVG 版式 A–I，可指定一种，也可随机抽选；随机模式尽量避免相邻日期版式相同。
- 本地 Hitokoto b/d/h/k 语料固定版本，保留出处及 UUID；同批次内语录正文不重复。
- 导入自己的 UTF-8 JSON / JSONL 语料，预览有效、重复和无效记录后再确认使用。
- 生成 SVG、PNG、`index.html` 和 `manifest.csv`；网页支持离线搜索、版式筛选与单页下载。
- 按清单恢复内容和实际版式；生成前预检，失败或取消时清理暂存文件，拒绝覆盖已有批次。
- 包内文件哈希校验，以及随发行包保留的第三方许可和构建依赖记录。

## 从源码运行

当前完整桌面及 PNG 流程面向 **Windows x64**。建议 Python **3.12**，CI 同时检查 3.10 和 3.12。随附 PNG 渲染器是 Windows 可执行文件，尚未验收 macOS / Linux。

```powershell
git clone https://github.com/QDxjs/calendar-workflow.git
cd calendar-workflow
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe launcher.py --desktop
```

无需激活虚拟环境即可使用上述命令。首次安装依赖需要联网；安装完成后的日历生成使用本地文件。

终端菜单：`.\.venv\Scripts\python.exe launcher.py --console`。源码版不带参数运行 `launcher.py` 时也进入终端菜单；桌面界面请明确使用 `--desktop`。

手动 CSV 预检及生成：

```powershell
.\.venv\Scripts\python.exe generate.py --input content.csv --check
.\.venv\Scripts\python.exe generate.py --input content.csv --seed 31415
```

CSV 必须包含唯一表头 `date,quote,source,layout`，日期使用 `YYYY-MM-DD`；正文或出处含逗号时请按 CSV 规则加双引号。版式可填 A–I，或填 `R` / `auto` / 留空以随机选择。预检不生成 PNG，也不写出批次。

## 输出与恢复

便携版默认保存到 EXE 同目录的 `calendar_runs/`；源码版默认保存到 `output/calendar_runs/`，也可在界面另选位置。每次生成一个独立批次：

```text
批次目录/
├── svg/2027-01-01_layout-C.svg
├── png/2027-01-01_layout-C.png
├── index.html
└── manifest.csv
```

清单记录日期、ISO 周、实际版式、语录、出处、UUID、种子及程序版本。桌面版可点击“从批次清单恢复…”；命令行示例：

```powershell
.\.venv\Scripts\python.exe generate.py --replay .\某个批次\manifest.csv --outdir .\restored-batch
```

恢复目录必须尚未存在。恢复使用当前模板、字体和渲染器；如需保存原始像素效果，请同时备份原图片。

## 检查与构建

```powershell
.\.venv\Scripts\python.exe tools/check_project.py
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
.\.venv\Scripts\python.exe -m pip install -r requirements-build.txt
$env:PATH = "$PWD\.venv\Scripts;$env:PATH"
.\build_portable.ps1
```

构建脚本在临时目录打包，收集许可并执行单页桌面自检，通过后才生成 `dist/CalendarWorkflow/`，已有目录不会被覆盖。发布版本标签会触发 GitHub Actions，自动构建便携 ZIP、校验文件并创建 Release。具体步骤见 [RELEASE_HANDOFF.md](RELEASE_HANDOFF.md)。

## 开源与维护

原创代码和文档采用 [MIT](LICENSE)，版权人为青灯。特别感谢 [Hitokoto 一言开源社区](https://github.com/hitokoto-osc/sentences-bundle) 和 [resvg](https://github.com/linebender/resvg)。第三方组件的许可边界见 [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md)。

内置语料来自固定版本的漫画（b）、文学（d）、影视（h）、哲学（k）四类，共 2,631 条原始记录；筛选、去重后当前有 2,400 条可用记录。上游声明 AGPL-3.0，同时提示并不拥有所有句子的著作权。**本项目 MIT 不会额外授予语料或单条句子的使用权。** 来源、固定提交与随附许可见 [HITOKOTO_SOURCE.md](HITOKOTO_SOURCE.md) 和 `data/hitokoto/`；公开或商业再分发前请核对相应内容权利。

- 不熟悉 GitHub 维护：先看 [MAINTENANCE.md](MAINTENANCE.md)。
- 报告问题或建议：[Issues](https://github.com/QDxjs/calendar-workflow/issues)。
- 参与修改：[CONTRIBUTING.md](CONTRIBUTING.md)；安全问题：[SECURITY.md](SECURITY.md)。
- 版本变化：[CHANGELOG.md](CHANGELOG.md)；后续方向：[ROADMAP.md](ROADMAP.md)。
