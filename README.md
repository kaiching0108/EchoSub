# EchoSub — 即時語音翻譯（Windows 系統音效 → 文字稿 + 繁中翻譯）

把電腦**正在播放的任何聲音**（YouTube 法說會、演講、影片…）即時轉成
文字稿，並翻譯成繁體中文，顯示在一個可拖動的浮動視窗裡。

全程**本機運算、CPU 跑**，不需要上傳任何音訊、也不連雲端。

## 專案結構

```
EchoSub/
├── main.py            # 入口：音訊捕捉執行緒 + 處理迴圈 + UI
├── capture.py         # WASAPI 環回擷取（也可單獨執行來列擷音裝置）
├── asr.py             # Silero VAD 切句 + SenseVoice 辨識（背景工作執行緒）
├── translate.py       # Opus-MT 三語翻譯 + OpenCC 簡轉繁
├── ui.py              # 可拖曳的浮動字幕視窗
├── config.py          # 所有設定（音訊、VAD、翻譯、視窗）
├── run.bat            # 雙擊啟動
├── requirements.txt   # 相依套件（版本鎖定，含純 CPU 版 torch）
└── models/
    ├── model.int8.onnx   # SenseVoice int8（~230MB，不入 git，見「取得模型」）
    ├── tokens.txt        # SenseVoice 詞表（~300KB，已在 repo）
    └── silero_vad.onnx   # Silero VAD（~600KB，不入 git，見「取得模型」）
```

## 安裝（新機器 / GitHub clone）

1. 安裝 **Python 3.10 或 3.11**（python.org），安裝時勾選「Add Python to PATH」。
2. 取得本專案（clone 或複製資料夾）。
3. 建虛擬環境並裝相依：
   ```bat
   cd <專案路徑>
   python -m venv .venv
   .venv\Scripts\activate
   pip install -r requirements.txt
   ```
   （torch 會從 PyTorch 官方 CPU 索引裝純 CPU 版，~200MB）
4. 準備 `models/` 裡的模型檔（見「取得模型」）。
5. 雙擊 `run.bat`。首次執行會自動從 HuggingFace 下載三語 Opus-MT 翻譯模型（需網路）。

## 運作方式

```
Windows 系統音效 (WASAPI loopback)
  → pyaudiowpatch 抓取 16k 單聲道
  → Silero VAD (ONNX) 切句（能忽略背景音樂，比 WebRTC VAD 強）
  → SenseVoice int8（語音轉文字，支援 zh/en/ja/ko/yue）
  → 翻譯成繁體中文（見下）
  → tkinter 浮動字幕視窗
```

### 翻譯後端（三語統一 Opus-MT）

來源語言由 SenseVoice 偵測，三語皆用 **Opus-MT**（經 transformers 原生推理，
MarianMTModel），目標語固定繁體中文：

> Opus-MT 的 `zh` 目標語其實輸出**簡體**中文，所以翻譯後會再用 **OpenCC**
> （`s2twp`，簡體→台灣繁體，含詞彙轉換如 软件→軟體、鼠标→滑鼠）轉成繁體；
> 中文/粵語來源原文也一併轉繁體，整個字幕視窗都是繁體中文。
> 想要香港繁體請改 `config.py` 的 `OPENCC_CONFIG = "s2hk"`。

| 來源語言 | 模型 | 說明 |
|----------|------|------|
| 英文 en  | `Helsinki-NLP/opus-mt-en-zh` | 官方小模型，商業/法說會文本自然準確 |
| 日文 ja  | `shun89/opus-mt-ja-zh` | 社群微調版，效果正確 |
| 韓文 ko  | `shun89/opus-mt-ko-zh` | 社群微調版，效果正確 |
| 中文/粵語 | 不翻譯 | 本身可讀，直接顯示原文 |

> 為什麼全用 Opus-MT？評測後發現：NLLB-200 雖然對少數慣用語（如 "Game of the Year"）
> 較強，但日文→中文會輸出亂碼、體積大（600M+）；而 Opus-MT 小巧（每顆約 300–600MB）、
> CPU 快、一般商業/演講文本翻譯自然準確，三語一致好維護。英文法說會這類內容用 Opus-MT
> 已完全夠用（註：`earnings call` 等特定領域詞彙 Opus-MT 可能字面化，必要時可再評估）。

## 執行

直接雙擊 `run.bat`（會用虛擬環境執行 `main.py`）。
或在專案目錄下手動：

```bat
.venv\Scripts\python.exe main.py
```

