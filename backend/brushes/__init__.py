"""自動載入本資料夾下所有筆刷模組。

新增筆刷只要在這裡放一個新的 .py 檔並使用 @register_brush，不需改其他地方。
"""
import importlib
import pkgutil


def load_all() -> None:
    for module in pkgutil.iter_modules(__path__):
        if not module.name.startswith("_"):
            importlib.import_module(f"{__name__}.{module.name}")
