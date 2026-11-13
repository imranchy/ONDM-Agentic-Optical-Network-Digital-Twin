"""Modular VLM interface.

``VLMBackend`` is the only thing the agent depends on, so additional backends (e.g. a fine-tuned
checkpoint served by vLLM / transformers, or other compact VLMs for the ONDM comparison) can be
added by implementing ``chat``. The default backend talks to a local Ollama server.
"""
from __future__ import annotations

import base64
import io
import json
import re
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Protocol

import requests

from .config import SETTINGS


@dataclass
class VLMResponse:
    content: str
    tool_calls: list[dict] = field(default_factory=list)
    thinking: str | None = None
    model: str = ""
    latency_s: float = 0.0
    prompt_tokens: int | None = None
    completion_tokens: int | None = None
    raw: dict | None = None


class VLMBackend(Protocol):
    name: str
    model: str

    def chat(self, messages: list[dict], *, tools: list[dict] | None = None, think: bool = False,
             temperature: float = 0.2, json_schema: dict | None = None, max_tokens: int | None = None) -> VLMResponse:
        ...

    def health(self) -> dict:
        ...


def encode_image(path: str | Path, max_px: int | None = None) -> str:
    """Base64 PNG, downscaled so the longest side <= max_px (keeps labels legible, cuts prefill time)."""
    max_px = max_px or SETTINGS.vlm_image_max_px
    from PIL import Image

    with Image.open(path) as img:
        img = img.convert("RGB")
        scale = max_px / max(img.size)
        if scale < 1:
            img = img.resize((int(img.width * scale), int(img.height * scale)), Image.LANCZOS)
        buf = io.BytesIO()
        img.save(buf, format="PNG")
    return base64.b64encode(buf.getvalue()).decode()


class OllamaVLM:
    name = "ollama"

    def __init__(self, model: str | None = None, host: str | None = None, num_ctx: int | None = None):
        self.model = model or SETTINGS.vlm_model
        self.host = (host or SETTINGS.ollama_host).rstrip("/")
        self.num_ctx = num_ctx or SETTINGS.vlm_num_ctx

    def health(self) -> dict:
        try:
            tags = requests.get(f"{self.host}/api/tags", timeout=5).json()
            names = [m["name"] for m in tags.get("models", [])]
            info = {}
            if self.model in names:
                show = requests.post(f"{self.host}/api/show", json={"model": self.model}, timeout=10).json()
                info = {"capabilities": show.get("capabilities"),
                        "parameter_size": show.get("details", {}).get("parameter_size"),
                        "quantization": show.get("details", {}).get("quantization_level"),
                        "family": show.get("details", {}).get("family")}
            return {"ok": self.model in names, "backend": self.name, "model": self.model, "host": self.host,
                    "installed_models": names, **info}
        except Exception as exc:
            return {"ok": False, "backend": self.name, "model": self.model, "host": self.host,
                    "error": f"{type(exc).__name__}: {exc}"}

    def chat(self, messages, *, tools=None, think=False, temperature=0.2, json_schema=None, max_tokens=None,
             seed=None):
        body: dict[str, Any] = {
            "model": self.model, "messages": messages, "stream": False, "think": bool(think),
            "keep_alive": "30m",
            "options": {"num_ctx": self.num_ctx, "temperature": temperature,
                        "num_predict": int(max_tokens or 2048),  # hard cap: prevents runaway generation
                        **({"seed": int(seed)} if seed is not None else {})},
        }
        if tools:
            body["tools"] = tools
        if json_schema:
            body["format"] = json_schema
        t0 = time.perf_counter()
        resp = requests.post(f"{self.host}/api/chat", json=body, timeout=SETTINGS.vlm_timeout_s)
        if resp.status_code != 200:
            raise RuntimeError(f"Ollama error {resp.status_code}: {resp.text[:300]}")
        data = resp.json()
        msg = data.get("message", {})
        return VLMResponse(content=msg.get("content", "") or "", tool_calls=msg.get("tool_calls") or [],
                           thinking=msg.get("thinking"), model=data.get("model", self.model),
                           latency_s=round(time.perf_counter() - t0, 2),
                           prompt_tokens=data.get("prompt_eval_count"), completion_tokens=data.get("eval_count"),
                           raw={k: v for k, v in data.items() if k != "message"})


BACKENDS = {"ollama": OllamaVLM}


def get_vlm(backend: str | None = None, model: str | None = None) -> VLMBackend:
    backend = backend or SETTINGS.vlm_backend
    if backend not in BACKENDS:
        raise ValueError(f"Unknown VLM backend {backend!r}; available: {sorted(BACKENDS)}")
    return BACKENDS[backend](model=model)


# --------------------------------------------------------------------------- helpers
def extract_code(text: str) -> str | None:
    blocks = re.findall(r"```(?:python|py)?\s*\n(.*?)```", text, flags=re.S)
    if blocks:
        return max(blocks, key=len).strip()
    m = re.search(r"```(?:python|py)\s*\n(.*)$", text, flags=re.S)  # unterminated (truncated) block
    if m:
        return m.group(1).strip()
    if "result" in text and ("import" in text or "G." in text):
        return text.strip()
    return None


def extract_json(text: str) -> Any:
    text = text.strip()
    try:
        return json.loads(text)
    except Exception:
        pass
    m = re.search(r"```(?:json)?\s*\n(.*?)```", text, flags=re.S)
    if m:
        try:
            return json.loads(m.group(1))
        except Exception:
            pass
    m = re.search(r"\{.*\}", text, flags=re.S)
    if m:
        return json.loads(m.group(0))
    raise ValueError("no JSON object found in model output")
