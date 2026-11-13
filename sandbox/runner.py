"""Sandbox runner: reads {"code", "topology", "params"} JSON on stdin, executes code, prints JSON result.

Runs inside a Docker container started with --network none, read-only rootfs, memory/CPU/pids
limits, a non-root user and no host mounts. The generated code receives:
  G         networkx.Graph (ROADM sites, edge attribute distance_km)
  topology  dict (sanitized synthetic topology)
  params    dict (task parameters)
and must assign a JSON-serialisable value to `result`.
"""
import contextlib, io, json, sys, traceback

MARK = "@@ONDM_RESULT@@"


def main():
    payload = json.loads(sys.stdin.read())
    import signal
    def _timeout(signum, frame):
        raise TimeoutError("sandbox time limit exceeded")
    signal.signal(signal.SIGALRM, _timeout)  # PID 1 ignores default SIGALRM, so install a handler
    signal.alarm(int(payload.get("timeout_s", 20)))
    import networkx as nx
    topo = payload["topology"]
    G = nx.Graph()
    for n in topo["nodes"]:
        G.add_node(n["id"], **{k: v for k, v in n.items() if k != "id"})
    for e in topo["edges"]:
        G.add_edge(e["source"], e["target"], distance_km=float(e["distance_km"]), weight=float(e["distance_km"]))
    env = {"__name__": "__ondm_generated__", "nx": nx, "networkx": nx, "G": G, "topology": topo,
           "params": payload.get("params", {}), "result": None}
    out = io.StringIO()
    status = {"ok": True}
    try:
        with contextlib.redirect_stdout(out):
            exec(compile(payload["code"], "<generated>", "exec"), env)
        result = env.get("result")
        json.dumps(result)  # must be serialisable
        status["result"] = result
    except Exception as exc:
        status = {"ok": False, "error_type": type(exc).__name__, "error": str(exc)[:2000],
                  "traceback": traceback.format_exc(limit=6)[-4000:]}
    status["stdout"] = out.getvalue()[-4000:]
    sys.stdout.write(MARK + json.dumps(status, default=str) + MARK)


if __name__ == "__main__":
    main()
