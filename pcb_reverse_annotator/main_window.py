from __future__ import annotations

import uuid
from collections import Counter
from pathlib import Path

from PySide6.QtCore import QPointF, Qt
from PySide6.QtGui import QAction, QPixmap
from PySide6.QtWidgets import (
    QAbstractItemView,
    QApplication,
    QFileDialog,
    QFormLayout,
    QGraphicsItem,
    QGraphicsScene,
    QGraphicsView,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QSplitter,
    QToolBar,
    QVBoxLayout,
    QWidget,
)

from .graphics_items import ImageItem, MarkerItem, create_marker_model
from .models import MarkerModel, SubImageModel
from .project_io import load_project, save_project


class CanvasScene(QGraphicsScene):
    """主画布场景，负责添加标记点模式与点击命中逻辑。"""

    def __init__(self, main_window: "MainWindow") -> None:
        """初始化场景并记录主窗口引用。"""
        super().__init__()
        self.main_window = main_window
        self.add_marker_mode = False

    def mousePressEvent(self, event):
        """在添加模式下仅允许在子图像上创建标记点。"""
        if self.add_marker_mode and event.button() == Qt.MouseButton.LeftButton:
            scene_pos = event.scenePos()
            target_image = self._hit_image_item(scene_pos)
            if target_image is not None:
                local = target_image.mapFromScene(scene_pos)
                self.main_window.create_marker_on_image(target_image, local)
                event.accept()
                return
        super().mousePressEvent(event)

    def _hit_image_item(self, scene_pos: QPointF) -> ImageItem | None:
        """查找鼠标位置命中的最上层图像项。"""
        for item in self.items(scene_pos):
            if isinstance(item, MarkerItem):
                parent = item.parentItem()
                if isinstance(parent, ImageItem):
                    return parent
            if isinstance(item, ImageItem):
                local = item.mapFromScene(scene_pos)
                if item.pixmap().rect().contains(local.toPoint()):
                    return item
        return None


class CanvasView(QGraphicsView):
    """主画布视图，扩展 Ctrl + 滚轮缩放能力。"""

    def __init__(self, scene: QGraphicsScene) -> None:
        """初始化视图并设置默认缩放锚点策略。"""
        super().__init__(scene)
        self.setTransformationAnchor(QGraphicsView.ViewportAnchor.AnchorViewCenter)

    def wheelEvent(self, event) -> None:
        """按住 Ctrl 时以光标为中心缩放整个视图。"""
        if event.modifiers() & Qt.KeyboardModifier.ControlModifier:
            angle = event.angleDelta().y()
            if angle == 0:
                event.accept()
                return

            factor = 1.15 if angle > 0 else 1 / 1.15
            self.setTransformationAnchor(QGraphicsView.ViewportAnchor.AnchorUnderMouse)
            self.scale(factor, factor)
            self.setTransformationAnchor(QGraphicsView.ViewportAnchor.AnchorViewCenter)
            event.accept()
            return
        super().wheelEvent(event)


