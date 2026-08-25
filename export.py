# -*- coding: utf-8 -*-
"""
字幕匯出：把每段字幕（原文＋中文翻譯）即時附加寫入文字檔。
- 檔名：EchoSub_<YYYYMMDD>_<HHMMSS>.txt（每次執行一個新檔）
- 編碼：utf-8-sig（含 BOM，Windows 記事本開中文正常）
- 儲存：每段寫入後 flush，關閉視窗即收尾
"""
import os
import threading
from datetime import datetime


class TranscriptExporter:
    """每段字幕即時附加到一個 session 文字檔（雙語純文字）。"""
    _LABELS = {"en": "EN", "ja": "JA", "ko": "KO", "yue": "粵", "zh": "中"}

    def __init__(self, export_dir):
        os.makedirs(export_dir, exist_ok=True)
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        self._path = os.path.join(export_dir, f"EchoSub_{ts}.txt")
        self._f = open(self._path, "w", encoding="utf-8-sig")
        self._lock = threading.Lock()

    @property
    def path(self):
        return self._path

    def write_segment(self, src_text, translation, src_lang):
        """寫入一段字幕。翻譯失敗時 translation 可能是錯誤字串，仍照寫。"""
        if not src_text or not src_text.strip():
            return
        label = self._LABELS.get(src_lang, "??")
        # zh/yue 無獨立翻譯（translation 已是繁體原文）→ 單行，不重複
        # TRANSLATOR=none 時 en/ja/ko 的 translation == src_text → 單行避免重複
        if src_lang in ("zh", "yue"):
            line = f"[{label}] {translation}\n\n"
        elif translation == src_text:
            line = f"[{label}] {src_text}\n\n"
        else:
            line = f"[{label}] {src_text}\n　{translation}\n\n"
        with self._lock:
            self._f.write(line)
            self._f.flush()

    def close(self):
        """收尾關檔（冪等，重複呼叫安全）。"""
        f = getattr(self, "_f", None)
        if f and not f.closed:
            try:
                f.close()
            except Exception:
                pass
