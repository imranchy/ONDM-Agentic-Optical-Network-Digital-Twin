"""Inventory access: live NetBox (read-only, via pynetbox) with an explicitly labelled local fallback.

Both backends return the same normalised structure so the agent/UI do not care which is used,
but every payload carries ``source`` so the UI can show whether data is LIVE NETBOX or the
LOCAL FALLBACK derived from the synthetic graph JSON.
"""
from __future__ import annotations

import math
from functools import lru_cache

from . import topology as topo
from .config import SETTINGS

MAX_DEGREES = 12
MAX_SPAN_KM = 80.0


def _val(x):
    """pynetbox returns choice fields either as objects with .value or as plain strings."""
    if x is None:
        return None
    return getattr(x, "value", x)


def _slug(text: str) -> str:
    return "".join(c if c.isalnum() else "-" for c in text.lower()).strip("-")


# --------------------------------------------------------------------------- NetBox backend
class NetBoxInventory:
    source = "LIVE NETBOX"

    def __init__(self, url: str | None = None, token: str | None = None):
        import pynetbox

        self.url = url or SETTINGS.netbox_url
        token = token or SETTINGS.netbox_token
        if not self.url or not token:
            raise RuntimeError("NETBOX_URL / NETBOX_TOKEN not configured")
        self.nb = pynetbox.api(self.url, token=token)
        self.nb.http_session.timeout = SETTINGS.netbox_timeout_s

    def status(self) -> dict:
        st = self.nb.status()
        return {"source": self.source, "url": self.url, "netbox_version": st.get("netbox-version"),
                "ondm_sites": self.nb.dcim.sites.count(tag="ondm-synthetic"),
                "ondm_devices": self.nb.dcim.devices.count(tag="ondm-synthetic"),
                "ondm_cables": self.nb.dcim.cables.count(tag="ondm-synthetic")}

    def has_topology(self, sample_id: str) -> bool:
        return self.nb.dcim.sites.count(group=_slug(sample_id)) > 0

    def topology_inventory(self, sample_id: str) -> dict:
        nb = self.nb
        sites = list(nb.dcim.sites.filter(group=_slug(sample_id)))
        site_ids = [s.id for s in sites]
        devices = list(nb.dcim.devices.filter(site_id=site_ids)) if site_ids else []
        dev_ids = [d.id for d in devices]
        ifaces = list(nb.dcim.interfaces.filter(device_id=dev_ids, limit=0)) if dev_ids else []
        cables = list(nb.dcim.cables.filter(device_id=dev_ids, limit=0)) if dev_ids else []
        prefix = f"{sample_id}-"
        out_devices = []
        for d in devices:
            out_devices.append({
                "name": d.name, "site": d.site.name, "node": d.site.name[len(prefix):],
                "role": d.role.name if getattr(d, "role", None) else None,
                "device_type": d.device_type.model, "status": _val(d.status),
                "tags": [t.slug for t in (d.tags or [])], "comments": d.comments or "", "netbox_id": d.id,
            })
        out_ifaces = []
        for i in ifaces:
            out_ifaces.append({"device": i.device.name, "name": i.name, "enabled": bool(i.enabled),
                               "cable_id": i.cable.id if i.cable else None, "description": i.description or "",
                               "tags": [t.slug for t in (i.tags or [])]})
        out_cables = []
        seen = set()
        for c in cables:
            if c.id in seen:
                continue
            seen.add(c.id)
            a = c.a_terminations[0] if c.a_terminations else None
            b = c.b_terminations[0] if c.b_terminations else None

            def _end(t):
                if t is None:
                    return None, None
                dev = getattr(t, "device", None)
                return (dev.name if dev else None), getattr(t, "name", None)

            a_dev, a_if = _end(a)
            b_dev, b_if = _end(b)
            out_cables.append({"id": c.id, "label": c.label, "status": _val(c.status),
                               "type": _val(c.type), "length": c.length,
                               "length_unit": _val(c.length_unit),
                               "a_device": a_dev, "a_interface": a_if, "b_device": b_dev, "b_interface": b_if,
                               "description": c.description or "", "tags": [t.slug for t in (c.tags or [])]})
        return {"source": self.source, "url": self.url, "sample_id": sample_id,
                "sites": [{"name": s.name, "status": _val(s.status)} for s in sites],
                "devices": out_devices, "interfaces": out_ifaces, "cables": out_cables}


