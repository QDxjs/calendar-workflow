# 参与贡献

问题请使用 [Issues](https://github.com/QDxjs/calendar-workflow/issues) 模板。先说明使用场景，再提出改动；小修复可直接提交 Pull Request。界面、版式或导出行为发生变化时请提供前后示例。

建议使用 Windows x64、Python 3.12 和虚拟环境。在项目根目录执行：

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements-build.txt
.\.venv\Scripts\python.exe tools/check_project.py
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
```

完整桌面单页检查：

```powershell
$env:QT_QPA_PLATFORM = 'offscreen'
.\.venv\Scripts\python.exe launcher.py --verify-portable
```

日期、模板、渲染或批次发布逻辑发生较大变化时，再做一次全年验证；普通文档修改无需本地打包。自动检查会验证 Python 3.10 和 3.12，PNG 渲染当前使用随附的 Windows x64 resvg。

贡献原创代码和文档意味着按本项目 MIT 许可证提供这些改动，并保留原版权说明。第三方代码、图片、字体或语料必须附来源和对应许可；不能把第三方资源改标为 MIT。不要提交个人日历、用户设置、未授权句库、密钥、构建目录或完整发行 ZIP。

不要仅为消除报错而更新 `third_party/manifest.json` 的哈希；资源升级时应先核对官方来源、许可证及对应结果，再更新记录。依赖升级需同步 `requirements*.txt` 和第三方说明，并完成相关验证；构建脚本从依赖文件读取固定版本。
