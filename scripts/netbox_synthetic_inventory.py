"""Reversible import of the SYNTHETIC ONDM topology inventory into a local NetBox.

Every object created is tagged ``ondm-synthetic`` and recorded in a manifest so it can be removed
exactly with ``rollback``. The script refuses to touch pre-existing objects with conflicting
names/slugs. Uses NETBOX_URL / NETBOX_WRITE_TOKEN from the environment or .env (never hard-coded).

Model (all synthetic, derived from data/semantic_pilot/graphs/*.json):
  Site group  "ONDM Synthetic"  ->  child site group per topology (e.g. topo_0003)
  Site        one per ROADM vertex  (e.g. topo_0003-A)
  Device      ROADM per site (type SYN-ROADM-CDC-12D: DEG-1..12 line ports, AD-1..4 add/drop ports)
  Device      400G transponder only where the dataset marks ``attached_transceiver: true``
  Cable       one SMF cable per topology edge between ROADM degree ports, length = distance_km
              (description records span/ILA counts under the 80 km max-span converter assumption)
  Cable       transponder LINE-1 <-> ROADM AD-1 patch
Optional ``--scenarios`` adds a few clearly tagged (``ondm-scenario``) synthetic operational
constraints for the troubleshooting demo (planned cable, disabled degree port, offline transponder).

Usage (Windows):
  .venv\\Scripts\\python scripts\\netbox_synthetic_inventory.py plan
  .venv\\Scripts\\python scripts\\netbox_synthetic_inventory.py import --scenarios
  .venv\\Scripts\\python scripts\\netbox_synthetic_inventory.py rollback
"""
from __future__ import annotations

import argparse
import json
import math
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from dotenv import load_dotenv  # noqa: E402

load_dotenv(ROOT / ".env")

import pynetbox  # noqa: E402

from ondm import topology as topo  # noqa: E402

MANIFEST = ROOT / "simulations" / "netbox" / "import_manifest.json"
TAG = {"name": "ondm-synthetic", "slug": "ondm-synthetic", "color": "9c27b0",
       "description": "Synthetic ONDM research inventory - NOT operator data"}
SCENARIO_TAG = {"name": "ondm-scenario", "slug": "ondm-scenario", "color": "ff9800",
                "description": "Synthetic operational constraint injected for the troubleshooting demo"}
MANUFACTURER = {"name": "ONDM Synthetic", "slug": "ondm-synthetic"}
ROLES = [{"name": "ROADM", "slug": "roadm", "color": "2196f3"},
         {"name": "Optical Transponder", "slug": "optical-transponder", "color": "4caf50"}]
ROADM_TYPE = {"model": "SYN-ROADM-CDC-12D", "slug": "syn-roadm-cdc-12d", "u_height": 0,
              "comments": "Synthetic 12-degree CDC ROADM (illustrative, not a vendor product)"}
TRX_TYPE = {"model": "SYN-TRX-400G", "slug": "syn-trx-400g", "u_height": 0,
            "comments": "Synthetic 400G coherent transponder (maps to GNPy example 'Voyager' mode 2)"}
MAX_DEGREES = 12
MAX_SPAN_KM = 80.0

# Synthetic scenarios (only with --scenarios). Picked from existing dataset edges/nodes.
SCENARIOS = {
    "topo_0013": {"planned_cable": None, "disabled_port_node": None, "offline_trx_node": None},
    "topo_0023": {"planned_cable": None, "disabled_port_node": None, "offline_trx_node": None},
    "topo_0003": {"planned_cable": None, "disabled_port_node": None, "offline_trx_node": None},
}


def api():
    url, token = os.environ.get("NETBOX_URL"), os.environ.get("NETBOX_WRITE_TOKEN")
    if not url or not token:
        sys.exit("NETBOX_URL and NETBOX_WRITE_TOKEN must be set (in .env). The read-only app token cannot import.")
    nb = pynetbox.api(url, token=token)
    nb.http_session.timeout = 30
    return nb


def slug(text: str) -> str:
    return "".join(c if c.isalnum() else "-" for c in text.lower()).strip("-")


def plan(samples: list[str]) -> dict:
    counts = {"topologies": len(samples), "sites": 0, "roadms": 0, "transponders": 0, "fiber_cables": 0,
              "patch_cables": 0}
    for s in samples:
        data = topo.load_topology(s)
        counts["sites"] += len(data["nodes"])
        counts["roadms"] += len(data["nodes"])
        trx = sum(1 for n in data["nodes"] if n.get("attached_transceiver"))
        counts["transponders"] += trx
        counts["patch_cables"] += trx
        counts["fiber_cables"] += len(data["edges"])
    return counts


def _scenario_choice(sample: str) -> dict:
    """Deterministically choose scenario targets from the real topology."""
    g = topo.build_graph(sample)
    edges = sorted(g.edges(data=True), key=lambda e: (-e[2]["distance_km"], e[0], e[1]))
    hub = max(sorted(g.nodes()), key=lambda n: g.degree(n))
    data = topo.load_topology(sample)
    trx_nodes = sorted(n["id"] for n in data["nodes"] if n.get("attached_transceiver"))
    return {"planned_cable": (edges[0][0], edges[0][1]), "disabled_port_node": hub,
            "offline_trx_node": trx_nodes[0] if trx_nodes else None}