class MainWindow(QMainWindow):
    """PCB Reverse Annotator 主窗口。"""

    def __init__(self) -> None:
        """初始化 UI、数据索引与事件绑定。"""
        super().__init__()
        self.setWindowTitle("PCB Reverse Annotator")
        self.resize(1400, 900)

        self.scene = CanvasScene(self)
        self.view = CanvasView(self.scene)
        self.view.setRenderHints(self.view.renderHints())

        self.image_items: dict[str, ImageItem] = {}
        self.marker_items: dict[str, MarkerItem] = {}

        self.active_label: str | None = None
        self.hover_label: str | None = None
        self.current_project_path: str | None = None

        self._setup_ui()
        self._setup_toolbar()
        self.scene.selectionChanged.connect(self.refresh_property_panel)

    def _setup_ui(self) -> None:
        """构建主界面布局与右侧面板。"""
        right_panel = QWidget()
        right_layout = QVBoxLayout(right_panel)

        self.label_search = QLineEdit()
        self.label_search.setPlaceholderText("搜索 label...")
        self.label_search.textChanged.connect(self.refresh_label_list)
        right_layout.addWidget(self.label_search)

        self.label_list = QListWidget()
        self.label_list.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.label_list.itemClicked.connect(self.on_label_item_clicked)
        right_layout.addWidget(self.label_list)

        property_widget = QWidget()
        form = QFormLayout(property_widget)
        self.prop_type = QLabel("-")
        self.prop_file = QLabel("-")
        self.prop_pos = QLabel("-")
        self.prop_scale = QLabel("-")
        self.prop_rotation = QLabel("-")
        self.prop_label = QLineEdit()
        self.prop_label.editingFinished.connect(self.apply_marker_text_changes)
        self.prop_note = QLineEdit()
        self.prop_note.editingFinished.connect(self.apply_marker_text_changes)
        self.prop_locked = QLabel("-")

        form.addRow("类型", self.prop_type)
        form.addRow("文件", self.prop_file)
        form.addRow("位置/坐标", self.prop_pos)
        form.addRow("缩放", self.prop_scale)
        form.addRow("旋转", self.prop_rotation)
        form.addRow("Label", self.prop_label)
        form.addRow("Note", self.prop_note)
        form.addRow("锁定", self.prop_locked)
        right_layout.addWidget(property_widget)

        splitter = QSplitter()
        splitter.addWidget(self.view)
        splitter.addWidget(right_panel)
        splitter.setStretchFactor(0, 4)
        splitter.setStretchFactor(1, 1)

        central = QWidget()
        layout = QHBoxLayout(central)
        layout.addWidget(splitter)
        self.setCentralWidget(central)

    def _setup_toolbar(self) -> None:
        """创建工具栏和菜单动作。"""
        toolbar = QToolBar("Tools")
        self.addToolBar(toolbar)

        import_action = QAction("导入图片", self)
        import_action.triggered.connect(self.import_images)
        toolbar.addAction(import_action)

        open_action = QAction("打开工程", self)
        open_action.triggered.connect(self.open_project)
        toolbar.addAction(open_action)

        save_action = QAction("保存工程", self)
        save_action.triggered.connect(self.save_project_as)
        toolbar.addAction(save_action)

        self.add_marker_action = QAction("添加标记点模式", self)
        self.add_marker_action.setCheckable(True)
        self.add_marker_action.triggered.connect(self.toggle_add_marker_mode)
        toolbar.addAction(self.add_marker_action)

        delete_action = QAction("删除选中对象", self)
        delete_action.triggered.connect(self.delete_selected)
        toolbar.addAction(delete_action)

        clear_hl_action = QAction("清除高亮", self)
        clear_hl_action.triggered.connect(self.clear_highlight)
        toolbar.addAction(clear_hl_action)

        fit_action = QAction("适配视图", self)
        fit_action.triggered.connect(self.fit_view)
        toolbar.addAction(fit_action)

        lock_action = QAction("锁定/解锁", self)
        lock_action.triggered.connect(self.toggle_lock_selected)
        toolbar.addAction(lock_action)

        z_up = QAction("上移一层", self)
        z_up.triggered.connect(lambda: self.adjust_selected_image_z(1))
        toolbar.addAction(z_up)

        z_down = QAction("下移一层", self)
        z_down.triggered.connect(lambda: self.adjust_selected_image_z(-1))
        toolbar.addAction(z_down)

        z_top = QAction("置顶", self)
        z_top.triggered.connect(self.bring_selected_to_top)
        toolbar.addAction(z_top)

        z_bottom = QAction("置底", self)
        z_bottom.triggered.connect(self.send_selected_to_bottom)
        toolbar.addAction(z_bottom)

        zoom_in = QAction("放大图像", self)
        zoom_in.triggered.connect(lambda: self.scale_selected_image(1.1))
        toolbar.addAction(zoom_in)

        zoom_out = QAction("缩小图像", self)
        zoom_out.triggered.connect(lambda: self.scale_selected_image(0.9))
        toolbar.addAction(zoom_out)

        rot_left = QAction("逆时针旋转", self)
        rot_left.triggered.connect(lambda: self.rotate_selected_image(-5))
        toolbar.addAction(rot_left)

        rot_right = QAction("顺时针旋转", self)
        rot_right.triggered.connect(lambda: self.rotate_selected_image(5))
        toolbar.addAction(rot_right)

    def import_images(self) -> None:
        """导入多张图片并创建子图像项。"""
        files, _ = QFileDialog.getOpenFileNames(
            self,
            "选择图片",
            "",
            "Images (*.png *.jpg *.jpeg *.bmp)",
        )
        if not files:
            return

        for file in files:
            pixmap = QPixmap(file)
            if pixmap.isNull():
                continue
            image_id = str(uuid.uuid4())
            model = SubImageModel(
                id=image_id,
                file_path=file,
                pos_x=0.0,
                pos_y=0.0,
                width=pixmap.width(),
                height=pixmap.height(),
                z_index=len(self.image_items),
            )
            item = ImageItem(model, pixmap)
            self.scene.addItem(item)
            self.image_items[image_id] = item

        self.refresh_label_list()
        self.fit_view()

    def create_marker_on_image(self, image_item: ImageItem, local_pos: QPointF) -> None:
        """在指定图像项上创建新标记点。"""
        if image_item.model.locked:
            return
        marker_model = create_marker_model(image_item.model.id, local_pos)
        marker = MarkerItem(
            model=marker_model,
            parent_image=image_item,
            on_clicked=self.on_marker_clicked,
            on_hover=self.on_marker_hover,
            on_changed=self.on_marker_changed,
        )
        self.marker_items[marker_model.id] = marker
        self.refresh_label_list()
        self.refresh_highlight()

    def on_marker_clicked(self, marker: MarkerItem) -> None:
        """点击标记点时切换 active_label。"""
        label = marker.model.label
        self.active_label = None if self.active_label == label else label
        self.sync_label_selection()
        self.refresh_highlight()

    def on_marker_hover(self, label: str | None) -> None:
        """悬浮标记点时设置 hover_label，离开后恢复。"""
        self.hover_label = label
        self.refresh_highlight()

    def clear_highlight(self) -> None:
        """清除 hover/active 高亮状态。"""
        self.hover_label = None
        self.active_label = None
        self.label_list.clearSelection()
        self.refresh_highlight()

    def refresh_highlight(self) -> None:
        """按照 hover > active 优先级刷新所有点视觉状态。"""
        effective_label = self.hover_label if self.hover_label else self.active_label
        for marker in self.marker_items.values():
            if not effective_label:
                marker.setOpacity(1.0)
                marker.set_highlighted(False)
            elif marker.model.label == effective_label:
                marker.setOpacity(1.0)
                marker.set_highlighted(True)
            else:
                marker.setOpacity(0.5)
                marker.set_highlighted(False)

    def refresh_label_list(self) -> None:
        """根据标记点实时刷新右侧 label 统计列表。"""
        counter = Counter(marker.model.label for marker in self.marker_items.values())
        keyword = self.label_search.text().strip().lower()
        self.label_list.blockSignals(True)
        self.label_list.clear()
        for label, count in sorted(counter.items()):
            if keyword and keyword not in label.lower():
                continue
            item = QListWidgetItem(f"{label} ({count})")
            item.setData(Qt.ItemDataRole.UserRole, label)
            self.label_list.addItem(item)
        self.label_list.blockSignals(False)
        self.sync_label_selection()

    def sync_label_selection(self) -> None:
        """将 active_label 同步到 label 列表选中项。"""
        self.label_list.blockSignals(True)
        self.label_list.clearSelection()
        if self.active_label:
            for i in range(self.label_list.count()):
                item = self.label_list.item(i)
                if item.data(Qt.ItemDataRole.UserRole) == self.active_label:
                    item.setSelected(True)
                    break
        self.label_list.blockSignals(False)

    def on_label_item_clicked(self, item: QListWidgetItem) -> None:
        """点击右侧 label 项时切换高亮状态。"""
        label = item.data(Qt.ItemDataRole.UserRole)
        self.active_label = None if self.active_label == label else label
        self.sync_label_selection()
        self.refresh_highlight()

    def on_marker_changed(self) -> None:
        """标记点数据变化时更新界面。"""
        self.refresh_property_panel()
        self.refresh_label_list()

    def selected_image_item(self) -> ImageItem | None:
        """返回当前选中的图像项。"""
        for item in self.scene.selectedItems():
            if isinstance(item, ImageItem):
                return item
            if isinstance(item, MarkerItem):
                parent = item.parentItem()
                if isinstance(parent, ImageItem):
                    return parent
        return None

    def selected_marker_item(self) -> MarkerItem | None:
        """返回当前选中的标记点项。"""
        for item in self.scene.selectedItems():
            if isinstance(item, MarkerItem):
                return item
        return None

    def refresh_property_panel(self) -> None:
        """根据当前选中对象刷新属性面板。"""
        marker = self.selected_marker_item()
        if marker is not None:
            self.prop_type.setText("标记点")
            self.prop_file.setText(marker.model.image_id)
            self.prop_pos.setText(f"({marker.model.local_x:.1f}, {marker.model.local_y:.1f})")
            self.prop_scale.setText("-")
            self.prop_rotation.setText("-")
            self.prop_label.setEnabled(True)
            self.prop_note.setEnabled(True)
            self.prop_label.setText(marker.model.label)
            self.prop_note.setText(marker.model.note or "")
            self.prop_locked.setText(str(marker.model.locked))
            return

        image = self.selected_image_item()
        if image is not None:
            self.prop_type.setText("子图像")
            self.prop_file.setText(image.model.file_path)
            self.prop_pos.setText(f"({image.model.pos_x:.1f}, {image.model.pos_y:.1f})")
            self.prop_scale.setText(f"{image.model.scale:.3f}")
            self.prop_rotation.setText(f"{image.model.rotation_deg:.1f}")
            self.prop_label.setEnabled(False)
            self.prop_note.setEnabled(False)
            self.prop_label.setText("")
            self.prop_note.setText("")
            self.prop_locked.setText(str(image.model.locked))
            return

        self.prop_type.setText("-")
        self.prop_file.setText("-")
        self.prop_pos.setText("-")
        self.prop_scale.setText("-")
        self.prop_rotation.setText("-")
        self.prop_label.setEnabled(False)
        self.prop_note.setEnabled(False)
        self.prop_label.setText("")
        self.prop_note.setText("")
        self.prop_locked.setText("-")

    def apply_marker_text_changes(self) -> None:
        """将属性面板中的 label/note 写回当前标记点。"""
        marker = self.selected_marker_item()
        if marker is None:
            return
        marker.model.label = self.prop_label.text().strip() or "NET"
        marker.model.note = self.prop_note.text().strip()
        self.refresh_label_list()
        self.refresh_highlight()

    def toggle_add_marker_mode(self, checked: bool) -> None:
        """切换添加标记点模式。"""
        self.scene.add_marker_mode = checked

    def delete_selected(self) -> None:
        """删除当前选中对象（图像或标记点）。"""
        for item in list(self.scene.selectedItems()):
            if isinstance(item, MarkerItem):
                self.marker_items.pop(item.model.id, None)
                self.scene.removeItem(item)
            elif isinstance(item, ImageItem):
                marker_ids = [m_id for m_id, marker in self.marker_items.items() if marker.model.image_id == item.model.id]
                for m_id in marker_ids:
                    marker = self.marker_items.pop(m_id)
                    self.scene.removeItem(marker)
                self.image_items.pop(item.model.id, None)
                self.scene.removeItem(item)
        self.refresh_label_list()
        self.refresh_highlight()
        self.refresh_property_panel()

    def toggle_lock_selected(self) -> None:
        """切换选中对象的锁定状态。"""
        marker = self.selected_marker_item()
        if marker:
            marker.apply_lock_state(not marker.model.locked)
            self.refresh_property_panel()
            return

        image = self.selected_image_item()
        if image:
            image.apply_lock_state(not image.model.locked)
            self.refresh_property_panel()

    def scale_selected_image(self, factor: float) -> None:
        """按比例缩放当前选中图像。"""
        image = self.selected_image_item()
        if image and not image.model.locked:
            image.setScale(max(0.05, image.scale() * factor))
            self.refresh_property_panel()

    def rotate_selected_image(self, delta_deg: float) -> None:
        """旋转当前选中图像。"""
        image = self.selected_image_item()
        if image and not image.model.locked:
            image.setRotation(image.rotation() + delta_deg)
            self.refresh_property_panel()

    def adjust_selected_image_z(self, delta: int) -> None:
        """上移/下移图像图层。"""
        image = self.selected_image_item()
        if image:
            image.setZValue(image.zValue() + delta)

    def bring_selected_to_top(self) -> None:
        """将当前图像置于最顶层。"""
        image = self.selected_image_item()
        if image:
            max_z = max((it.zValue() for it in self.image_items.values()), default=0)
            image.setZValue(max_z + 1)

    def send_selected_to_bottom(self) -> None:
        """将当前图像置于最底层。"""
        image = self.selected_image_item()
        if image:
            min_z = min((it.zValue() for it in self.image_items.values()), default=0)
            image.setZValue(min_z - 1)

    def fit_view(self) -> None:
        """将视图适配到当前场景内容。"""
        if not self.scene.items():
            return
        self.view.fitInView(self.scene.itemsBoundingRect(), Qt.AspectRatioMode.KeepAspectRatio)

    def _collect_models(self) -> tuple[list[SubImageModel], list[MarkerModel]]:
        """收集当前场景中的模型数据。"""
        images = [item.model for item in self.image_items.values()]
        markers = [item.model for item in self.marker_items.values()]
        return images, markers

    def save_project_as(self) -> None:
        """保存工程到 JSON 文件。"""
        path, _ = QFileDialog.getSaveFileName(self, "保存工程", "", "JSON (*.json)")
        if not path:
            return
        images, markers = self._collect_models()
        save_project(path, images, markers)
        self.current_project_path = path

    def open_project(self) -> None:
        """从 JSON 打开工程并恢复画布状态。"""
        path, _ = QFileDialog.getOpenFileName(self, "打开工程", "", "JSON (*.json)")
        if not path:
            return
        self.load_from_path(path)

    def load_from_path(self, path: str) -> None:
        """执行工程加载流程并处理缺失文件提示。"""
        images, markers, missing = load_project(path)
        self.scene.clear()
        self.image_items.clear()
        self.marker_items.clear()

        for image_model in images:
            pixmap = QPixmap(image_model.file_path)
            if pixmap.isNull():
                continue
            image_item = ImageItem(image_model, pixmap)
            self.scene.addItem(image_item)
            self.image_items[image_model.id] = image_item

        for marker_model in markers:
            image_item = self.image_items.get(marker_model.image_id)
            if image_item is None:
                continue
            marker = MarkerItem(
                model=marker_model,
                parent_image=image_item,
                on_clicked=self.on_marker_clicked,
                on_hover=self.on_marker_hover,
                on_changed=self.on_marker_changed,
            )
            self.marker_items[marker_model.id] = marker

        self.current_project_path = path
        self.refresh_label_list()
        self.refresh_highlight()
        self.fit_view()

        if missing:
            QMessageBox.warning(self, "缺失文件", "以下图片文件不存在：\n" + "\n".join(missing))


def run() -> int:
    """应用入口函数。"""
    app = QApplication.instance() or QApplication([])
    window = MainWindow()
    window.show()
    return app.exec()
