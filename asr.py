# -*- coding: utf-8 -*-
"""
語音轉文字：SenseVoice(int8) 做辨識 + Silero VAD(ONNX) 做切句。
- Silero VAD 把連續音訊切成「一句話」等級的語音段。它比 WebRTC VAD 強在
  能區分「人聲」與「背景音樂/雜音」，只對真正的人聲觸發，
  解決 YouTube 影片背景音樂讓 WebRTC 誤判「一直有聲音」而無法切句的問題。
- SenseVoice 把每一段語音轉成文字，並標出語言（auto 模式下從結果前綴解析）。
"""
import queue
import threading
import numpy as np
import onnxruntime as ort
import config


class SileroVADSegmenter:
    """用 Silero VAD (ONNX) 把 16k 單聲道 int16 音訊切成語音段。

    與 WebRTC VAD 最大的差別：Silero 是類神經網路 VAD，能忽略背景音樂，
    只對人聲觸發。對 YouTube / 演講 / 財報會議影片（多半有 BGM）尤其重要，
    否則 VAD 會把「音樂 + 人聲」整段當成連續語音，要等到 20s 強制切段才出字。
    """

    WINDOW = 512  # Silero 模型每次吃 512 個取樣 = 32ms @ 16k

    def __init__(self, sample_rate=16000, min_silence_ms=300, min_speech_ms=250,
                 max_speech_s=20, threshold=0.5, pad_ms=100, model_path=None):
        self.sr = sample_rate
        self.threshold = threshold
        # 以「window 數」表示各種長度（1 window = 32ms）
        self.min_silence = max(1, int(sample_rate * min_silence_ms // 1000 // self.WINDOW))
        self.min_speech = max(1, int(sample_rate * min_speech_ms // 1000 // self.WINDOW))
        self.pad = max(0, int(sample_rate * pad_ms // 1000 // self.WINDOW))
        self.max_speech = max(1, int(sample_rate * max_speech_s // self.WINDOW))
        self.model_path = model_path or config.SILERO_VAD_MODEL

        opts = ort.SessionOptions()
        opts.intra_op_num_threads = 1
        opts.inter_op_num_threads = 1
        self.sess = ort.InferenceSession(self.model_path, sess_options=opts,
                                         providers=["CPUExecutionProvider"])
        self.reset()

    def reset(self):
        # LSTM 狀態（在整個音訊流中連續傳遞，不隨句邊界重置）
        self._h = np.zeros((2, 1, 64), dtype=np.float32)
        self._c = np.zeros((2, 1, 64), dtype=np.float32)
        self._buf = []            # 待處理的 float 取樣（< WINDOW）
        self._win_idx = 0         # 下一個要處理的 window 的絕對索引
        self._ring = {}           # win_idx -> float[512]（用於回組 segment）
        self._ring_min = 0
        self._max_ring = 4096     # 最多保留的 window 數（~131s，足夠容納 max_speech）
        self._in_speech = False
        self._confirmed = False
        self._speech_run = 0
        self._silence_run = 0
        self._speech_start = None  # 語音開始的絕對 window 索引

    def feed(self, arr_int16, on_segment):
        arr_f = arr_int16.astype(np.float32) / 32768.0
        self._buf.extend(arr_f.tolist())
        while len(self._buf) >= self.WINDOW:
            window = np.array(self._buf[:self.WINDOW], dtype=np.float32)
            del self._buf[:self.WINDOW]
            self._process_window(window, on_segment)

    def _process_window(self, window, on_segment):
        wi = self._win_idx
        prob, h, c = self.sess.run(
            None,
            {"x": window.reshape(1, self.WINDOW).astype(np.float32),
             "h": self._h, "c": self._c})
        self._h, self._c = h, c
        p = float(prob[0, 0])
        self._ring[wi] = window

        if p >= self.threshold:
            if not self._in_speech:
                self._in_speech = True
                self._confirmed = False
                self._speech_start = wi
                self._speech_run = 1
                self._silence_run = 0
            else:
                self._speech_run += 1
                self._silence_run = 0
                if not self._confirmed and self._speech_run >= self.min_speech:
                    self._confirmed = True
        else:
            if self._in_speech:
                self._silence_run += 1
                if self._confirmed and self._silence_run >= self.min_silence:
                    # 語音結束：句尾多留 pad 個 window
                    end_win = wi - self._silence_run + 1 + self.pad
                    self._emit(self._speech_start, end_win, on_segment)
                    self._reset_speech()
                elif not self._confirmed:
                    # 太短，視為雜音/音樂 blip，丟棄
                    self._reset_speech()
            else:
                self._silence_run = 0

        # 超長語音強制切段（背景音樂一直被當語音時，避免卡住不出字）
        if self._confirmed and (wi - self._speech_start) >= self.max_speech:
            self._emit(self._speech_start, wi + 1, on_segment)
            self._reset_speech()

        self._win_idx += 1
        self._trim_ring()

    def _reset_speech(self):
        self._in_speech = False
        self._confirmed = False
        self._speech_run = 0
        self._silence_run = 0
        self._speech_start = None

    def _trim_ring(self):
        cutoff = self._win_idx - self._max_ring
        if cutoff > self._ring_min:
            for k in range(self._ring_min, cutoff):
                self._ring.pop(k, None)
            self._ring_min = cutoff

    def _emit(self, start_win, end_win, on_segment):
        samples = []
        for w in range(start_win, end_win):
            seg = self._ring.get(w)
            if seg is not None:
                samples.extend(seg.tolist())
        if samples:
            seg_f = np.clip(np.array(samples, dtype=np.float32), -1.0, 1.0)
            seg_int16 = (seg_f * 32768.0).astype(np.int16)
            on_segment(seg_int16)

    def flush(self, on_segment):
        # 殘餘不足一個 window 的取樣直接丟棄
        self._buf = []
        if self._confirmed:
            self._emit(self._speech_start, self._win_idx + 1, on_segment)
        self.reset()


class ASR:
    def __init__(self):
        import sherpa_onnx
        # ---- SenseVoice ----
        self.model = sherpa_onnx.OfflineRecognizer.from_sense_voice(
            model=config.SENSEVOICE_MODEL,
            tokens=config.TOKENS,
            language=config.ASR_LANGUAGE,
            use_itn=config.ASR_USE_ITN,
            num_threads=config.ASR_NUM_THREADS,
        )
        # ---- VAD ----
        self.vad = SileroVADSegmenter(
            sample_rate=config.SAMPLE_RATE,
            min_silence_ms=config.VAD_MIN_SILENCE_MS,
            min_speech_ms=config.SILERO_MIN_SPEECH_MS,
            max_speech_s=config.SILERO_MAX_SPEECH_S,
            threshold=config.SILERO_THRESHOLD,
            pad_ms=config.SILERO_PAD_MS,
        )
        # ---- 辨識/翻譯背景 worker ----
        # VAD 切出語音段後，把波形丟進佇列，由獨立 worker 做 SenseVoice + 翻譯，
        # 避免阻塞音訊消費迴圈：否則上一句在翻譯時，下一句的音訊無法送進 VAD，
        # 就會出現「講完一句卻遲遲不翻譯」的延遲。
        self._seg_q = queue.Queue(maxsize=50)
        self._on_seg = None
        self._worker = threading.Thread(target=self._worker_loop, daemon=True)
        self._worker.start()
        print("[asr] SenseVoice + Silero VAD 初始化完成")

    @staticmethod
    def _parse_lang_tag(tag):
        """從 SenseVoice 的 result.lang（如 '<|en|>'）解析語言碼。"""
        lang_map = {"zh": "zh", "en": "en", "ja": "ja", "ko": "ko", "yue": "yue"}
        import re
        m = re.search(r"<\|(\w+)\|>", tag or "")
        code = m.group(1) if m else None
        return lang_map.get(code, code)

    def feed(self, samples_int16, on_segment):
        """餵入 16k 單聲道 int16 音訊；切出語音段交給背景 worker 做辨識+翻譯。"""
        self._on_seg = on_segment
        if len(samples_int16) == 0:
            return
        self.vad.feed(samples_int16, self._enqueue)

    def _enqueue(self, seg):
        """VAD 切出語音段時呼叫：丟進佇列，由 worker 處理（不阻塞呼叫方）。"""
        try:
            self._seg_q.put_nowait(seg)
        except queue.Full:
            try:
                self._seg_q.get_nowait()      # 佇列滿就丟最舊的，避免卡死
                self._seg_q.put_nowait(seg)
            except Exception:
                pass

    def _worker_loop(self):
        while True:
            seg = self._seg_q.get()
            if seg is None:
                break
            try:
                text, lang = self._recognize(seg)
                if text and self._on_seg:
                    self._on_seg(text, lang)
            except Exception as e:
                print(f"[asr] 辨識/翻譯錯誤：{e}")

    def _recognize(self, wave_int16):
        wave_f = wave_int16.astype(np.float32) / 32768.0
        stream = self.model.create_stream()
        stream.accept_waveform(config.SAMPLE_RATE, wave_f)
        self.model.decode_stream(stream)
        text = stream.result.text.strip()
        lang = self._parse_lang_tag(getattr(stream.result, "lang", ""))
        return text, lang

    def flush(self, on_segment):
        self._on_seg = on_segment
        self.vad.flush(self._enqueue)
