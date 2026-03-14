from __future__ import annotations

import json
from pathlib import Path

from .models import MarkerModel, SubImageModel


def save_project(project_path: str, images: list[SubImageModel], markers: list[MarkerModel]) -> None:
    """将工程数据保存为 JSON 文件。"""
    path = Path(project_path)
    base_dir = path.parent
    images_data = []
    for image in images:
        entry = image.to_dict()
        try:
            entry["file_path"] = str(Path(image.file_path).resolve().relative_to(base_dir.resolve()))
        except ValueError:
            entry["file_path"] = image.file_path
        images_data.append(entry)

    payload = {
        "version": 1,
        "images": images_data,
        "markers": [marker.to_dict() for marker in markers],
    }
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")


def load_project(project_path: str) -> tuple[list[SubImageModel], list[MarkerModel], list[str]]:
    """从 JSON 文件加载工程，并返回缺失图片提示。"""
    path = Path(project_path)
    base_dir = path.parent
    payload = json.loads(path.read_text(encoding="utf-8"))

    images: list[SubImageModel] = []
    missing_files: list[str] = []
    for image_data in payload.get("images", []):
        file_path = Path(image_data["file_path"])
        if not file_path.is_absolute():
            file_path = (base_dir / file_path).resolve()
        image_data["file_path"] = str(file_path)
        if not file_path.exists():
            missing_files.append(str(file_path))
        images.append(SubImageModel.from_dict(image_data))

    markers = [MarkerModel.from_dict(data) for data in payload.get("markers", [])]
    return images, markers, missing_files
