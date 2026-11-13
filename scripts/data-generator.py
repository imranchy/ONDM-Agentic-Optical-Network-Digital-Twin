"""ONDM optical diagram dataset generator v2.

Produces diagrams, graph annotations, YOLO bounding boxes and rendering metadata.
ROADM sites are switching vertices; terminal transceivers attach at sites.
ILAs are modeled as in-line span equipment, never switching vertices.
Physical equipment parameters are declared assumptions, not measurements.
Requires: pillow, networkx, numpy (networkx layouts).
"""
from __future__ import annotations

import argparse
import csv
import json
import math
import random
from collections import Counter
from pathlib import Path

import networkx as nx
from PIL import Image, ImageDraw, ImageFont

TOPOLOGIES = ('ring', 'star', 'mesh', 'tree', 'hybrid', 'random')
EQUIPMENT = ('ROADM', 'ILA', 'TRANSCEIVER')
COLORS = {'ROADM': '#2563A6', 'ILA': '#E18B28', 'TRANSCEIVER': '#238B72'}
CLASS_IDS = {'ROADM': 0, 'ILA': 1, 'TRANSCEIVER': 2, 'fiber_link': 3}


def args_parse():
    p = argparse.ArgumentParser(description='Generate annotated optical-network diagrams (V2).')
    p.add_argument('--output-dir', default='optical_topology_v2_pilot')
    p.add_argument('--num-samples', type=int, default=30)
    p.add_argument('--min-nodes', type=int, default=6)
    p.add_argument('--max-nodes', type=int, default=12)
    p.add_argument('--image-size', type=int, default=1280)
    p.add_argument('--seed', type=int, default=2027)
    p.add_argument('--topologies', nargs='+', choices=TOPOLOGIES, default=list(TOPOLOGIES))
    p.add_argument('--difficulty', choices=('easy', 'medium', 'hard', 'mixed'), default='mixed')
    p.add_argument('--distance-min-km', type=int, default=40)
    p.add_argument('--distance-max-km', type=int, default=400)
    p.add_argument('--distance-step-km', type=int, default=10)
    p.add_argument('--train-ratio', type=float, default=.7)
    p.add_argument('--val-ratio', type=float, default=.15)
    p.add_argument('--no-splits', action='store_true')
    p.add_argument('--clear-existing', action='store_true', help='Clear only generated files in output directory.')
    a = p.parse_args()
    if not 3 <= a.min_nodes <= a.max_nodes <= 100:
        p.error('Require 3 <= min-nodes <= max-nodes <= 100')
    if a.image_size < 512:
        p.error('image-size must be >= 512')
    if a.num_samples < 1:
        p.error('num-samples must be positive')
    if a.distance_min_km <= 0 or a.distance_max_km < a.distance_min_km or a.distance_step_km <= 0:
        p.error('Invalid distance settings')
    if not (0 < a.train_ratio < 1 and 0 <= a.val_ratio < 1 and a.train_ratio + a.val_ratio < 1):
        p.error('Invalid split ratios')
    return a


