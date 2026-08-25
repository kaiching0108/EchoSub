# -*- coding: utf-8 -*-
"""
EchoSub 設定檔
"""
import os

# 模型所在目錄（SenseVoice int8 / tokens / silero_vad.onnx）
# models/ 目錄與程式同級；整個專案搬到任何位置都不用改設定。
_HERE = os.path.dirname(os.path.abspath(__file__))
MODEL_DIR = os.path.join(_HERE, "models")
if not os.path.exists(os.path.join(MODEL_DIR, "model.int8.onnx")):
    raise FileNotFoundError(
        "找不到 models/model.int8.onnx，請先下載模型到 models/ 目錄（見 README「取得模型」）"
    )
SENSEVOICE_MODEL = os.path.join(MODEL_DIR, "model.int8.onnx")
TOKENS = os.path.join(MODEL_DIR, "tokens.txt")

# Silero VAD 模型（sherpa-onnx 用，需另行下載，見 README / setup）
SILERO_VAD_MODEL = os.path.join(MODEL_DIR, "silero_vad.onnx")

# 本機暫存（工作目錄下，不用 /tmp）
TMP_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "tmp")
os.makedirs(TMP_DIR, exist_ok=True)

# 字幕自動匯出（雙語文字檔）目錄，專案下自動建立；每次執行一個時間戳檔
EXPORT_DIR = os.path.join(_HERE, "logs")

# 音訊設定
SAMPLE_RATE = 16000
CHANNELS = 1

# VAD 切句參數（Silero VAD / ONNX，能忽略背景音樂，比 WebRTC VAD 強）
# min_silence_ms：語音結束後要聽到幾 ms 靜音才切句。
#   太大 → 連續短句（句間停頓 < 此值）會被併成一個段落、一起翻譯一起顯示；
#   太小 → 會在句中換氣/停頓處誤切，把一句拆成好幾段。
#   因為 Silero 能區分「人聲」與「背景音樂」，一般設 300 左右即可乾淨切句。
VAD_MIN_SILENCE_MS = 300

# Silero VAD 細部參數
SILERO_THRESHOLD = 0.9     # 語音機率門檻（0~1）。
                          # 越高越嚴：越能忽略背景音樂（句尾不被 BGM 拖住），
                          #   但語音太輕/太遠時可能被判成靜音而誤切句。
                          # 越低越敏感：輕聲語音抓得更好，但 BGM 拖尾更長、
                          #   甚至可能把「語音+背景音樂」併成一段。
                          # 一般 0.7~0.85；YouTube 有 BGM 建議 0.8，若發現句子被切太碎就降到 0.6。
SILERO_MIN_SPEECH_MS = 250   # 最短語音段，短於此視為雜音/音樂 blip 直接丟棄
SILERO_PAD_MS = 100          # 句首句尾各多留 100ms，避免切到半個字
SILERO_MAX_SPEECH_S = 20     # 單段最長秒數，超過強制切（防背景音樂一直被當語音而卡住）

# WASAPI 環回擷取裝置名稱。
# 設為 None 會自動嘗試「預設播放裝置」的環回擷取；
# 若擷到的是麥克風或沒聲音，請用 list_devices() 列出的播放裝置名稱填這裡。
WASAPI_DEVICE = None

# ASR 設定
ASR_LANGUAGE = "auto"   # auto / zh / en / ja / ko / yue
ASR_USE_ITN = True      # 數字、日期等反正規化（123 -> 一百二十三）
ASR_NUM_THREADS = min(4, os.cpu_count() or 1)

# 翻譯設定
# 可選: "none" | "marian"
#  - none:   不翻譯，直接回傳原文
#  - marian: 三語統一用 Opus-MT（transformers MarianMTModel，en/ja/ko 同一套路子，品質穩定）
TRANSLATOR = "marian"

# 三語皆用 Opus-MT（Helsinki-NLP / shun89 出品，transformers 原生推理）
# 英文用官方小模型；日/韓用 shun89 微調版（其 CTranslate2 轉換版有問題，故用原生）
EN_REPO = "Helsinki-NLP/opus-mt-en-zh"
JA_REPO = "shun89/opus-mt-ja-zh"
KO_REPO = "shun89/opus-mt-ko-zh"

# 繁體中文轉換（OpenCC）
# Opus-MT 的目標語 zh 輸出是「簡體中文」，翻譯後用 OpenCC 轉成繁體。
#   s2twp = 簡體→台灣繁體（含詞彙轉換，如 软件→軟體、鼠标→滑鼠、内存→記憶體）
#   s2hk  = 簡體→香港繁體（若想要香港習慣請改成這個）
OPENCC_CONFIG = "s2twp"

# 浮動視窗
WINDOW_WIDTH = 860
WINDOW_HEIGHT = 210
WINDOW_OPACITY = 0.92
