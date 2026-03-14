# PCB Reverse Annotator

基于 **Python 3.11+ + PySide6** 的桌面工具，用于 PCB 逆向分析中的图像叠加与引脚/焊盘标注。

## 功能概览

- 多图导入（PNG/JPG/BMP），同一画布叠加
- 子图像支持拖动、缩放、旋转、锁定、Z 顺序调整
- 标记点仅允许创建在子图像上，且使用局部坐标绑定
- 图像变换时标记点同步运动，避免漂移
- 同 label 标记点联动高亮（hover 与点击常亮）
- 右侧 label 统计列表（含搜索）与画布双向联动
- JSON 工程保存/加载（优先相对路径）

## 安装

```bash
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\\Scripts\\activate
pip install -U pip
pip install PySide6
```

## 运行

```bash
python -m pcb_reverse_annotator
```

## 工程文件

保存为 JSON，包含：

- `images`: 子图像状态（路径、位置、缩放、旋转、锁定、Z 层级、尺寸）
- `markers`: 标记点状态（所属图像、局部坐标、label、note、锁定）

