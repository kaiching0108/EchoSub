# -*- coding: utf-8 -*-
"""
主程式：把「擷音 → VAD切句 → SenseVoice轉文字 → 翻譯 → 浮動字幕」串起來。
"""
import sys
import os
import queue
import threading

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.stderr.reconfigure(encoding="utf-8", errors="replace")

import numpy as np
import config
import capture
import asr
import translate
import ui


def main():
    stop_event = threading.Event()
    audio_queue: queue.Queue = queue.Queue(maxsize=2000)
    ui_queue: queue.Queue = queue.Queue()

    window = ui.SubtitleWindow()
    window.set_status("● 初始化模型中…", "#ffcc66")
    try:
        recognizer = asr.ASR()
        translator = translate.build_translator()
        # 預載英文翻譯模型（約 10~20s），避免第一句英文出現時才卡在載入
        window.set_status("● 預載英文翻譯模型…", "#ffcc66")
        try:
            translator.map["en"]._load()
        except Exception as e:
            print("英文模型預載失敗（首次翻譯時再載）：", e)
    except Exception as e:
        import traceback
        traceback.print_exc()
        window.set_status("✕ 初始化失敗，請看終端機", "#ff6666")
        window._append(f"初始化錯誤：{e}\n", "#ff6666")
        window.run()
        return

    def on_segment(src_text, src_lang):
        try:
            tr = translator.translate(src_text, src_lang)
        except Exception as e:
            tr = f"（翻譯失敗：{e}）"
        ui_queue.put((src_text, tr, src_lang))

    # 擷音執行緒
    cap = capture.AudioCaptureThread(audio_queue, device=config.WASAPI_DEVICE,
                                     stop_event=stop_event)
    cap.start()
    window.set_status("● 聆聽中…（任何 Windows 聲音都會被轉錄）", "#88ff88")

    # 處理執行緒：消費音訊 → ASR → 翻譯
    buf = []

    def process_loop():
        while not stop_event.is_set():
            try:
                arr = audio_queue.get(timeout=0.4)
            except queue.Empty:
                # 超過 0.4s 沒新音訊：把剩餘音訊送進去並強制切出段落，
                # 解決「講完一句且停頓，卻一直不翻譯」的延遲。
                if buf:
                    recognizer.feed(np.concatenate(buf), on_segment)
                    buf.clear()
                recognizer.flush(on_segment)
                continue
            buf.append(arr)
            if len(buf) >= 3:                       # 累積 ~0.25s 就送一次
                recognizer.feed(np.concatenate(buf), on_segment)
                buf.clear()
        recognizer.flush(on_segment)

    proc = threading.Thread(target=process_loop, daemon=True)
    proc.start()

    # 關閉：停止所有執行緒
    orig_destroy = window.root.destroy

    def on_close():
        stop_event.set()
        try:
            orig_destroy()
        except Exception:
            pass

    window.root.destroy = on_close

    # UI 輪詢 ui_queue
    def poll():
        try:
            while True:
                src, tr, lang = ui_queue.get_nowait()
                window.add_segment(src, tr, lang)
        except queue.Empty:
            pass
        if not stop_event.is_set():
            window.root.after(100, poll)

    window.root.after(100, poll)
    window.run()
    stop_event.set()
    cap.stop()
    cap.join(timeout=2)
    proc.join(timeout=2)


if __name__ == "__main__":
    main()
