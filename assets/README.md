# 应用图标

`calendar.svg` 是本项目绘制的日历与打开书页组合图标，沿用界面的紫色、纸白与暖金色，按项目 MIT 许可提供。未使用第三方图标或字体。

`calendar.ico` 包含 16、20、24、32、40、48、64、128、256 像素尺寸，用于 Windows EXE、窗口和任务栏；`calendar.png` 是 256 像素预览。

修改矢量源文件后，在项目根目录运行 `python tools/build_icon.py`，通过已随项目提供的 resvg 重建，不需要新增 Python 依赖。便携包将 ICO 放在 `_internal/assets/`，包顶层无需额外图标文件。
