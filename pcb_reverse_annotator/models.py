from __future__ import annotations

from dataclasses import dataclass, asdict
from typing import Optional


@dataclass
class SubImageModel:
    """子图像模型：保存图像在画布中的状态。"""

    id: str
    file_path: str
    pos_x: float
    pos_y: float
    scale: float = 1.0
    rotation_deg: float = 0.0
    locked: bool = False
    z_index: int = 0
    width: int = 0
    height: int = 0

    def to_dict(self) -> dict:
        """导出为可序列化字典。"""
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> "SubImageModel":
        """从字典恢复子图像模型。"""
        return cls(**data)


@dataclass
class MarkerModel:
    """标记点模型：始终使用相对子图像的局部坐标。"""

    id: str
    image_id: str
    local_x: float
    local_y: float
    label: str
    locked: bool = False
    note: Optional[str] = None

    def to_dict(self) -> dict:
        """导出为可序列化字典。"""
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> "MarkerModel":
        """从字典恢复标记点模型。"""
        return cls(**data)
