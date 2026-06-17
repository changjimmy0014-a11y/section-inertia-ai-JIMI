# AI 拍照解析－截面慣性矩網頁公開版

這是可部署成公開網址的 Streamlit 網頁應用程式。

部署後，使用者只要開啟 `https://你的名稱.streamlit.app`，即可：

- 用手機拍照或上傳題目圖片
- 使用 Gemini 或 OpenAI / GPT 解析題目
- 自動建立組合截面
- 人工校正尺寸與位置
- 計算整體形心、Ix、Iy、kx、ky
- 查看平行軸定理完整步驟
- 下載 JSON 與 CSV

---

## 先在自己電腦測試

1. 安裝 Python 3。
2. 解壓縮本資料夾。
3. 複製 `.streamlit/secrets.toml.example`，改名為：
   `.streamlit/secrets.toml`
4. 將自己的 Gemini 或 OpenAI API Key 填入。
5. 雙擊 `本機啟動網頁版.bat`。
6. 瀏覽器會開啟 `http://localhost:8501`。

---

## 部署成公開連結：Streamlit Community Cloud

### 第一步：建立 GitHub 儲存庫

將下列檔案全部上傳到同一個 GitHub repository：

- `streamlit_app.py`
- `section_engine.py`
- `ai_service.py`
- `requirements.txt`
- `.streamlit/config.toml`
- `.gitignore`
- `README.md`

不要上傳真正的 `.streamlit/secrets.toml`。

### 第二步：部署

1. 登入 Streamlit Community Cloud。
2. 選擇 `Create app`。
3. 選擇剛才的 GitHub repository。
4. Main file path 填入：
   `streamlit_app.py`
5. 開啟 Advanced settings。
6. Python version 建議選 3.12。
7. 在 Secrets 貼入：

```toml
GEMINI_API_KEY = "你的 Gemini API Key"
MAX_ANALYSES_PER_SESSION = 5
ALLOW_USER_API_KEY = true
```

也可改用 OpenAI：

```toml
OPENAI_API_KEY = "你的 OpenAI API Key"
MAX_ANALYSES_PER_SESSION = 5
ALLOW_USER_API_KEY = true
```

8. 按下 Deploy。
9. 完成後會取得類似：
   `https://section-inertia-ai.streamlit.app`
   的網址，直接把該網址分享給其他人。

---

## API Key 安全

- Key 只能放在 Streamlit Secrets。
- 不要將 Key 寫入 Python 程式。
- 不要將 `.streamlit/secrets.toml` 上傳到 GitHub。
- 公開網站若使用你的伺服器端 Key，所有人的 API 費用都會計入你的帳號。
- 可設定 `APP_PASSWORD`，只讓班級或指定人員使用。
- `MAX_ANALYSES_PER_SESSION` 是基本使用次數限制，但不是完整的防濫用機制。

---

## 可選的密碼保護

在 Streamlit Secrets 加上：

```toml
APP_PASSWORD = "你的共用密碼"
```

網站開啟時便會要求輸入密碼。

---

## 支援截面

- 矩形
- 圓形
- I 型鋼
- T 型截面
- 中空矩形
- 中空圓管
- 多個實體及孔洞組合

AI 會優先將複雜圖形拆成不重疊的矩形與圓形，再由本地公式引擎計算。
