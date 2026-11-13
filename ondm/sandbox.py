"""Isolated execution of VLM-generated Python/NetworkX code.

Isolation model (primary backend = Docker):
  * fresh container per run from the minimal ``ondm-sandbox`` image (python:3.12-slim + networkx)
  * ``--network none`` (no network), read-only root FS, tiny noexec tmpfs, no host volume mounts
  * non-root UID, ``--cap-drop ALL``, ``no-new-privileges``, memory/CPU/PID limits, wall-clock timeout
  * no environment variables forwarded -> no NetBox tokens or other host secrets are reachable
  * input = sanitized topology JSON + params on stdin; output = JSON on stdout
A static AST pre-check rejects obviously dangerous constructs before anything runs (defence in
depth only — the container is the security boundary).

If Docker is unavailable, code is generated and displayed but NOT executed (status
``NOT_EXECUTED``); the caller must fall back to trusted, pre-written graph tools.
"""
from __future__ import annotations

import ast
import json
import shutil
import subprocess
import time
import uuid
from dataclasses import dataclass, field

from .config import SETTINGS

MARK = "@@ONDM_RESULT@@"
ALLOWED_IMPORTS = {"networkx", "math", "itertools", "collections", "heapq", "json", "statistics",
                   "functools", "operator", "copy", "typing", "dataclasses"}
FORBIDDEN_NAMES = {"open", "exec", "eval", "compile", "__import__", "input", "breakpoint", "globals",
                   "locals", "vars", "getattr", "setattr", "delattr", "memoryview", "exit", "quit"}
FORBIDDEN_ATTR_PREFIX = "__"


@dataclass
class ExecutionResult:
    status: str                      # OK | RUNTIME_ERROR | VALIDATION_ERROR | TIMEOUT | NOT_EXECUTED | SANDBOX_ERROR
    result: object = None
    error: str | None = None
    traceback: str | None = None
    stdout: str = ""
    runtime_s: float = 0.0
    backend: str = "docker"
    isolation: dict = field(default_factory=dict)

    def as_dict(self) -> dict:
        return self.__dict__.copy()


def validate_code(code: str) -> list[str]:
    """Static policy check. Returns a list of violations (empty = accepted)."""
    problems: list[str] = []
    if len(code) > 20_000:
        problems.append("code longer than 20k characters")
    try:
        tree = ast.parse(code)
    except SyntaxError as exc:
        return [f"SyntaxError: {exc.msg} (line {exc.lineno})"]
    assigns_result = False
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name.split(".")[0] not in ALLOWED_IMPORTS:
                    problems.append(f"import of '{alias.name}' not allowed")
        elif isinstance(node, ast.ImportFrom):
            if (node.module or "").split(".")[0] not in ALLOWED_IMPORTS:
                problems.append(f"import from '{node.module}' not allowed")
        elif isinstance(node, ast.Name) and node.id in FORBIDDEN_NAMES:
            problems.append(f"use of '{node.id}' not allowed")
        elif isinstance(node, ast.Attribute) and node.attr.startswith(FORBIDDEN_ATTR_PREFIX):
            problems.append(f"dunder attribute access '.{node.attr}' not allowed")
        elif isinstance(node, (ast.Assign, ast.AnnAssign, ast.AugAssign)):
            targets = node.targets if isinstance(node, ast.Assign) else [node.target]
            for t in targets:
                if isinstance(t, ast.Name) and t.id == "result":
                    assigns_result = True
    if not assigns_result:
        problems.append("code must assign its output to a variable named `result`")
    return problems


def docker_available() -> bool:
    if not shutil.which("docker"):
        return False
    try:
        proc = subprocess.run(["docker", "image", "inspect", SETTINGS.sandbox_image], capture_output=True,
                              timeout=15)
        return proc.returncode == 0
    except Exception:
        return False


def _docker_cmd(name: str) -> list[str]:
    return [
        "docker", "run", "--rm", "-i", "--name", name,
        "--network", "none",
        "--read-only", "--tmpfs", "/tmp:rw,noexec,nosuid,size=16m",
        "--memory", SETTINGS.sandbox_memory, "--memory-swap", SETTINGS.sandbox_memory,
        "--cpus", SETTINGS.sandbox_cpus, "--pids-limit", "64",
        "--cap-drop", "ALL", "--security-opt", "no-new-privileges",
        "--user", "10001:10001",
        SETTINGS.sandbox_image,
    ]


def isolation_profile() -> dict:
    return {"backend": "docker", "image": SETTINGS.sandbox_image, "network": "none", "rootfs": "read-only",
            "memory": SETTINGS.sandbox_memory, "cpus": SETTINGS.sandbox_cpus, "pids_limit": 64,
            "user": "uid 10001 (non-root)", "capabilities": "all dropped", "host_mounts": "none",
            "env_forwarded": "none", "timeout_s": SETTINGS.sandbox_timeout_s}


def run_code(code: str, topology: dict, params: dict | None = None) -> ExecutionResult:
    problems = validate_code(code)
    if problems:
        return ExecutionResult(status="VALIDATION_ERROR", error="; ".join(problems), backend="static-check")
    if not docker_available():
        return ExecutionResult(status="NOT_EXECUTED", backend="none",
                               error="Docker sandbox unavailable: generated code was NOT executed. "
                                     "Use trusted graph tools instead.")
    name = f"ondm-sbx-{uuid.uuid4().hex[:10]}"
    payload = json.dumps({"code": code, "topology": topology, "params": params or {},
                          "timeout_s": SETTINGS.sandbox_timeout_s})
    t0 = time.perf_counter()
    try:
        proc = subprocess.run(_docker_cmd(name), input=payload, capture_output=True, text=True,
                              timeout=SETTINGS.sandbox_timeout_s + 10)
    except subprocess.TimeoutExpired:
        subprocess.run(["docker", "kill", name], capture_output=True)
        return ExecutionResult(status="TIMEOUT", error=f"execution exceeded {SETTINGS.sandbox_timeout_s}s",
                               runtime_s=round(time.perf_counter() - t0, 2), isolation=isolation_profile())
    runtime = round(time.perf_counter() - t0, 2)
    out = proc.stdout or ""
    if MARK not in out:
        err = (proc.stderr or "").strip()[-2000:]
        if proc.returncode == 137:
            err = "container killed (memory limit exceeded?) " + err
        return ExecutionResult(status="SANDBOX_ERROR", error=err or f"no result (exit {proc.returncode})",
                               runtime_s=runtime, isolation=isolation_profile())
    body = out.split(MARK)[1]
    data = json.loads(body)
    if data.get("ok"):
        return ExecutionResult(status="OK", result=data.get("result"), stdout=data.get("stdout", ""),
                               runtime_s=runtime, isolation=isolation_profile())
    return ExecutionResult(status="RUNTIME_ERROR", error=f"{data.get('error_type')}: {data.get('error')}",
                           traceback=data.get("traceback"), stdout=data.get("stdout", ""), runtime_s=runtime,
                           isolation=isolation_profile())
