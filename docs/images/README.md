# README 展示图片

这些图片展示应用 0.6.8 的实际界面和真实导出结果，随项目文档按根目录 MIT 许可证提供。示例使用古代诗句，不包含用户私人语料、日历批次或个人文件路径。

| 文件 | 内容与来源 |
| --- | --- |
| `desktop.png` | 直接渲染 `desktop.CalendarWindow` 的实际 Qt 桌面组件，显示默认随机制作、日期 `20270101` 及通用示例目录。无操作系统标题栏，界面布局和功能未改动。 |
| `quote-picker.png` | 实际 `QuotePickerDialog` 语录挑选窗口；确定性推荐三至五条内置语录，并在后台生成所选候选的真实页面预览。 |
| `batch-preview.png` | 实际 `BatchPreviewDialog`，以固定种子准备同一日期的三张日历，并通过与生成相同的渲染任务取得预览图。 |
| `first-page-preview.png` | 实际 `FirstPageDialog` 首张预览窗口；以导入的左思诗句建立生成计划，经 `run_preview_job` 渲染，并核对 PNG 字节与 C 版式正式导出一致。 |
| `quote-import.png` | 实际 `QuotePreviewDialog` 导入诊断窗口；显示演示文件中的两条有效记录、一条重复记录和一条过短记录，选中重复项查看完整详情。 |
| `calendar-examples.png` | A、C、D 三种版式的实际 0.6.8 PNG 缩略拼图，只增加版式名称和画布边距。 |
| `all-layouts.png` | A–I 九种版式的实际 PNG 对照图；排序从左至右、从上至下。 |
| `calendar-single.png` | C 版式的 1122 × 1402 原尺寸 PNG，未缩放或修改。 |

生成输入为仓库的 `examples/template_gallery.csv` 和 `examples/template_gallery_F-I.csv`，示例日期为 2027-01-01，诗句为左思《咏史·郁郁涧底松》的“郁郁涧底松，离离山上苗。”。导入诊断另含周兴嗣《千字文》的“天地玄黄，宇宙洪荒。”、一条重复的左思诗句及过短的“短”字演示项。日历内容由现有 `generate.prepare_pages` / `generate.write_batch` 产生，没有修改模板或渲染逻辑。

安装项目桌面依赖后，可在 Windows 的项目根目录运行以下命令，重新生成全部展示图片。脚本读取系统已有的 Segoe UI 与微软雅黑字体，直接渲染实际 Qt 组件（不含操作系统标题栏），覆盖本目录 PNG，并自动清理临时日历批次：

```powershell
python tools/render_readme_images.py
```

重新生成示例可在项目根目录执行下列命令，目标目录必须尚未存在：

```powershell
python generate.py --input examples/template_gallery.csv --outdir output/readme-gallery-a-e
python generate.py --input examples/template_gallery_F-I.csv --outdir output/readme-gallery-f-i
```

仓库仅收录经过挑选的上述文档图片；手动生成的完整运行批次、清单和网页保存在被忽略的 `output/` 下。
