"""目前編輯中的影像，以及復原／重做紀錄。"""
from __future__ import annotations

from pathlib import Path

from PIL import Image


class ImageDocument:
    def __init__(self, max_history: int = 30):
        self.image: Image.Image | None = None
        self.path: Path | None = None
        self.max_history = max_history
        self._undo: list[Image.Image] = []
        self._redo: list[Image.Image] = []

    def open(self, path: str | Path) -> None:
        img = Image.open(path)
        img.load()
        if img.mode not in ("RGB", "RGBA"):
            img = img.convert("RGBA" if "A" in img.getbands() else "RGB")
        self.image = img
        self.path = Path(path)
        self._undo.clear()
        self._redo.clear()

    def save(self, path: str | Path) -> None:
        if self.image is None:
            return
        img = self.image
        if Path(path).suffix.lower() in (".jpg", ".jpeg") and img.mode == "RGBA":
            img = img.convert("RGB")
        img.save(path)
        self.path = Path(path)

    def update(self, new_image: Image.Image) -> None:
        """套用新的處理結果，並把舊影像推入復原堆疊。"""
        if self.image is not None:
            self._undo.append(self.image)
            del self._undo[: -self.max_history]
        self._redo.clear()
        self.image = new_image

    def can_undo(self) -> bool:
        return bool(self._undo)

    def can_redo(self) -> bool:
        return bool(self._redo)

    def undo(self) -> None:
        if self._undo:
            self._redo.append(self.image)
            self.image = self._undo.pop()

    def redo(self) -> None:
        if self._redo:
            self._undo.append(self.image)
            self.image = self._redo.pop()
