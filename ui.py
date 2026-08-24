# -*- coding: utf-8 -*-
"""
浮動字幕視窗（tkinter）。半透明、置頂、可拖動，顯示「原文 / 中文翻譯」滾動字幕。
頂部有明顯的標題列（可拖動視窗、含 ✕ 關閉鈕），避免無邊框視窗難以操作。
"""
import tkinter as tk
import config


class SubtitleWindow:
    def __init__(self):
        self.root = tk.Tk()
        self.root.title("EchoSub — 即時語音翻譯")
        # 明確擺放位置（避免貼死在左上角 0,0）
        self.root.geometry(f"{config.WINDOW_WIDTH}x{config.WINDOW_HEIGHT}+140+120")
        self.root.attributes("-topmost", True)
        self.root.attributes("-alpha", config.WINDOW_OPACITY)
        self.root.configure(bg="#1e1e1e")
        self.root.overrideredirect(True)   # 無邊框浮動外觀

        # ---- 頂部標題列（拖動 + 關閉）----
        title = tk.Frame(self.root, bg="#3a3a3a", height=30)
        title.pack(side="top", fill="x")
        title.pack_propagate(False)
        tk.Label(title, text="EchoSub — 即時語音翻譯", bg="#3a3a3a", fg="#eeeeee",
                 font=("Microsoft JhengHei", 10, "bold")).pack(side="left", padx=12)
        close_btn = tk.Label(title, text="✕", bg="#3a3a3a", fg="#ff7777",
                             font=("Microsoft JhengHei", 13, "bold"), cursor="hand2")
        close_btn.pack(side="right", padx=12)
        close_btn.bind("<Button-1>", self._on_close)
        # 拖動：標題列任意處（關閉鈕已自行處理並停止傳播）
        title.bind("<Button-1>", self._start_move)
        title.bind("<B1-Motion>", self._do_move)
        self._drag = None

        # ---- 底部狀態列 + 縮放把手 ----
        bar = tk.Frame(self.root, bg="#111111")
        self.status = tk.Label(bar, text="● 準備中…", bg="#111111",
                               fg="#88ff88", font=("Microsoft JhengHei", 9))
        self.status.pack(side="left", padx=8)
        # 縮放把手：固定大小的可視方塊 + 畫布畫兩條對角線（不依賴字型符號）
        grip = tk.Frame(bar, bg="#2a2a2a", cursor="size_nw_se",
                        width=26, height=24)
        grip.pack(side="right", padx=2, pady=2)
        grip.pack_propagate(False)
        cv = tk.Canvas(grip, bg="#2a2a2a", highlightthickness=0,
                       width=22, height=20, cursor="size_nw_se")
        cv.pack(expand=True, fill="both")
        cv.create_line(3, 17, 17, 3, fill="#999999", width=2)
        cv.create_line(9, 17, 17, 9, fill="#999999", width=2)
        for w in (grip, cv):
            w.bind("<Button-1>", self._start_resize)
            w.bind("<B1-Motion>", self._do_resize)
        bar.pack(side="bottom", fill="x")

        # ---- 字幕區（必須在狀態列之後 pack，才不會被 expand 吃掉底部空間）----
        self.text = tk.Text(
            self.root, bg="#1e1e1e", fg="#dddddd",
            font=("Microsoft JhengHei", 12), wrap="word",
            state="disabled", padx=12, pady=10, cursor="arrow",
        )
        self.text.pack(fill="both", expand=True)

        self._append("系統：視窗已啟動。開始播放影片/聲音後會自動轉錄。\n", "#88ff88")

    def _on_close(self, e):
        self.root.destroy()
        return "break"   # 阻止事件繼續傳給標題列（避免觸發拖動）

    def _start_move(self, e):
        self._drag = (e.x_root - self.root.winfo_x(), e.y_root - self.root.winfo_y())

    def _do_move(self, e):
        if self._drag:
            x = e.x_root - self._drag[0]
            y = e.y_root - self._drag[1]
            self.root.geometry(f"+{x}+{y}")

    def _start_resize(self, e):
        self._rz = (e.x_root, e.y_root,
                    self.root.winfo_width(), self.root.winfo_height())

    def _do_resize(self, e):
        if getattr(self, "_rz", None):
            sx, sy, w0, h0 = self._rz
            nw = max(320, w0 + (e.x_root - sx))
            nh = max(120, h0 + (e.y_root - sy))
            self.root.geometry(f"{nw}x{nh}")

    def set_status(self, text, color="#88ff88"):
        self.status.config(text=text, fg=color)

    def add_segment(self, src_text, translation, src_lang):
        src_label = {
            "en": "EN", "ja": "JA", "ko": "KO", "yue": "粵", "zh": "中",
        }.get(src_lang, "??")
        block = ""
        if src_lang not in ("zh", "yue"):
            block += f"[{src_label}] {src_text}\n"
        block += f"　{translation}\n\n"
        self._append(block, "#dddddd" if src_lang in ("zh", "yue") else "#ffffff")

    def _append(self, text, color):
        self.text.config(state="normal")
        self.text.insert("end", text, color)
        self.text.tag_config(color, foreground=color)
        self.text.see("end")
        # 限制行數，避免記憶體無限成長
        lines = int(self.text.index("end-1c").split(".")[0])
        if lines > 400:
            self.text.delete("1.0", f"{lines-300}.0")
        self.text.config(state="disabled")

    def run(self):
        self.root.mainloop()