# --------------------------------------------------------------------------- local fallback
class LocalInventory:
    """Inventory derived from the synthetic graph JSON (no NetBox). Explicitly labelled."""

    source = "LOCAL FALLBACK (synthetic graph JSON, not NetBox)"

    def status(self) -> dict:
        return {"source": self.source, "url": None, "netbox_version": None}

    def has_topology(self, sample_id: str) -> bool:
        return sample_id in topo.list_samples()

    def topology_inventory(self, sample_id: str) -> dict:
        data = topo.load_topology(sample_id)
        devices, ifaces, cables = [], [], []
        used = {}
        for n in data["nodes"]:
            nid = str(n["id"])
            used[nid] = 0
            devices.append({"name": f"{sample_id}-ROADM-{nid}", "site": f"{sample_id}-{nid}", "node": nid,
                            "role": "ROADM", "device_type": "SYN-ROADM-CDC-12D", "status": "active", "tags": [],
                            "comments": ""})
            for i in range(1, MAX_DEGREES + 1):
                ifaces.append({"device": f"{sample_id}-ROADM-{nid}", "name": f"DEG-{i}", "enabled": True,
                               "cable_id": None, "description": "", "tags": []})
            if n.get("attached_transceiver"):
                devices.append({"name": f"{sample_id}-TRX-{nid}", "site": f"{sample_id}-{nid}", "node": nid,
                                "role": "Optical Transponder", "device_type": "SYN-TRX-400G", "status": "active",
                                "tags": [], "comments": ""})
        cid = 0
        for e in sorted(data["edges"], key=lambda e: (str(e["source"]), str(e["target"]))):
            u, v, km = str(e["source"]), str(e["target"]), float(e["distance_km"])
            used[u] += 1
            used[v] += 1
            cid += 1
            spans = math.ceil(km / MAX_SPAN_KM)
            cables.append({"id": cid, "label": f"{sample_id} {u}-{v}", "status": "connected", "type": "smf",
                           "length": km, "length_unit": "km", "a_device": f"{sample_id}-ROADM-{u}",
                           "a_interface": f"DEG-{used[u]}", "b_device": f"{sample_id}-ROADM-{v}",
                           "b_interface": f"DEG-{used[v]}", "tags": [],
                           "description": f"{spans} span(s), {spans - 1} ILA(s) assumed"})
            for dev, port in ((f"{sample_id}-ROADM-{u}", f"DEG-{used[u]}"), (f"{sample_id}-ROADM-{v}", f"DEG-{used[v]}")):
                for i in ifaces:
                    if i["device"] == dev and i["name"] == port:
                        i["cable_id"] = cid
        return {"source": self.source, "url": None, "sample_id": sample_id,
                "sites": [{"name": f"{sample_id}-{n['id']}", "status": "active"} for n in data["nodes"]],
                "devices": devices, "interfaces": ifaces, "cables": cables}


# --------------------------------------------------------------------------- selection
def get_backend(prefer_live: bool = True):
    """Return (backend, note). Falls back to LocalInventory if NetBox is unreachable."""
    if prefer_live:
        try:
            nb = NetBoxInventory()
            nb.status()
            return nb, "connected"
        except Exception as exc:
            return LocalInventory(), f"NetBox unavailable ({type(exc).__name__}: {str(exc)[:120]}) - using local fallback"
    return LocalInventory(), "local fallback selected"


def inventory_for(sample_id: str, prefer_live: bool = True) -> dict:
    backend, note = get_backend(prefer_live)
    if isinstance(backend, NetBoxInventory) and not backend.has_topology(sample_id):
        backend, note = LocalInventory(), f"{sample_id} not present in NetBox - using local fallback"
    inv = backend.topology_inventory(sample_id)
    inv["backend_note"] = note
    return inv


