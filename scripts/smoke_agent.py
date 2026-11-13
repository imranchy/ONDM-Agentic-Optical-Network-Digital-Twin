r"""End-to-end smoke run of the three business workflows + chat with the real VLM.

Writes a JSON summary to simulations/smoke/ (gitignored cache) for the handoff notes.
Usage: .venv\Scripts\python scripts\smoke_agent.py
"""
import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from ondm.agent import ONDMAgent, chat_turn  # noqa: E402
from ondm.vlm import get_vlm  # noqa: E402

CASES = [
    ("topo_0013", "provisioning", "Provision a 400G optical service between ROADM A and ROADM G. Inspect the available "
     "equipment, generate code to identify candidate routes, and determine their optical feasibility using GNPy.",
     {"source": "A", "target": "G"}),
    ("topo_0023", "failure_restoration", "Analyze the failure of fiber link H-J. Generate code to identify affected "
     "routes and calculate possible restoration paths.", {"failed_link": ["H", "J"]}),
    ("topo_0013", "troubleshooting", "Inspect the equipment and fiber connections associated with ROADM D. Identify "
     "potential connectivity or equipment constraints affecting service provisioning.", {"roadm": "D"}),
]


def main():
    out = []
    vlm = get_vlm()
    for sample, task, req, h in CASES:
        agent = ONDMAgent(vlm, on_step=lambda s: print(f"  [{s.actor}] {s.title} | {s.status} | {s.detail[:140]}",
                                                       flush=True))
        print(f"== {task} on {sample}")
        r = agent.run_workflow(sample, req, hints={"task": task, "strict": True, **h})
        out.append({"sample": sample, "task": task, "code_status": r.code_status, "origin": r.result_origin,
                    "attempts": len(r.code_attempts), "gnpy": [(g["sites"], g["requirement"]["line_rate_gbps"],
                                                                g["verdict"], g.get("remaining_margin_db_worst"))
                                                               for g in r.gnpy],
                    "total_s": r.total_s, "error": r.error, "answer": r.answer})
        print(f"   -> {r.code_status} / {r.result_origin} / {r.total_s}s")
    t0 = time.time()
    ans, steps, _ = chat_turn(vlm, "topo_0013", [], "Which links in this network are single points of failure? "
                              "Write code to check.", attach_image=True,
                              on_step=lambda s: print(f"  [chat {s.actor}] {s.title} | {s.status}", flush=True))
    out.append({"task": "chat", "tools": [s.title for s in steps if s.actor != "VLM"], "answer": ans,
                "total_s": round(time.time() - t0, 1)})
    p = ROOT / "simulations" / "smoke" / f"smoke_{time.strftime('%Y%m%d_%H%M%S')}.json"
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(out, indent=1), encoding="utf-8")
    print("saved", p)


if __name__ == "__main__":
    main()
