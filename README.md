# AI 截面慣性矩全題型網頁版 v2.1

## 本次新增

- 一次上傳多張照片，題目文字與共用圖形可以分開拍。
- 同一張圖有多個題號時，可選擇要解的題目。
- 組合截面新增：三角形、梯形、任意多邊形、橢圓、圓形扇形。
- 支援孔洞負面積、T 型、U 型、工字型及多矩形梁。
- 支援曲線陰影直接積分，例如：
  - `y² = 1 - x`
  - `y² = (b²/a)x`
- 支援極座標扇形，例如半徑 `r0`、總角度 `alpha`。
- 計算原始 x/y 軸及形心 x′/y′ 軸：
  - 面積 A
  - 形心 xbar、ybar
  - Ix、Iy、Ixy
  - 極慣性矩 J
  - 轉動半徑 kx、ky
- 支援題目指定的水平軸與垂直軸。
- 顯示積分式、符號精確答案、數值答案與平行軸定理表格。
- AI 辨識模型可在網頁中用 JSON 人工修正後再計算。

## 更新你原本的 Streamlit 網站

1. 下載並解壓縮新版 ZIP。
2. 進入原本的 GitHub Repository。
3. 按 `Add file → Upload files`。
4. 上傳並覆蓋：
   - `streamlit_app.py`
   - `ai_service.py`
   - `requirements.txt`
   - `.streamlit/config.toml`
5. 新增：
   - `geometry_engine.py`
   - `symbolic_engine.py`
6. 按 `Commit changes`。
7. Streamlit Community Cloud 會自動重新部署，原本分享網址不變。

舊的 `section_engine.py` 可以保留，也可以刪除；新版不再使用它。

## Streamlit Secrets

```toml
GEMINI_API_KEY = "你的新 Gemini API Key"
GEMINI_MODEL = "gemini-3.5-flash"
MAX_ANALYSES_PER_SESSION = 5
ALLOW_USER_API_KEY = false
```

真正的 API Key 不可上傳到 GitHub。

## 注意

AI 只負責辨識題目、尺寸、邊界與建立數學模型。
最後的積分、形心、平行軸定理與慣性矩，會由本地 SymPy 與幾何公式引擎重新計算。


## v2.1：10-21／10-22 驗證與修正

原 AI 解析曾將底板誤判為 275×25，並遺漏中央向下的 25×100 立板，
因此得到錯誤的：

- A = 11875 mm²
- ȳ ≈ 38.816 mm

正確幾何為四個不重疊矩形：

1. 底板 325×25，形心 (0, 12.5)
2. 左上立板 25×100，形心 (-100, 75)
3. 右上立板 25×100，形心 (100, 75)
4. 中央下立板 25×100，形心 (0, -50)

水平尺寸鏈：

```text
50 + 25 + 75 + 25 + 75 + 25 + 50 = 325 mm
```

本地公式結果：

- A = 15625 mm²
- x̄ = 0
- ȳ = 22.5 mm
- Ix′ = 34.407552×10^6 mm⁴ ≈ 34.4×10^6 mm⁴
- Iy（題圖 y 軸）= 121.907552×10^6 mm⁴ ≈ 122×10^6 mm⁴

與課本答案一致。

v2.1 另新增：

- 第二次 AI 幾何審查
- 板件清單、尺寸鏈總和、對稱與重疊稽核
- 503／429 自動重試
- 自動切換備用 Gemini 模型
- 10-21／10-22 確定幾何的本地修正與課本答案比對