def make_graph(kind, n, rng):
    seed = rng.randrange(2**31)
    if kind == 'ring':
        return nx.cycle_graph(n), kind
    if kind == 'star':
        return nx.star_graph(n - 1), kind
    if kind == 'tree':
        g = nx.random_tree(n, seed=seed) if hasattr(nx, 'random_tree') else nx.random_labeled_tree(n, seed=seed)
        return g, kind
    if kind == 'mesh':
        g = nx.random_labeled_tree(n, seed=seed)
        target = min(n * (n - 1) // 2, int(n * rng.uniform(1.2, 1.7)))
        choices = [(i, j) for i in range(n) for j in range(i + 1, n) if not g.has_edge(i, j)]
        rng.shuffle(choices)
        for u, v in choices[:max(0, target - g.number_of_edges())]:
            g.add_edge(u, v)
        return g, kind
    if kind == 'hybrid':
        g = nx.cycle_graph(max(3, n // 2))
        g.add_nodes_from(range(n))
        for v in range(max(3, n // 2), n):
            g.add_edge(v, rng.randrange(v))
        if n > 6:
            g.add_edge(0, n - 1)
        return g, kind
    mode = rng.choice(('erdos_renyi', 'watts_strogatz', 'barabasi_albert'))
    if mode == 'erdos_renyi':
        g = nx.erdos_renyi_graph(n, rng.uniform(.15, .3), seed=seed)
    elif mode == 'watts_strogatz':
        k = min(4, n - 1)
        if k % 2:
            k -= 1
        g = nx.watts_strogatz_graph(n, max(2, k), .25, seed=seed)
    else:
        g = nx.barabasi_albert_graph(n, min(2, n - 1), seed=seed)
    comps = [list(c) for c in nx.connected_components(g)]
    for c1, c2 in zip(comps, comps[1:]):
        g.add_edge(rng.choice(c1), rng.choice(c2))
    return g, f'random_{mode}'


def font(size, bold=False):
    names = (['C:/Windows/Fonts/arialbd.ttf', '/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf'] if bold else
             ['C:/Windows/Fonts/arial.ttf', '/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf'])
    for name in names:
        try:
            return ImageFont.truetype(name, size)
        except OSError:
            pass
    return ImageFont.load_default()


def node_id(i):
    s = ''
    while True:
        i, rem = divmod(i, 26)
        s = chr(65 + rem) + s
        if i == 0:
            return s
        i -= 1


def layout(g, n, size, rng, difficulty):
    # Multiple attempts: prefer spatially separated nodes.
    best, best_sep = None, -1
    margin = int(size * .11)
    for _ in range(7):
        raw = nx.spring_layout(g, seed=rng.randrange(2**31), iterations=110)
        xs, ys = [float(v[0]) for v in raw.values()], [float(v[1]) for v in raw.values()]
        xmin, xmax, ymin, ymax = min(xs), max(xs), min(ys), max(ys)
        pos = {u: (int(margin + (float(v[0]) - xmin) / max(1e-9, xmax-xmin) * (size - 2*margin)),
                   int(margin + (float(v[1]) - ymin) / max(1e-9, ymax-ymin) * (size - 2*margin))) for u, v in raw.items()}
        sep = min(math.dist(pos[u], pos[v]) for u in g for v in g if u < v)
        if sep > best_sep:
            best, best_sep = pos, sep
    return best, best_sep


def bbox_norm(box, size):
    x0, y0, x1, y1 = box
    x0, x1 = max(0, x0), min(size, x1)
    y0, y1 = max(0, y0), min(size, y1)
    return ((x0+x1)/(2*size), (y0+y1)/(2*size), max(1, x1-x0)/size, max(1, y1-y0)/size)


def intersects(a, b, pad=0):
    return not (a[2] + pad < b[0] or b[2] + pad < a[0] or a[3] + pad < b[1] or b[3] + pad < a[1])


def label_box(draw, text, fnt, x, y, pad=5):
    l, t, r, b = draw.textbbox((0, 0), text, font=fnt)
    w, h = r-l+2*pad, b-t+2*pad
    return (int(x-w/2), int(y-h/2), int(x+w/2), int(y+h/2))


def draw_text_center(draw, text, fnt, box, fill='#111827'):
    draw.rounded_rectangle(box, radius=5, fill='white', outline='#CBD5E1', width=1)
    l, t, r, b = draw.textbbox((0, 0), text, font=fnt)
    draw.text(((box[0]+box[2]-(r-l))/2-l, (box[1]+box[3]-(b-t))/2-t), text, font=fnt, fill=fill)


def sample_equipment(g, rng):
    # Every graph vertex is a switching site. Terminal transceivers are attached
    # equipment; ILA amplifiers are inserted along fiber spans, not at vertices.
    return {u: 'ROADM' for u in g.nodes()}


def render(g, kind, sid, size, rng, difficulty, distances, out_img):
    img = Image.new('RGB', (size, size), '#FFFFFF')
    d = ImageDraw.Draw(img)
    pos, separation = layout(g, g.number_of_nodes(), size, rng, difficulty)
    n = g.number_of_nodes()
    radius = max(14, min(31, int(size / (n * 3.5))))
    nf = font(max(13, int(size*.015)), bold=True)
    df = font(max(14, int(size*.016)), bold=True)
    equipment = sample_equipment(g, rng)
    occupied = []
    node_boxes = {}
    for u, (x, y) in pos.items():
        node_boxes[u] = (x-radius-4, y-radius-4, x+radius+4, y+radius+4)
        occupied.append(node_boxes[u])
    edge_items = []
    styles = ['solid', 'dashed'] if difficulty != 'easy' else ['solid']
    # Draw straight lines; crossing links remain a controlled source of difficulty.
    for u, v in sorted(g.edges()):
        x0, y0 = pos[u]; x1, y1 = pos[v]
        style = rng.choice(styles)
        width = max(2, int(size / 500))
        if style == 'solid':
            d.line((x0, y0, x1, y1), fill='#475569', width=width)
        else:
            length = math.dist((x0, y0), (x1, y1))
            for t in range(0, int(length), 19):
                a, b = t/length, min(1, (t+11)/length)
                d.line((x0+(x1-x0)*a, y0+(y1-y0)*a, x0+(x1-x0)*b, y0+(y1-y0)*b), fill='#475569', width=width)
        edge_items.append((u, v, style))
    # Place distance labels with candidate offsets, avoiding nodes and previous labels.
    label_records = []
    collisions = 0
    for u, v, style in edge_items:
        x0, y0 = pos[u]; x1, y1 = pos[v]
        dx, dy = x1-x0, y1-y0
        length = max(1, math.hypot(dx, dy))
        nxp, nyp = -dy/length, dx/length
        text = f'{distances[(u,v)]} km'
        candidates = []
        for frac in (.5, .36, .64, .25, .75):
            for offset in (23, -23, 37, -37, 52, -52):
                x = x0+frac*dx+offset*nxp
                y = y0+frac*dy+offset*nyp
                box = label_box(d, text, df, x, y)
                outside = box[0]<5 or box[1]<5 or box[2]>size-5 or box[3]>size-5
                overlap = sum(intersects(box, other, pad=3) for other in occupied)
                candidates.append((overlap+100*outside, box))
        score, chosen = min(candidates, key=lambda t: t[0])
        if score:
            collisions += 1
        occupied.append(chosen)
        draw_text_center(d, text, df, chosen)
        label_records.append({'source':node_id(u),'target':node_id(v),'text':text,'bbox_xyxy_px':list(chosen),'placement_conflicts':int(score)})
    nodes = []
    for u in sorted(g.nodes()):
        x, y = pos[u]
        typ = equipment[u]
        box = (x-radius, y-radius, x+radius, y+radius)
        if typ == 'ROADM':
            d.rounded_rectangle(box, radius=7, fill=COLORS[typ], outline='#17324D', width=2)
        elif typ == 'ILA':
            d.ellipse(box, fill=COLORS[typ], outline='#17324D', width=2)
        else:
            d.polygon([(x,y-radius),(x+radius,y),(x,y+radius),(x-radius,y)], fill=COLORS[typ])
        label = node_id(u)
        bb = d.textbbox((0,0), label, font=nf)
        d.text((x-(bb[2]-bb[0])/2-bb[0], y-(bb[3]-bb[1])/2-bb[1]), label, font=nf, fill='white')
        nodes.append({'id':label,'equipment_type':typ,'position_px':{'x':x,'y':y},'bbox_xyxy_px':list(box),
                      'site_role':'terminal_roadm' if g.degree(u)==1 else 'switching_roadm',
                      'attached_transceiver':g.degree(u)==1})
    img.save(out_img)
    edges = []
    yolo = []
    for nd in nodes:
        vals = bbox_norm(nd['bbox_xyxy_px'], size)
        yolo.append(f"{CLASS_IDS[nd['equipment_type']]} " + ' '.join(f'{v:.6f}' for v in vals))
    for u, v, style in edge_items:
        x0, y0 = pos[u]; x1, y1 = pos[v]
        box = (min(x0,x1)-5,min(y0,y1)-5,max(x0,x1)+5,max(y0,y1)+5)
        vals = bbox_norm(box,size)
        yolo.append(f"{CLASS_IDS['fiber_link']} " + ' '.join(f'{v:.6f}' for v in vals))
        edges.append({'source':node_id(u),'target':node_id(v),'distance_km':distances[(u,v)],
                      'visual_style':style,'bbox_xyxy_px':list(box),
                      'site_role':'terminal_roadm' if g.degree(u)==1 else 'switching_roadm',
                      'attached_transceiver':g.degree(u)==1})
    graph = {'sample_id':sid,'image':out_img.name,'topology_type':kind,'nodes':nodes,'edges':edges,
             'metadata':{'schema_version':'2.0','difficulty':difficulty,'image_size':size,
                         'node_separation_min_px':round(separation,1), 'label_placement_conflicts':collisions,
                         'distance_label_boxes':label_records,'equipment_semantics':'ROADM switching sites; endpoint transceivers attached; inline EDFAs on spans',
                         'physical_layer':'synthetic reference design, not field measurements',
                         'simulation_parameters':'GNPy example equipment profile; parameters are assumptions',
                         'logical_graph_representation':'ROADM sites only; optical spans include inline amplifiers'}}
    return graph, yolo


def main():
    a = args_parse()
    output = Path(a.output_dir).resolve()
    # Prevent accidental deletion of old datasets; V2 requires a dedicated output directory.
    if a.clear_existing and output.exists():
        marker = output / '.ondm_v2_generated'
        if not marker.exists():
            raise SystemExit('Refusing --clear-existing: directory lacks V2 safety marker')
        for folder, ext in (('images','png'),('graphs','json'),('labels_yolo','txt')):
            for f in (output/folder).glob(f'topo_*.{ext}'):
                f.unlink()
    elif output.exists() and any((output/'graphs').glob('topo_*.json')):
        raise SystemExit('Output already contains generated graphs; choose a new directory or use --clear-existing with V2 marker')
    for sub in ('images','graphs','labels_yolo'):
        (output/sub).mkdir(parents=True,exist_ok=True)
    (output/'.ondm_v2_generated').write_text('Generated by ONDM V2; safe clear marker.\n')
    rng = random.Random(a.seed)
    dist_choices = list(range(a.distance_min_km,a.distance_max_km+1,a.distance_step_km))
    if not dist_choices:
        raise SystemExit('No valid distance choices')
    manifest=[]
    for i in range(1,a.num_samples+1):
        sid=f'topo_{i:04d}'
        topo=rng.choice(a.topologies)
        n=rng.randint(a.min_nodes,a.max_nodes)
        g, actual=make_graph(topo,n,rng)
        difficulty=rng.choice(('easy','medium','hard')) if a.difficulty=='mixed' else a.difficulty
        distances={(min(u,v),max(u,v)):rng.choice(dist_choices) for u,v in g.edges()}
        data,yolo=render(g,actual,sid,a.image_size,rng,difficulty,distances,output/'images'/f'{sid}.png')
        (output/'graphs'/f'{sid}.json').write_text(json.dumps(data,indent=2),encoding='utf-8')
        (output/'labels_yolo'/f'{sid}.txt').write_text('\n'.join(yolo)+'\n',encoding='utf-8')
        manifest.append({'sample_id':sid,'topology':actual,'nodes':n,'edges':g.number_of_edges(),
                         'diameter_hops':nx.diameter(g),'difficulty':difficulty,
                         'label_conflicts':data['metadata']['label_placement_conflicts']})
        if i%25==0 or i==a.num_samples:
            print(f'Generated {i}/{a.num_samples}')
    with (output/'manifest.csv').open('w',newline='',encoding='utf-8') as f:
        w=csv.DictWriter(f,fieldnames=list(manifest[0]));w.writeheader();w.writerows(manifest)
    (output/'generation_config.json').write_text(json.dumps(vars(a),indent=2),encoding='utf-8')
    if not a.no_splits:
        ids=[r['sample_id'] for r in manifest]
        rng.shuffle(ids)
        ntr=int(len(ids)*a.train_ratio);nv=int(len(ids)*a.val_ratio)
        for name,subset in [('train',ids[:ntr]),('val',ids[ntr:ntr+nv]),('test',ids[ntr+nv:])]:
            (output/f'{name}.txt').write_text('\n'.join(f'images/{x}.png' for x in subset)+'\n',encoding='utf-8')
        yaml='path: '+output.as_posix()+'\ntrain: train.txt\nval: val.txt\ntest: test.txt\nnames:\n'
        yaml+=''.join(f'  {i}: {name}\n' for name,i in CLASS_IDS.items())
        (output/'dataset.yaml').write_text(yaml,encoding='utf-8')
    print('Done:',output)
    print('Topology counts:',dict(Counter(x['topology'] for x in manifest)))
    print('Samples with label placement conflicts:',sum(x['label_conflicts']>0 for x in manifest))
    print('NOTE: Physical layer uses documented synthetic assumptions; run GNPy validation before use.')

if __name__=='__main__':
    main()
