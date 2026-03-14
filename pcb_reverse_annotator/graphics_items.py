from __future__ import annotations

import uuid
from collections.abc import Callable

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QColor, QPainter, QPen, QPixmap
from PySide6.QtWidgets import (
    QGraphicsEllipseItem,
    QGraphicsItem,
    QGraphicsPixmapItem,
    QGraphicsSceneHoverEvent,
    QGraphicsSceneMouseEvent,
)

from .models import MarkerModel, SubImageModel


class ImageItem(QGraphicsPixmapItem):
    """可编辑子图像项，负责承载标记点子项。"""

    def __init__(self, model: SubImageModel, pixmap: QPixmap) -> None:
        """初始化图像项及其基础交互能力。"""
        super().__init__(pixmap)
        self.model = model
        self.setTransformationMode(Qt.TransformationMode.SmoothTransformation)
        self.setShapeMode(QGraphicsPixmapItem.ShapeMode.BoundingRectShape)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsMovable, True)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsSelectable, True)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemSendsGeometryChanges, True)
        self.setPos(model.pos_x, model.pos_y)
        self.setScale(model.scale)
        self.setRotation(model.rotation_deg)
        self.setZValue(model.z_index)
        self.apply_lock_state(model.locked)

    def apply_lock_state(self, locked: bool) -> None:
        """根据锁定状态启用/禁用可移动能力。"""
        self.model.locked = locked
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsMovable, not locked)

    def itemChange(self, change: QGraphicsItem.GraphicsItemChange, value):
        """同步图像几何变换到模型数据。"""
        if change == QGraphicsItem.GraphicsItemChange.ItemPositionHasChanged:
            pos = value
            self.model.pos_x = pos.x()
            self.model.pos_y = pos.y()
        elif change == QGraphicsItem.GraphicsItemChange.ItemScaleHasChanged:
            self.model.scale = float(value)
        elif change == QGraphicsItem.GraphicsItemChange.ItemRotationHasChanged:
            self.model.rotation_deg = float(value)
        elif change == QGraphicsItem.GraphicsItemChange.ItemZValueHasChanged:
            self.model.z_index = int(value)
        return super().itemChange(change, value)


class MarkerItem(QGraphicsEllipseItem):
    """标记点图元：作为 ImageItem 子项，使用局部坐标绑定。"""

    RADIUS = 5

    def __init__(
        self,
        model: MarkerModel,
        parent_image: ImageItem,
        on_clicked: Callable[["MarkerItem"], None],
        on_hover: Callable[[str | None], None],
        on_changed: Callable[[], None],
    ) -> None:
        """初始化标记点及交互回调。"""
        super().__init__(-self.RADIUS, -self.RADIUS, self.RADIUS * 2, self.RADIUS * 2, parent_image)
        self.model = model
        self.on_clicked = on_clicked
        self.on_hover = on_hover
        self.on_changed = on_changed

        self.setPos(QPointF(model.local_x, model.local_y))
        self.setPen(QPen(QColor("black"), 1.2))
        self.setBrush(QColor("orange"))
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsMovable, True)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsSelectable, True)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemSendsGeometryChanges, True)
        self.setAcceptHoverEvents(True)
        self.apply_lock_state(model.locked)

    def apply_lock_state(self, locked: bool) -> None:
        """根据锁定状态切换可编辑能力。"""
        self.model.locked = locked
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsMovable, not locked)

    def set_highlighted(self, highlighted: bool) -> None:
        """设置高亮视觉状态。"""
        self.setBrush(QColor("deepskyblue") if highlighted else QColor("orange"))

    def hoverEnterEvent(self, event: QGraphicsSceneHoverEvent) -> None:
        """鼠标进入时通知当前 hover label。"""
        self.on_hover(self.model.label)
        super().hoverEnterEvent(event)

    def hoverLeaveEvent(self, event: QGraphicsSceneHoverEvent) -> None:
        """鼠标离开时清除 hover label。"""
        self.on_hover(None)
        super().hoverLeaveEvent(event)

    def mousePressEvent(self, event: QGraphicsSceneMouseEvent) -> None:
        """点击标记点时切换 active label。"""
        if event.button() == Qt.MouseButton.LeftButton:
            self.on_clicked(self)
        super().mousePressEvent(event)

    def itemChange(self, change: QGraphicsItem.GraphicsItemChange, value):
        """限制标记点范围并同步局部坐标。"""
        if change == QGraphicsItem.GraphicsItemChange.ItemPositionChange:
            parent = self.parentItem()
            if isinstance(parent, ImageItem):
                pix_rect = QRectF(parent.pixmap().rect())
                new_pos = value
                new_x = min(max(new_pos.x(), 0.0), pix_rect.width())
                new_y = min(max(new_pos.y(), 0.0), pix_rect.height())
                return QPointF(new_x, new_y)
        if change == QGraphicsItem.GraphicsItemChange.ItemPositionHasChanged:
            pos = value
            self.model.local_x = pos.x()
            self.model.local_y = pos.y()
            self.on_changed()
        return super().itemChange(change, value)


def create_marker_model(image_id: str, local_pos: QPointF) -> MarkerModel:
    """创建默认标记点模型。"""
    return MarkerModel(
        id=str(uuid.uuid4()),
        image_id=image_id,
        local_x=local_pos.x(),
        local_y=local_pos.y(),
        label="NET",
        locked=False,
        note="",
    )


def marker_paint_hint(item: MarkerItem, painter: QPainter) -> None:
    """预留扩展绘制函数，当前由默认样式绘制。"""
    _ = item
    _ = painter
