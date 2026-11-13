"""Read-only audit for ONDM image/JSON/YOLO dataset (v2)."""
from __future__ import annotations
import argparse
import csv
import json
import math
from collections import Counter
from pathlib import Path

import networkx as nx
from PIL import Image, ImageDraw, ImageFont


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--dataset', type=Path, required=True)
    p.add_argument('--out-dir', type=Path, required=True)
    p.add_argument('--contact-count', type=int, default=16)
    args = p.parse_args()
    root, out = args.dataset, args.out_dir
    out.mkdir(parents=True, exist_ok=True)
    problems, rows, hashes = [], [], Counter()
    graph_paths = sorted((root/'graphs').glob('*.json'))
    if not graph_paths:
        raise SystemExit('No graph JSON files found')
    for path in graph_paths:
        try:
            data = json.loads(path.read_text(encoding='utf-8'))
            name = data['sample_id']
            img_path = root/'images'/data['image']
            labels_path = root/'labels_yolo'/f'{name}.txt'
            with Image.open(img_path) as im:
                width, height = im.size
                im.verify()
            g = nx.Graph()
            for node in data['nodes']:
                if node['id'] in g:
                    problems.append((name, 'duplicate node id'))
                g.add_node(node['id'], equipment=node.get('equipment_type', 'UNSPECIFIED'))
            for e in data['edges']:
                u, v = e['source'], e['target']
                if u not in g or v not in g or u == v or g.has_edge(u,v):
                    problems.append((name, f'invalid edge {u}-{v}'))
                    continue
                length = float(e['distance_km'])
                if not math.isfinite(length) or length <= 0:
                    problems.append((name, f'invalid length for {u}-{v}'))
                g.add_edge(u, v, distance_km=length)
            for item in data['nodes']+data['edges']:
                box = item.get('bbox_xyxy_px')
                if box and not (0 <= box[0] < box[2] <= width and 0 <= box[1] < box[3] <= height):
                    problems.append((name, 'box outside image'))
            if not nx.is_connected(g):
                problems.append((name, 'disconnected graph'))
            labels = labels_path.read_text(encoding='utf-8').strip().splitlines()
            if len(labels) != len(data['nodes'])+len(data['edges']):
                problems.append((name, 'YOLO label count mismatch'))
            for line in labels:
                vals = line.split()
                if len(vals) != 5 or any(not math.isfinite(float(x)) or not 0 <= float(x) <= 1 for x in vals[1:]):
                    problems.append((name, 'invalid YOLO row'))
            signature = nx.weisfeiler_lehman_graph_hash(g)
            hashes[signature] += 1
            rows.append({'sample_id':name,'topology':data.get('topology_type',''),
                         'nodes':g.number_of_nodes(),'edges':g.number_of_edges(),
                         'diameter':nx.diameter(g) if nx.is_connected(g) else None,
                         'density':round(nx.density(g),5),
                         'total_km':round(sum(e['distance_km'] for _,_,e in g.edges(data=True)),3),
                         'graph_hash':signature,
                         'conflicts':data.get('metadata',{}).get('label_placement_conflicts',0),
                         'types':';'.join(f'{k}:{v}' for k,v in sorted(Counter(nx.get_node_attributes(g,'equipment').values()).items()))})
        except Exception as exc:
            problems.append((path.name, f'could not inspect: {exc}'))
    with (out/'dataset_statistics.csv').open('w',newline='',encoding='utf-8') as fh:
        writer=csv.DictWriter(fh,fieldnames=list(rows[0])); writer.writeheader();writer.writerows(rows)
    with (out/'validation_issues.csv').open('w',newline='',encoding='utf-8') as fh:
        writer=csv.writer(fh);writer.writerow(['sample_id','issue']);writer.writerows(problems)
    report = {'dataset':str(root),'total_graph_json':len(graph_paths),'audited':len(rows),
              'unique_unweighted_graph_hashes':len(hashes),
              'graph_hash_note':'WL hashes characterize structures but collisions are possible; exact graph isomorphism is needed for definitive uniqueness.',
              'topology_count':dict(Counter(r['topology'] for r in rows)),
              'sampled_class_counts':dict(Counter(r['types'] for r in rows)),
              'validation_issue_count':len(problems),
              'images_visually_verified':False,
              'optical_equipment_physically_verified':False,
              'independent_source_heldout_verified':False,
              'note':'This script is a structural audit, not optical simulation validation.'}
    (out/'audit_summary.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
    print(json.dumps(report,indent=2))
    print(f'Files written to: {out}')

if __name__=='__main__':
    main()
