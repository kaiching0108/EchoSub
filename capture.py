# -*- coding: utf-8 -*-
"""
用 pyaudiowpatch（PyAudio 的 WASAPI 修正版）抓 Windows 系統音效（WASAPI loopback）。
抓到的是「正在播放的聲音」，不限來源（YouTube / 影片 / 任何 App）。
輸出：16k / 單聲道 / int16 的 np.ndarray，直接餵給 VAD + SenseVoice。
"""
import audioop
import threading
import queue
import numpy as np
import pyaudiowpatch as pyaudio
import config


class AudioCaptureThread(threading.Thread):
    """背景執行緒：持續把系統音效（16k 單聲道 int16）丟進 out_queue。"""

    def __init__(self, out_queue: queue.Queue, device=None, stop_event=None):
        super().__init__(daemon=True)
        self.out_queue = out_queue
        self.device_name = device
        self.stop_event = stop_event or threading.Event()
        self.p = pyaudio.PyAudio()
        self.stream = None
        self._ratecv_state = None
        self._stop = False

    # ---- 選擇 loopback 裝置 ----
    def _pick_loopback(self):
        wasapi = self.p.get_host_api_info_by_type(pyaudio.paWASAPI)
        if self.device_name:
            # 依名稱（模糊比對）找輸出裝置
            target = self.device_name.lower()
            for i in range(self.p.get_device_count()):
                d = self.p.get_device_info_by_index(i)
                if (d["hostApi"] == wasapi["index"]
                        and d["maxOutputChannels"] > 0
                        and target in d["name"].lower()):
                    idx = i
                    break
            else:
                idx = wasapi["defaultOutputDevice"]
        else:
            idx = wasapi["defaultOutputDevice"]
        return self.p.get_wasapi_loopback_analogue_by_index(idx)

    def run(self):
        try:
            lb = self._pick_loopback()
            rate = int(lb["defaultSampleRate"])
            ch = lb["maxInputChannels"]
            self.stream = self.p.open(
                format=pyaudio.paInt16, channels=ch, rate=rate,
                input=True, input_device_index=lb["index"],
                frames_per_buffer=4096,
            )
            self.stream.start_stream()
            print(f"[capture] 開始擷取系統音效：{lb['name']} ({rate}Hz, {ch}ch)")
            while not self._stop and not self.stop_event.is_set():
                data = self.stream.read(4096, exception_on_overflow=False)
                if not data:
                    continue
                # 重採樣到 16k
                if rate != config.SAMPLE_RATE:
                    data, self._ratecv_state = audioop.ratecv(
                        data, 2, ch, rate, config.SAMPLE_RATE, self._ratecv_state)
                # 轉單聲道
                if ch == 2:
                    data = audioop.tomono(data, 2, 1, 1)
                arr = np.frombuffer(data, dtype=np.int16)
                if arr.size:
                    self.out_queue.put(arr)
        except Exception as e:
            import traceback
            traceback.print_exc()
            print(f"[capture] 擷取失敗：{e}")
        finally:
            self._cleanup()

    def _cleanup(self):
        try:
            if self.stream:
                self.stream.stop_stream()
                self.stream.close()
        except Exception:
            pass
        try:
            self.p.terminate()
        except Exception:
            pass

    def stop(self):
        self._stop = True
        self.stop_event.set()


def list_output_devices():
    """列出可用的輸出（可環回）裝置，供設定 config.WASAPI_DEVICE 用。"""
    p = pyaudio.PyAudio()
    wasapi = p.get_host_api_info_by_type(pyaudio.paWASAPI)
    out = []
    for i in range(p.get_device_count()):
        d = p.get_device_info_by_index(i)
        if d["hostApi"] == wasapi["index"] and d["maxOutputChannels"] > 0:
            out.append(d["name"])
    p.terminate()
    return out


if __name__ == "__main__":
    print("可用輸出裝置（可環回）：")
    for n in list_output_devices():
        print(" -", n)
