# -*- coding: utf-8 -*-
"""
翻譯模組（可抽換）。目標語言固定為繁體中文。
- none:   不翻譯，直接回傳原文
- marian: 三語統一用 Opus-MT（transformers MarianMTModel）
           英文  → Helsinki-NLP/opus-mt-en-zh
           日文  → shun89/opus-mt-ja-zh
           韓文  → shun89/opus-mt-ko-zh
           這三顆皆經 transformers 原生推理，品質穩定（CTranslate2 轉換版有問題故不用）。

來源語言由 ASR 偵測；中文/粵語本身可讀，直接回傳原文。
"""
import config


class Translator:
    """介面：translate(text, src_lang) -> str（中文）"""
    def translate(self, text, src_lang):
        raise NotImplementedError


class TraditionalConverter:
    """用 OpenCC 把簡體中文轉成繁體中文（台灣習慣，含詞彙轉換）。
    Opus-MT 目標語 zh 輸出是簡體，故翻譯後統一轉繁體；中文/粵語來源原文
    也一併轉繁體，讓整個字幕視窗都是繁體中文。
    對英文/日文/韓文不影響（OpenCC 只處理漢字，其他字元原樣通過）。"""
    _inst = None

    @classmethod
    def to_traditional(cls, text):
        if not text:
            return text
        try:
            if cls._inst is None:
                from opencc import OpenCC
                cls._inst = OpenCC(config.OPENCC_CONFIG)
            return cls._inst.convert(text)
        except Exception:
            return text


class NoTranslator(Translator):
    def translate(self, text, src_lang):
        # 不翻譯模式：中文/粵語來源仍轉成繁體顯示
        if src_lang in ("zh", "yue", None):
            return TraditionalConverter.to_traditional(text)
        return text


class MarianTranslator(Translator):
    """transformers 的 MarianMTModel（如 shun89/opus-mt-ja-zh），固定方向。
    模型以_repo 為鍵惰性載入並快取，避免同時佔用多份記憶體。
    """

    _cache = {}

    def __init__(self, repo):
        self.repo = repo

    def _load(self):
        if self.repo not in MarianTranslator._cache:
            from transformers import MarianMTModel, MarianTokenizer
            print(f"[translate] 載入 Marian 模型 {self.repo} ...", flush=True)
            tok = MarianTokenizer.from_pretrained(self.repo)
            mdl = MarianMTModel.from_pretrained(self.repo)
            MarianTranslator._cache[self.repo] = (tok, mdl)
        return MarianTranslator._cache[self.repo]

    def translate(self, text, src_lang=None):
        tok, mdl = self._load()
        out = mdl.generate(**tok(text, return_tensors="pt",
                                 truncation=True, max_length=512))
        return tok.decode(out[0], skip_special_tokens=True).strip()


class MultiTranslator(Translator):
    """依來源語言分流；三語皆用 Opus-MT（transformers MarianMTModel）。
    英文用小模型官方版，日/韓用 shun89 微調版。"""

    def __init__(self):
        self.map = {
            "en": MarianTranslator(config.EN_REPO),
            "ja": MarianTranslator(config.JA_REPO),
            "ko": MarianTranslator(config.KO_REPO),
        }

    def translate(self, text, src_lang):
        # 中文/粵語來源直接回原文（仍需轉繁體）；
        # 其他語言走 Opus-MT 翻成簡體中文後，再轉成繁體中文。
        if src_lang in ("zh", "yue", None):
            return TraditionalConverter.to_traditional(text)
        t = self.map.get(src_lang)
        if not t:
            return text
        return TraditionalConverter.to_traditional(t.translate(text, src_lang))


def build_translator():
    """依 config.TRANSLATOR 建立對應翻譯器。"""
    kind = (config.TRANSLATOR or "none").lower()
    if kind == "none":
        return NoTranslator()
    if kind == "marian":
        return MultiTranslator()
    raise ValueError(f"未知的 TRANSLATOR: {kind}")
