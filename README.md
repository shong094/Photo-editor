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

或用一個指令同時啟動前後端（每次都是最新程式碼，不會有前後端版本不一致的問題）：

```bash
.venv\Scripts\python launcher.py
```

改過後端程式碼後，記得重新啟動後端；後端還在跑舊版時，前端會跳出「後端版本較舊」的提示。

API 文件：後端啟動後開啟 http://127.0.0.1:8000/docs

## 使用方式

1. 「檔案 > 開啟」載入影像
2. 在影像上按住滑鼠左鍵拖曳框出範圍（右鍵或 Esc 取消選取）
3. 右側面板調整參數，按「套用」
4. 右上「↶ 復原」「↷ 重做」按鈕，或 Ctrl+Z / Ctrl+Y；Ctrl+S 另存新檔

### 筆刷與橡皮擦

在右上「工具」切換到「筆刷」（Ctrl+B）或「橡皮擦」（Ctrl+E），直接在影像上拖曳；切回框選為 Ctrl+M。

- 三種筆觸：**硬邊筆**（實心、邊緣清楚）、**柔邊筆**（邊緣淡出）、**噴槍**（隨機細點）
- 可調大小、不透明度；顏色可點色塊開啟調色盤，或點下方的預設色
- **橡皮擦**會把擦過的地方還原成「開檔時的原圖」，可搭配三種筆觸（例如柔邊擦除）
  - 注意：濾波效果也會被擦回原圖
- 有框選範圍時，筆刷與橡皮擦只會作用在範圍內（要改範圍請先切回「框選」）
- 每一筆都可以復原；拖曳時先顯示預覽線（橡皮擦為灰色），放開後由後端算出真正的筆觸

### 邊緣偵測子（拉普拉斯）

套用後工作區會並排顯示三張圖：**原圖 | 拉普拉斯濾波 | 疊加結果**。

- 濾波後的圖顯示 `|∇²f|`；疊加結果為 `g = f - c·∇²f`（`c` 為「疊加強度」，核的中心為負）。
- 在比較畫面調整參數再按「套用」，會從原圖重新計算，不會疊加在上一次的結果上。
- 也可以在最左邊的原圖重新框選範圍。有框選時，濾波圖的範圍外為黑色。
- 按「返回單圖編輯」回到單張畫面，並以疊加結果繼續編輯；「另存新檔」儲存的是疊加結果。

### 製作 GIF

按右側欄最下方「GIF 動畫」區塊的「製作 GIF...」（或 Ctrl+G）開啟獨立視窗，把多張圖片串成會動的 GIF：

1. 把圖片拖進虛線框，或點擊選檔（可一次選多張，依檔名排序加入）
   - PNG、JPEG、WebP、GIF（GIF 只取第一格）；單張最大 10MB；最多 50 張
2. 在下方清單用 ↑ ↓ 調整順序、✕ 移除，每一幀可以設定各自的顯示時間（毫秒）
   - 「所有幀的顯示時間」是新加入圖片的預設值；按「套用到所有幀」一次改全部
3. 右側設定**循環播放**（無限／指定次數）與**輸出寬度**（留空則與第一張相同，高度依第一張的比例）
   - 尺寸或比例不同的圖片會等比例縮放並置中，周圍留透明
4. 按「建立 GIF」，右側會播放成品預覽，再按「下載 GIF」儲存

加入圖片後右側就會先播放預覽；改了任何設定，需要重新按「建立 GIF」。

## 專案結構

```
backend/
  app.py              建立 FastAPI app，自動載入所有功能
  api/
    routes.py         功能路由（GET /api/filters、POST /api/filters/{name}）
    brush_routes.py   筆刷路由（GET /api/brushes、POST /api/brushes/{name}/stroke）
    gif_routes.py     GIF 路由（GET /api/gif/limits、POST /api/gif）
    schemas.py        請求／回應格式
  core/
    base.py           ImageFilter 基底類別、ParamSpec 參數規格
    brush.py          Brush 基底類別、筆畫取樣與顏色合成
    registry.py       通用註冊表（功能用 @register，筆刷用 @register_brush）
    roi.py            只在選取範圍內套用功能
    gif.py            多張圖片合成 GIF（尺寸統一、透明處理、循環次數、限制檢查）
    image_io.py       影像 <-> base64
  filters/
    median.py         中值濾波
    laplacian.py      邊緣偵測子（拉普拉斯銳利濾波）
  brushes/
    hard.py           硬邊筆
    soft.py           柔邊筆
    spray.py          噴槍
frontend/
  api_client.py       呼叫後端的唯一入口
  document.py         目前影像 + 復原／重做堆疊
  ui/
    main_window.py    主視窗、選單、狀態列、背景執行請求
    workspace.py      工作區：單圖編輯／多圖並排比較
    canvas_view.py    影像顯示、滑鼠框選、筆刷預覽
    brush_panel.py    工具切換與筆刷設定（筆觸、大小、不透明度、顏色）
    tool_panel.py     依後端參數規格自動產生控制項
    gif_maker.py      製作 GIF 視窗（拖放選檔、幀清單、預覽、下載）
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

## 新增筆刷

筆刷只決定「筆印的形狀」，顏色、不透明度、沿路徑取樣都由框架處理。在 `backend/brushes/` 新增一個檔案即可：

```python
# backend/brushes/square.py
import numpy as np
from ..core.brush import Brush, dab_radius, register_brush

@register_brush
class SquareBrush(Brush):
    name = "square"
    display_name = "方頭筆"
    spacing = 0.15  # 筆印間距（相對於筆刷直徑）

    def dab(self, size, rng):
        r = dab_radius(size)
        return np.ones((2 * r + 1, 2 * r + 1), np.float32)  # 每格覆蓋率 0~1
```

前端的筆刷選項是向後端讀取的，所以不用改前端。

## 打包成執行檔

```bash
.venv\Scripts\python -m pip install pyinstaller
.venv\Scripts\python -m PyInstaller --noconfirm photo_editor.spec
```

產生 `dist\PhotoEditor.exe`（約 34 MB，單一檔案，不需安裝 Python）。

執行檔的進入點是 [launcher.py](launcher.py)：它在背景執行緒啟動後端（隨機的本機埠），再開啟前端視窗，前後端仍透過 HTTP 溝通。
排查啟動錯誤時，可設定 `PYI_CONSOLE=1` 再打包，會產生帶主控台視窗的版本以顯示錯誤訊息。

## 測試

```bash
.venv\Scripts\python -m pytest tests
```
