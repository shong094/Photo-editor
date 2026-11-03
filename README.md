# 影像編輯軟體

Python 實作、前後端分離的影像編輯軟體。

- **後端**：FastAPI，負責所有影像運算（`backend/`）
- **前端**：Tkinter 桌面視窗，負責顯示與操作，透過 HTTP 呼叫後端（`frontend/`）

## 安裝與執行

```bash
python -m venv .venv
.venv\Scripts\python -m pip install -r requirements.txt
```

開兩個終端機，先啟動後端，再啟動前端：

```bash
.venv\Scripts\python run_backend.py
```

```bash
.venv\Scripts\python run_frontend.py
```

API 文件：後端啟動後開啟 http://127.0.0.1:8000/docs

## 使用方式

1. 「檔案 > 開啟」載入影像
2. 在影像上按住滑鼠左鍵拖曳框出範圍（右鍵或 Esc 取消選取）
3. 右側面板調整參數，按「套用」
4. Ctrl+Z / Ctrl+Y 復原、重做；Ctrl+S 另存新檔

### 邊緣偵測子（拉普拉斯）

套用後工作區會並排顯示三張圖：**原圖 | 拉普拉斯濾波 | 疊加結果**。

- 濾波後的圖顯示 `|∇²f|`；疊加結果為 `g = f - c·∇²f`（`c` 為「疊加強度」，核的中心為負）。
- 在比較畫面調整參數再按「套用」，會從原圖重新計算，不會疊加在上一次的結果上。
- 也可以在最左邊的原圖重新框選範圍。有框選時，濾波圖的範圍外為黑色。
- 按「返回單圖編輯」回到單張畫面，並以疊加結果繼續編輯；「另存新檔」儲存的是疊加結果。

## 專案結構

```
backend/
  app.py              建立 FastAPI app，自動載入所有功能
  api/
    routes.py         HTTP 路由（GET /api/filters、POST /api/filters/{name}）
    schemas.py        請求／回應格式
  core/
    base.py           ImageFilter 基底類別、ParamSpec 參數規格
    registry.py       功能註冊表（@register）
    roi.py            只在選取範圍內套用功能
    image_io.py       影像 <-> base64
  filters/
    median.py         中值濾波
    laplacian.py      邊緣偵測子（拉普拉斯銳利濾波）
frontend/
  api_client.py       呼叫後端的唯一入口
  document.py         目前影像 + 復原／重做堆疊
  ui/
    main_window.py    主視窗、選單、狀態列、背景執行請求
    workspace.py      工作區：單圖編輯／多圖並排比較
    canvas_view.py    影像顯示與滑鼠框選
    tool_panel.py     依後端參數規格自動產生控制項
tests/
```

## 新增功能

只要在 `backend/filters/` 新增一個檔案，**前端不用改**，重新啟動後端與前端後就會出現在面板上：

```python
# backend/filters/invert.py
import numpy as np
from ..core.base import ImageFilter, ParamSpec
from ..core.registry import register

@register
class Invert(ImageFilter):
    name = "invert"
    display_name = "負片"
    category = "色彩"
    params = []  # 例：ParamSpec(name="strength", label="強度", type="float", default=1.0, min=0, max=1, step=0.1)

    def process(self, image: np.ndarray) -> np.ndarray:
        out = image.copy()
        out[:, :, :3] = 255 - out[:, :, :3]
        return out
```

參數型別支援 `int`、`float`、`bool`、`choice`，後端會自動驗證範圍，ROI 處理也由框架處理。

如果功能要一併顯示中間結果，改為覆寫 `run()` 並回傳 `FilterOutput(結果, [("標籤", 中間結果)], "結果標籤")`，前端就會自動改成並排比較（範例見 `backend/filters/laplacian.py`）。

## 打包成執行檔

```bash
.venv\Scripts\python -m pip install pyinstaller
.venv\Scripts\python -m PyInstaller --noconfirm photo_editor.spec
```

產生 `dist\PhotoEditor.exe`（約 33 MB，單一檔案，不需安裝 Python）。

執行檔的進入點是 [launcher.py](launcher.py)：它在背景執行緒啟動後端（隨機的本機埠），再開啟前端視窗，前後端仍透過 HTTP 溝通。
排查啟動錯誤時，可設定 `PYI_CONSOLE=1` 再打包，會產生帶主控台視窗的版本以顯示錯誤訊息。

## 測試

```bash
.venv\Scripts\python -m pytest tests
```