# --------------------------------------------------------------------------- correlation / checks
def correlate(sample_id: str, inv: dict) -> dict:
    """Compare inventory records against the topology graph and list provisioning constraints."""
    g = topo.build_graph(sample_id)
    prefix = f"{sample_id}-ROADM-"
    roadm_names = {d["name"] for d in inv["devices"] if d["role"] == "ROADM"}
    trx = {d["node"]: d for d in inv["devices"] if d["role"] == "Optical Transponder"}
    iface_by = {(i["device"], i["name"]): i for i in inv["interfaces"]}
    findings = []
    matched_edges = set()
    for c in inv["cables"]:
        if not (c.get("a_device") or "").startswith(prefix) or not (c.get("b_device") or "").startswith(prefix):
            continue  # patch cables (transponder <-> ROADM)
        u, v = c["a_device"][len(prefix):], c["b_device"][len(prefix):]
        key = tuple(sorted((u, v)))
        if not g.has_edge(u, v):
            findings.append({"severity": "high", "type": "cable_not_in_topology", "object": c["label"],
                             "detail": f"NetBox cable {u}-{v} has no corresponding topology link"})
            continue
        matched_edges.add(key)
        km = g[u][v]["distance_km"]
        if c.get("length") is not None and c.get("length_unit") == "km" and abs(float(c["length"]) - km) > 0.5:
            findings.append({"severity": "medium", "type": "length_mismatch", "object": c["label"],
                             "detail": f"cable length {c['length']} km vs topology {km} km"})
        if c.get("status") != "connected":
            findings.append({"severity": "high", "type": "cable_not_in_service", "object": c["label"],
                             "link": [u, v], "detail": f"cable status '{c.get('status')}' (link unusable for service)"})
        for dev, port in ((c["a_device"], c["a_interface"]), (c["b_device"], c["b_interface"])):
            i = iface_by.get((dev, port))
            if i is not None and not i["enabled"]:
                findings.append({"severity": "high", "type": "port_disabled", "object": f"{dev} {port}",
                                 "link": [u, v], "detail": f"interface disabled: {i['description'] or 'no reason recorded'}"})
    for u, v in g.edges():
        if tuple(sorted((u, v))) not in matched_edges:
            findings.append({"severity": "high", "type": "link_missing_in_inventory", "object": f"{u}-{v}",
                             "link": [u, v], "detail": "topology link has no NetBox cable record"})
    for n in g.nodes():
        if f"{prefix}{n}" not in roadm_names:
            findings.append({"severity": "high", "type": "roadm_missing", "object": n,
                             "detail": "topology ROADM has no NetBox device"})
        t = trx.get(n)
        if t is None:
            findings.append({"severity": "info", "type": "no_transponder", "object": n,
                             "detail": "no transponder in inventory: site cannot terminate a new service without "
                                       "installing one (GNPy test transceivers are a simulation assumption)"})
        elif t["status"] != "active":
            findings.append({"severity": "high", "type": "transponder_not_active", "object": t["name"],
                             "detail": f"transponder status '{t['status']}' {t.get('comments', '')}"})
    unusable = [f["link"] for f in findings if f.get("link") and f["type"] in
                ("cable_not_in_service", "port_disabled", "link_missing_in_inventory")]
    return {"source": inv["source"], "findings": findings,
            "unusable_links": [list(x) for x in {tuple(sorted(l)) for l in unusable}],
            "transponder_sites": sorted(trx), "num_cables": len(inv["cables"])}


def roadm_view(sample_id: str, node: str, inv: dict) -> dict:
    dev = f"{sample_id}-ROADM-{node}"
    ifaces = [i for i in inv["interfaces"] if i["device"] == dev]
    cables = [c for c in inv["cables"] if dev in (c.get("a_device"), c.get("b_device"))]
    devices = [d for d in inv["devices"] if d["node"] == node]
    used = [i for i in ifaces if i["cable_id"] and i["name"].startswith("DEG")]
    return {"source": inv["source"], "roadm": dev, "devices_at_site": devices,
            "degree_ports_total": sum(1 for i in ifaces if i["name"].startswith("DEG")),
            "degree_ports_used": len(used),
            "disabled_interfaces": [i for i in ifaces if not i["enabled"]],
            "cables": cables}
