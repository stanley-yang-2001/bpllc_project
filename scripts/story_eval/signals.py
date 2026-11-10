"""Offline, non-LLM signals for a story's grammar and naturalness (10 Nov 2026). No Groq calls.

Each signal is a small class with the same three members (name, higher_is_better, measure), so a new one is one new class and nothing else changes:
  - LanguageToolSignal: errors per 100 words from a LanguageTool server (docker image `erikvl87/languagetool`, set LANGUAGETOOL_URL).
  - PerplexitySignal: how surprised a local multilingual language model is by the text (needs `transformers` and `torch`, model from MODEL).
  - WorstSentenceSignal: the surprise of the single most surprising sentence (one broken sentence hurts a story more than the average shows).
A signal returns None when it cannot judge a language; the report leaves that cell empty instead of guessing."""
from __future__ import annotations

import json
import math
import os
import re
import urllib.parse
import urllib.request

LT_CODES = {"en": "en-US", "es": "es", "fr": "fr", "de": "de-DE", "it": "it", "pt": "pt-PT", "ja": "ja-JP", "zh": "zh-CN"}   # Korean has no LanguageTool rules
UNSPACED = {"ja", "zh"}
DEFAULT_LM = "Qwen/Qwen2.5-0.5B"


def count_words(text: str, language: str) -> int:
    if language in UNSPACED:
        return len(re.findall(r"[぀-ヿ㐀-鿿]", text)) or 1
    return len(re.findall(r"\w+", text)) or 1


def sentences(text: str):
    return [s.strip() for s in re.split(r"(?<=[.!?。！？])\s+|\n+", text) if len(s.strip()) > 3]


class LanguageToolSignal:
    name = "languagetool_per100"
    higher_is_better = False

    def __init__(self, url: str = None, post=None):
        self.url = (url or os.environ.get("LANGUAGETOOL_URL") or "http://localhost:8010").rstrip("/")
        self._post = post or self._http

    def _http(self, url: str, fields: dict) -> dict:
        req = urllib.request.Request(url, urllib.parse.urlencode(fields).encode(), {"Accept": "application/json"})
        with urllib.request.urlopen(req, timeout=60) as r:
            return json.load(r)

    def measure(self, text: str, language: str):
        code = LT_CODES.get(language)
        if not code:
            return None
        data = self._post(self.url + "/v2/check", {"text": text, "language": code})
        matches = [m for m in data.get("matches", []) if m.get("rule", {}).get("issueType") != "style"]
        return round(100 * len(matches) / count_words(text, language), 3)


class PerplexitySignal:
    name = "perplexity"
    higher_is_better = False

    def __init__(self, model: str = None, scorer=None):
        self.model = model or os.environ.get("MODEL") or DEFAULT_LM
        self._scorer = scorer          # a function text -> mean negative log-likelihood per token; tests pass a fake

    def _load(self):
        if self._scorer:
            return self._scorer
        try:
            import torch
            from transformers import AutoModelForCausalLM, AutoTokenizer
        except ImportError as e:
            raise RuntimeError("perplexity needs `pip install torch transformers`") from e
        tok = AutoTokenizer.from_pretrained(self.model)
        lm = AutoModelForCausalLM.from_pretrained(self.model).eval()

        def nll(text: str) -> float:
            ids = tok(text, return_tensors="pt", truncation=True, max_length=1024).input_ids
            if ids.shape[1] < 2:
                return math.nan
            with torch.no_grad():
                return float(lm(ids, labels=ids).loss)
        self._scorer = nll
        return nll

    def measure(self, text: str, language: str):
        value = self._load()(text)
        return None if value != value else round(math.exp(value), 3)


class WorstSentenceSignal(PerplexitySignal):
    name = "worst_sentence_perplexity"

    def measure(self, text: str, language: str):
        score = self._load()
        values = [score(s) for s in sentences(text)]
        values = [v for v in values if v == v]
        return round(math.exp(max(values)), 3) if values else None


def default_signals(names=None):
    """Signals by name; LanguageTool is always cheap to try, the model ones only when asked for (they load a model)."""
    every = {"languagetool": LanguageToolSignal, "perplexity": PerplexitySignal, "worst_sentence": WorstSentenceSignal}
    return [every[n]() for n in (names or ["languagetool"])]
