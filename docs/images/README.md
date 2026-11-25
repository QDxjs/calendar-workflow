# README 展示图片

这些图片展示应用 0.5.4 的界面和真实导出结果，随项目文档按根目录 MIT 许可证提供。示例使用古代诗句，不包含用户私人语料、日历批次或个人文件路径。

| 文件 | 内容与来源 |
| --- | --- |
| `desktop.png` | 直接渲染 `desktop.CalendarWindow` 的实际 Qt 桌面组件，设置日期 `20270101`、随机版式及种子 `31415`；保存目录显示为通用示例 `calendar_runs`。无操作系统标题栏，界面布局和功能未改动。 |
| `calendar-examples.png` | A、C、D 三种版式的实际 PNG 缩略拼图，只增加版式名称和画布边距。 |
| `all-layouts.png` | A–I 九种版式的实际 PNG 对照图；排序从左至右、从上至下。 |
| `calendar-single.png` | C 版式的 1122 × 1402 原尺寸 PNG，未缩放或修改。 |

生成输入为仓库的 `examples/template_gallery.csv` 和 `examples/template_gallery_F-I.csv`，示例日期为 2027-01-01，诗句为左思《咏史·郁郁涧底松》的“郁郁涧底松，离离山上苗。”。日历内容由现有 `generate.prepare_pages` / `generate.write_batch` 产生，没有修改模板或渲染逻辑。

重新生成示例可在项目根目录执行下列命令，目标目录必须尚未存在：

```powershell
python generate.py --input examples/template_gallery.csv --outdir output/readme-gallery-a-e
python generate.py --input examples/template_gallery_F-I.csv --outdir output/readme-gallery-f-i
```

仓库仅收录经过挑选的上述文档图片；完整运行批次、清单和网页仍保存在被忽略的 `output/` 下。
