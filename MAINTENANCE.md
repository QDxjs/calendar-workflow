# 青灯的 GitHub 维护手册

仓库：[QDxjs/calendar-workflow](https://github.com/QDxjs/calendar-workflow)。`main` 保存公开源码；普通用户在 Releases 下载 Windows 便携版。GitHub 是版本和发布入口，本地日历输出请另外备份。

## 平时只需要关注三件事

| 位置 | 什么时候看 | 怎么处理 |
| --- | --- | --- |
| Actions | 每次提交或发布后 | 绿色表示配置的检查通过；红色先打开失败步骤，不发布未通过的版本。可以直接把失败链接交给 Codex 修复。 |
| Issues | 有反馈时 | 先确认版本和复现步骤；无法复现就请对方补充最小样例，解决后再关闭。个人维护可以按精力安排，不承诺固定响应时限。 |
| Pull requests / Dependabot | 收到更新提醒时，或每月集中看一次 | Dependabot 每月提出依赖和 Actions 更新。检查通过后再审阅合并；Qt/PySide 等大版本先检查兼容性及许可证。没有开启自动合并。 |

你可以直接对 Codex 说：“检查这个仓库的失败检查和待处理更新，修复后验证，再同步到 GitHub。”无需先学会所有 Git 命令。

## 修改后如何同步源码

在已连接这个仓库的项目文件夹中执行；文档和普通修复可以提交到 `main`，较大的改动建议开分支和 Pull Request：

```powershell
git pull --ff-only
git status --short
python tools/check_project.py
python -m unittest discover -s tests -v
git add .
git diff --cached --stat
git diff --cached --check
git commit -m "描述这次解决的问题"
git push origin main
```

如果 `git pull` 提示本地有未提交改动，先保留改动并检查，不要运行 `reset --hard` 或强制推送。检查脚本只打印可能有问题的文件名，不打印匹配到的密钥；它只是辅助检查，提交前仍要看文件清单。

`.gitignore` 排除了 `output/`、`calendar_runs/`、`dist/`、虚拟环境、缓存、归档、密钥文件与旧语料。已被 Git 跟踪的文件不会因加入忽略规则而自动移除；如果误提交了口令，先吊销口令，再处理历史。

## 什么时候发布新版本

只有想让用户下载一个新版本时才发布。普通文档修改不用打包。

1. 修改 `generate.py` 的 `APP_VERSION`，例如从 `0.5.4` 改为 `0.5.5`。
2. 在 `CHANGELOG.md` 顶部写新版本变化，同步 README、使用手册和 `.github/release-notes.md`。界面改动后可在 Windows 运行 `python tools/render_readme_images.py` 更新实际界面与导出图片，并核对 `docs/images/README.md` 的版本和说明。
3. 按上节提交并推送，等待 Actions 的 CI 通过。
4. 在当前提交创建并推送版本标签：

```powershell
git tag -a v0.5.5 -m "Release 0.5.5"
git push origin v0.5.5
```

`Release Windows portable` 会检查标签与版本号、运行回归、构建及自检，再创建 Release，上传便携 ZIP 和 `.sha256`。构建失败会停止发布；可从 Actions 查看原因。工作流支持手动对已有标签重试；已经存在的 Release 不会被自动覆盖。已经发布的版本标签不移动，修复后使用新版本号。

## 更新依赖和第三方资源

- `requirements.txt` 固定桌面依赖；`requirements-build.txt` 固定打包依赖。
- Python 小版本升级也要重新构建并检查便携包；构建记录放在包内 `Documentation/BUILD_DEPENDENCIES.json`。
- 更新 Qt/PySide 时同步 `third_party/qt/` 的版本许可文本及来源说明。
- CI 会核对 PySide6 固定版本与 Qt 许可来源版本；Dependabot 的版本升级需要完成许可同步后才能通过这项检查。
- 更新语料或 resvg 时先核对官方来源和许可，再更新 `third_party/manifest.json`。不能为了让检查通过而直接换哈希。
- 源码保持 MIT；第三方语料及工具保留自己的许可，新增素材必须有明确的使用权。

## 维护成本与备份

这是个人维护的公开项目，不要求固定发版频率。仓库已配置提交检查、月度依赖更新和版本标签发布；这些功能不会每天替你更改代码。GitHub Actions 的运行额度和存储政策以账号实际计划为准。

源码在本地和 GitHub 各保留一份；重要版本另保留发行 ZIP 与 SHA-256。生成的日历、私人语料和本机设置不进入公开仓库，请保存在你自己的备份位置。当前便携程序未做代码签名；哈希校验不能替代发行者签名。
