# PyInstaller 打包設定：pyinstaller photo_editor.spec
from PyInstaller.utils.hooks import collect_submodules
import os

# filters、brushes 是動態載入的，要明確告訴 PyInstaller 收進去
hiddenimports = collect_submodules("backend.filters") + collect_submodules("backend.brushes")

# 用不到的大型模組，排除以縮小檔案
excludes = [
    "pytest", "_pytest", "PyInstaller", "setuptools", "pip", "pkg_resources",
    "numpy.f2py", "numpy.distutils", "numpy.testing", "numpy.typing",
    "PIL.ImageQt", "PIL.ImageShow",
    "pydoc", "pydoc_data", "lib2to3", "doctest", "xmlrpc", "sqlite3",
    "curses", "idlelib", "tkinter.test", "test",
    "IPython", "matplotlib", "scipy", "pandas",
    "uvloop", "httptools", "websockets", "wsproto", "watchfiles", "dotenv", "yaml",
    "email_validator", "jinja2", "python_multipart",
]

a = Analysis(
    ["launcher.py"],
    hiddenimports=hiddenimports,
    excludes=excludes,
)
pyz = PYZ(a.pure)
exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    name="PhotoEditor",
    console=os.environ.get("PYI_CONSOLE") == "1",
    upx=False,
    strip=False,
)