class Importer:
    def __init__(self, nb):
        self.nb = nb
        self.created: list[dict] = []
        self.tag_ids: list[int] = []

    def _record(self, endpoint: str, obj):
        self.created.append({"endpoint": endpoint, "id": obj.id, "display": str(obj)})
        self._save()

    def _save(self):
        MANIFEST.parent.mkdir(parents=True, exist_ok=True)
        MANIFEST.write_text(json.dumps({"netbox_url": os.environ.get("NETBOX_URL"), "objects": self.created},
                                       indent=1), encoding="utf-8")

    def _create(self, endpoint: str, lookup: dict, payload: dict, reuse_if_tagged=True):
        app, model = endpoint.split(".")
        ep = getattr(getattr(self.nb, app), model)
        existing = ep.get(**lookup)
        if existing is not None:
            tags = {t.slug for t in (getattr(existing, "tags", None) or [])}
            if reuse_if_tagged and "ondm-synthetic" in tags:
                return existing
            raise SystemExit(f"Refusing to modify pre-existing NetBox object {endpoint} {lookup} (not ONDM-tagged)")
        obj = ep.create(payload)
        self._record(endpoint, obj)
        return obj

    def run(self, samples: list[str], scenarios: bool):
        nb = self.nb
        tag = nb.extras.tags.get(slug=TAG["slug"]) or nb.extras.tags.create(TAG)
        if not any(c["endpoint"] == "extras.tags" and c["id"] == tag.id for c in self.created):
            self._record("extras.tags", tag)
        tags = [tag.id]
        stag = None
        if scenarios:
            stag = nb.extras.tags.get(slug=SCENARIO_TAG["slug"]) or nb.extras.tags.create(SCENARIO_TAG)
            self._record("extras.tags", stag)
        mfr = self._create("dcim.manufacturers", {"slug": MANUFACTURER["slug"]}, {**MANUFACTURER, "tags": tags})
        roles = {r["slug"]: self._create("dcim.device_roles", {"slug": r["slug"]}, {**r, "tags": tags}) for r in ROLES}
        rtype = self._create("dcim.device_types", {"slug": ROADM_TYPE["slug"]},
                             {**ROADM_TYPE, "manufacturer": mfr.id, "tags": tags})
        ttype = self._create("dcim.device_types", {"slug": TRX_TYPE["slug"]},
                             {**TRX_TYPE, "manufacturer": mfr.id, "tags": tags})
        if not nb.dcim.interface_templates.filter(device_type_id=rtype.id):
            for i in range(1, MAX_DEGREES + 1):
                t = nb.dcim.interface_templates.create({"device_type": rtype.id, "name": f"DEG-{i}", "type": "other",
                                                        "description": "ROADM line degree (synthetic)"})
                self._record("dcim.interface_templates", t)
            for i in range(1, 5):
                t = nb.dcim.interface_templates.create({"device_type": rtype.id, "name": f"AD-{i}", "type": "other",
                                                        "description": "Add/drop port (synthetic)"})
                self._record("dcim.interface_templates", t)
        if not nb.dcim.interface_templates.filter(device_type_id=ttype.id):
            t = nb.dcim.interface_templates.create({"device_type": ttype.id, "name": "LINE-1",
                                                    "type": "400gbase-x-qsfpdd",
                                                    "description": "400G coherent line port (synthetic)"})
            self._record("dcim.interface_templates", t)
        root = self._create("dcim.site_groups", {"slug": "ondm-synthetic"},
                            {"name": "ONDM Synthetic", "slug": "ondm-synthetic", "tags": tags,
                             "description": "Synthetic topologies from data/semantic_pilot"})

        for sample in samples:
            data = topo.load_topology(sample)
            g = topo.build_graph(sample)
            sc = _scenario_choice(sample) if (scenarios and sample in SCENARIOS) else {}
            grp = self._create("dcim.site_groups", {"slug": slug(sample)},
                               {"name": sample, "slug": slug(sample), "parent": root.id, "tags": tags,
                                "description": f"{data.get('topology_type')} synthetic topology"})
            roadms, ports_used = {}, {}
            for node in data["nodes"]:
                nid = str(node["id"])
                site = self._create("dcim.sites", {"slug": slug(f"{sample}-{nid}")},
                                    {"name": f"{sample}-{nid}", "slug": slug(f"{sample}-{nid}"), "group": grp.id,
                                     "status": "active", "tags": tags,
                                     "description": f"Synthetic ROADM site {nid} of {sample}",
                                     "custom_fields": {}})
                dev = self._create("dcim.devices", {"name": f"{sample}-ROADM-{nid}"},
                                   {"name": f"{sample}-ROADM-{nid}", "device_type": rtype.id,
                                    "role": roles["roadm"].id, "site": site.id, "status": "active", "tags": tags,
                                    "comments": f"Topology vertex {nid}; degree {g.degree(nid)}"})
                roadms[nid] = dev
                ports_used[nid] = 0
                if node.get("attached_transceiver"):
                    status = "active"
                    dtags = list(tags)
                    if sc.get("offline_trx_node") == nid:
                        status, dtags = "offline", tags + [stag.id]
                    trx = self._create("dcim.devices", {"name": f"{sample}-TRX-{nid}"},
                                       {"name": f"{sample}-TRX-{nid}", "device_type": ttype.id,
                                        "role": roles["optical-transponder"].id, "site": site.id,
                                        "status": status, "tags": dtags,
                                        "comments": "Synthetic 400G transponder" +
                                                    (" - SCENARIO: offline for maintenance" if status == "offline" else "")})
                    a = nb.dcim.interfaces.get(device_id=trx.id, name="LINE-1")
                    b = nb.dcim.interfaces.get(device_id=dev.id, name="AD-1")
                    cab = nb.dcim.cables.create({"a_terminations": [{"object_type": "dcim.interface", "object_id": a.id}],
                                                 "b_terminations": [{"object_type": "dcim.interface", "object_id": b.id}],
                                                 "type": "smf", "status": "connected", "length": 5, "length_unit": "m",
                                                 "label": f"{sample} {nid} TRX-AD patch", "tags": tags})
                    self._record("dcim.cables", cab)
            for edge in sorted(data["edges"], key=lambda e: (str(e["source"]), str(e["target"]))):
                u, v, km = str(edge["source"]), str(edge["target"]), float(edge["distance_km"])
                ports = []
                for n in (u, v):
                    ports_used[n] += 1
                    if ports_used[n] > MAX_DEGREES:
                        raise SystemExit(f"{sample} {n}: more than {MAX_DEGREES} degrees")
                    ports.append(nb.dcim.interfaces.get(device_id=roadms[n].id, name=f"DEG-{ports_used[n]}"))
                spans = math.ceil(km / MAX_SPAN_KM)
                status, ctags = "connected", list(tags)
                if sc.get("planned_cable") in ((u, v), (v, u)):
                    status, ctags = "planned", tags + [stag.id]
                cab = nb.dcim.cables.create({
                    "a_terminations": [{"object_type": "dcim.interface", "object_id": ports[0].id}],
                    "b_terminations": [{"object_type": "dcim.interface", "object_id": ports[1].id}],
                    "type": "smf", "status": status, "length": km, "length_unit": "km",
                    "label": f"{sample} {u}-{v}", "tags": ctags,
                    "description": f"{spans} span(s), {spans - 1} ILA(s) assumed (max span {MAX_SPAN_KM:g} km)"
                                   + (" - SCENARIO: not yet in service" if status == "planned" else "")})
                self._record("dcim.cables", cab)
            if sc.get("disabled_port_node"):
                hub = sc["disabled_port_node"]
                iface = nb.dcim.interfaces.get(device_id=roadms[hub].id, name="DEG-1")
                iface.update({"enabled": False, "description": "SCENARIO: degree card fault (synthetic)",
                              "tags": [{"id": stag.id}]})
            print(f"  {sample}: {len(data['nodes'])} ROADMs, {len(data['edges'])} fiber cables"
                  + (f", scenarios {sc}" if sc else ""))