啟動後會出現半透明浮動視窗，開始播放影片/聲音就會自動轉錄與翻譯。
視窗底部有「✕ 關閉」按鈕；拖動底部黑條可移動視窗。

首次遇到日文/韓文時，會一次性載入對應模型（約數秒，之後很快）。

## 選擇擷音裝置（重要）

預設擷取「Windows 預設**輸出**裝置」的環回音（也就是你喇叭正在播的聲音）。
如果你的聲音從藍牙喇叭 / 特定裝置播出、卻抓不到，請：

1. 列出可用輸出裝置：
   ```bat
   .venv\Scripts\python.exe capture.py
   ```
2. 在 `config.py` 把 `WASAPI_DEVICE` 設成該裝置名稱（模糊比對即可），例如：
   ```python
   WASAPI_DEVICE = "Realtek"   # 用喇叭/內建輸出的關鍵字
   ```

> 提示：藍牙裝置的 WASAPI 環回有時無效，建議把「預設輸出裝置」設成
> 內建喇叭/HDMI 音訊，或直接指定 `WASAPI_DEVICE`。

## 開關翻譯 / 模式

`config.py` 中的 `TRANSLATOR`：
- `"marian"`（預設）：三語皆用 Opus-MT（transformers），英文/日文/韓文都翻。
- `"none"`：只顯示原文（SenseVoice 轉出的原始語言文字），不翻譯。

來源語言若已是中文/粵語，會直接顯示原文、不再翻譯。

## 相依套件（已在 `.venv` 安裝，版本見 `requirements.txt`）

- `sherpa-onnx`：SenseVoice 推理
- `pyaudiowpatch`：WASAPI 環回擷取
- `onnxruntime` + `silero_vad.onnx`：Silero VAD 切句（類神經網路 VAD，能忽略背景音樂，
  只對人聲觸發；這是 YouTube 影片有 BGM 時仍能正常切句的關鍵）
- `opencc`：簡體→繁體中文轉換（Opus-MT 輸出簡體，統一轉成繁體顯示）
- `transformers` + `torch`（CPU 版）：三語 Opus-MT 翻譯（MarianMTModel）
- `numpy`、`tkinter`（Python 內建）

## 取得模型

模型都放在專案目錄下的 `models/`（兩個 onnx 不入 git，clone 後需另行下載）：

| 檔案 | 大小 | 來源 |
|------|------|------|
| `model.int8.onnx`（+ repo 已含 `tokens.txt`） | ~230MB | SenseVoice int8，HuggingFace [`csukuangfj/sense-voice-onnx`](https://huggingface.co/csukuangfj/sense-voice-onnx) |
| `silero_vad.onnx` | ~600KB | Silero VAD（ONNX），HuggingFace [`snakers4/silero-vad`](https://huggingface.co/snakers4/silero-vad) |

三語 Opus-MT 翻譯模型（`Helsinki-NLP/opus-mt-en-zh`、`shun89/opus-mt-ja-zh`、
`shun89/opus-mt-ko-zh`）不用手動下載：首次使用時自動從 HuggingFace 快取到
`C:\Users\<你>\.cache\huggingface\hub\`（英文約 300MB、日/韓各約 600MB，只下一次）。

## 常見問題

- **抓不到聲音**：看上方「選擇擷音裝置」，把 `WASAPI_DEVICE` 指向實際輸出裝置。
- **翻譯很慢 / 沒反應**：首次遇到某語言會一次性載入該 Opus-MT 模型（英文約 10–20s、
  日/韓各約 5–6s，之後很快）。
- **控制台中文/emoji 變亂碼**：程式已把 stdout 設成 UTF-8；若仍有問題是 Windows
  cp950 主控台限制，不影響視窗內顯示。
- **影片有背景音樂，句子遲遲不出 / 被併成一長段**：這是 VAD 把 BGM 誤判成語音。
  Silero 比 WebRTC 抗音樂，但仍可微調 `config.py` 的 `SILERO_THRESHOLD`：
  
  - 調高（如 0.8→0.9）：更嚴，句尾背景音樂拖尾更短、更不會併段；
    但若語音很輕可能被判成靜音而誤切句。
  - 調低（如 0.8→0.6）：更敏，輕聲語音抓得更好；但 BGM 拖尾變長。
  - 一般 0.7~0.85；YouTube 有 BGM 建議 0.8。
  - 亦可調 `VAD_MIN_SILENCE_MS`（語音後要聽到幾 ms 靜音才切句，預設 300）。
