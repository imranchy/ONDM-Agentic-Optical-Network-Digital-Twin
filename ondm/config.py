"""Central configuration. Secrets are read from environment / .env only (never hard-coded)."""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

try:  # optional
    from dotenv import load_dotenv

    load_dotenv(Path(__file__).resolve().parent.parent / ".env")
except Exception:  # pragma: no cover
    pass

ROOT = Path(__file__).resolve().parent.parent


def _env(name: str, default: str | None = None) -> str | None:
    value = os.environ.get(name)
    return value if value not in (None, "") else default


@dataclass(frozen=True)
class Settings:
    data_dir: Path = Path(_env("ONDM_DATA_DIR", str(ROOT / "data" / "semantic_pilot")))
    cache_dir: Path = Path(_env("ONDM_CACHE_DIR", str(ROOT / "simulations" / "cache")))

    # VLM backend (Ollama by default; modular — see ondm/vlm.py)
    vlm_backend: str = _env("ONDM_VLM_BACKEND", "ollama")
    vlm_model: str = _env("ONDM_VLM_MODEL", "qwen3-vl:8b-instruct")
    ollama_host: str = _env("OLLAMA_HOST_URL", "http://localhost:11434")
    vlm_num_ctx: int = int(_env("ONDM_VLM_NUM_CTX", "16384"))
    vlm_timeout_s: int = int(_env("ONDM_VLM_TIMEOUT_S", "600"))
    vlm_image_max_px: int = int(_env("ONDM_VLM_IMAGE_MAX_PX", "896"))

    # NetBox (read-only token for the application; the write token is only used by the import script)
    netbox_url: str | None = _env("NETBOX_URL", "http://localhost:8000")
    netbox_token: str | None = _env("NETBOX_TOKEN")
    netbox_timeout_s: int = int(_env("NETBOX_TIMEOUT_S", "10"))

    # Code sandbox
    sandbox_image: str = _env("ONDM_SANDBOX_IMAGE", "ondm-sandbox:latest")
    sandbox_timeout_s: int = int(_env("ONDM_SANDBOX_TIMEOUT_S", "20"))
    sandbox_memory: str = _env("ONDM_SANDBOX_MEMORY", "256m")
    sandbox_cpus: str = _env("ONDM_SANDBOX_CPUS", "1.0")
    max_code_attempts: int = int(_env("ONDM_MAX_CODE_ATTEMPTS", "3"))

    # GNPy
    gnpy_max_span_km: float = float(_env("ONDM_GNPY_MAX_SPAN_KM", "80"))


SETTINGS = Settings()