def rollback(nb):
    if not MANIFEST.exists():
        sys.exit(f"No manifest at {MANIFEST}; nothing to roll back.")
    objs = json.loads(MANIFEST.read_text(encoding="utf-8"))["objects"]
    order = ["dcim.cables", "dcim.devices", "dcim.sites", "dcim.site_groups", "dcim.interface_templates",
             "dcim.device_types", "dcim.device_roles", "dcim.manufacturers", "extras.tags"]
    removed = 0
    for endpoint in order:
        app, model = endpoint.split(".")
        ep = getattr(getattr(nb, app), model)
        items = [o for o in objs if o["endpoint"] == endpoint]
        if endpoint == "dcim.site_groups":
            items = list(reversed(items))  # children before parent
        for o in items:
            obj = ep.get(o["id"])
            if obj is not None:
                obj.delete()
                removed += 1
    MANIFEST.rename(MANIFEST.with_suffix(".rolled_back.json"))
    print(f"Rolled back {removed} ONDM synthetic objects.")


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("action", choices=["plan", "import", "rollback"])
    p.add_argument("--samples", nargs="*", help="subset of sample ids (default: all 30)")
    p.add_argument("--scenarios", action="store_true", help="inject tagged synthetic troubleshooting scenarios")
    a = p.parse_args()
    samples = a.samples or topo.list_samples()
    if a.action == "plan":
        print(json.dumps(plan(samples), indent=2))
        if a.scenarios:
            print({s: _scenario_choice(s) for s in SCENARIOS if s in samples})
        return
    nb = api()
    if a.action == "rollback":
        rollback(nb)
        return
    if MANIFEST.exists():
        sys.exit(f"Manifest {MANIFEST} exists - run rollback first (or delete it if the objects are gone).")
    print(f"Importing {len(samples)} synthetic topologies into {os.environ.get('NETBOX_URL')} ...")
    Importer(nb).run(samples, a.scenarios)
    print(f"Done. Manifest: {MANIFEST}")


if __name__ == "__main__":
    main()
