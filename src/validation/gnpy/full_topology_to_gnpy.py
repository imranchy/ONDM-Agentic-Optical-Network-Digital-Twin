"""Convert an equipment-aware ONDM diagram graph into a bidirectional GNPy network.

Only ROADM graph vertices are accepted. Terminal transceivers attach to ROADM
sites; ILA/EDFA elements are located INSIDE directed fiber chains, never used
as switching vertices. Requires the GNPy example equipment file for the
selected reference optical design. All fiber/amplifier parameters are assumed.
"""
from __future__ import annotations
import argparse
import copy
import json
import math
import re
from pathlib import Path
import networkx as nx


def load(path):
    return json.loads(Path(path).read_text(encoding='utf-8'))


def dump(path, data):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2), encoding='utf-8')


def safe(value):
    return re.sub(r'[^A-Za-z0-9_-]', '_', str(value))


def convert(args):
    data = load(args.graph)
    graph = nx.Graph()
    node_types = {}
    for node in data['nodes']:
        uid = str(node['id'])
        if not uid or uid in node_types:
            raise ValueError(f'Invalid or duplicate node {uid!r}')
        typ = node.get('equipment_type')
        if typ != 'ROADM':
            raise ValueError(f'{uid} is {typ}, not ROADM. Legacy illustrative datasets cannot be converted faithfully. Regenerate using updated data-generator.py.')
        node_types[uid] = typ
        graph.add_node(uid)
    if len({safe(x) for x in node_types}) != len(node_types):
        raise ValueError('Node identifiers collide after normalization')
    for edge in data['edges']:
        u, v = str(edge['source']), str(edge['target'])
        if u not in graph or v not in graph or u == v or graph.has_edge(u,v):
            raise ValueError(f'Invalid edge {u}-{v}')
        distance = float(edge['distance_km'])
        if not math.isfinite(distance) or distance <= 0:
            raise ValueError('Distance must be finite and positive')
        graph.add_edge(u,v,distance_km=distance)
    if not nx.is_connected(graph):
        raise ValueError('Disconnected network')
    if args.source not in graph or args.target not in graph or args.source == args.target:
        raise ValueError('Invalid source/destination')
    if not 0 < args.max_span_km <= 120:
        raise ValueError('max-span-km must be between 0 and 120 km')

    ref = load(args.reference)
    templates = {e['type']:e for e in ref['elements']}
    for typ in ('Fiber','Edfa','Transceiver'):
        if typ not in templates:
            raise ValueError(f'Missing {typ} template in reference')
    elements, connections, ids, arcs = [], [], set(), set()
    def add(element):
        uid=element['uid']
        if uid in ids:
            raise ValueError('Duplicate GNPy UID: '+uid)
        ids.add(uid)
        elements.append(element)
    def connect(a,b):
        if (a,b) in arcs:
            raise ValueError(f'Duplicate arc {a} -> {b}')
        arcs.add((a,b))
        connections.append({'from_node':a,'to_node':b})
    def templated(typ, uid):
        t=copy.deepcopy(templates[typ]); t['uid']=uid
        return t

    for site in sorted(graph):
        # A switching site is a genuine GNPy ROADM, not an ILA proxy.
        roadm = {'uid':f'Roadm_{safe(site)}','type':'Roadm','type_variety':'default'}
        add(roadm)
        # Test transceivers are attached at all ROADM sites for pairwise tests.
        # This is explicit endpoint equipment, not a transit node.
        trx=templated('Transceiver',f'Trx_{safe(site)}')
        add(trx)
        connect(trx['uid'],roadm['uid'])
        connect(roadm['uid'],trx['uid'])

    chains=[]
    for u,v in sorted(graph.edges()):
        distance=graph[u][v]['distance_km']
        spans=math.ceil(distance/args.max_span_km)
        span_length=distance/spans
        for origin,dest in ((u,v),(v,u)):
            prev=f'Roadm_{safe(origin)}'
            chain=[prev]
            tag=f'{safe(origin)}__{safe(dest)}'
            for i in range(spans):
                fiber=templated('Fiber',f'Fiber_{tag}_{i+1}')
                fiber.setdefault('params',{})['length']=round(span_length,8)
                fiber['params']['length_units']='km'
                add(fiber);connect(prev,fiber['uid']);prev=fiber['uid'];chain.append(prev)
                if i < spans-1:
                    edfa=templated('Edfa',f'Edfa_ILA_{tag}_{i+1}')
                    # Let GNPy autodesign calculate operating gain and VOA.
                    edfa.pop('operational',None)
                    add(edfa);connect(prev,edfa['uid']);prev=edfa['uid'];chain.append(prev)
            connect(prev,f'Roadm_{safe(dest)}')
            chain.append(f'Roadm_{safe(dest)}')
            chains.append({'source':origin,'target':dest,'length_km':distance,
                           'spans':spans,'inline_amplifiers':spans-1,'elements':chain})

    routes=[]
    from itertools import islice
    for path in islice(nx.shortest_simple_paths(graph,args.source,args.target,weight='distance_km'),args.k_paths):
        length=sum(graph[u][v]['distance_km'] for u,v in zip(path,path[1:]))
        routes.append({'sites':path,'length_km':length})
    dg=nx.DiGraph(arcs)
    if not nx.has_path(dg,f'Trx_{safe(args.source)}',f'Trx_{safe(args.target)}'):
        raise RuntimeError('Directed GNPy path missing')
    output={'network_name':'ONDM_'+safe(data.get('sample_id','graph')),
            'elements':elements,'connections':connections}
    dump(args.output,output)
    assumptions={'status':'PHYSICALLY STRUCTURED, NOT FIELD-VALIDATED',
      'source_graph':str(args.graph),'equipment_reference':str(args.reference),
      'site_semantics':'Every graph vertex is a ROADM; no ILA or transceiver is a switching vertex',
      'transceivers':'One simulated endpoint transceiver attached to each ROADM',
      'inline_amplifiers':'Separate unidirectional EDFAs between fiber spans; type and parameters from GNPy reference',
      'fiber':'SSMF reference fiber; loss/PMD/connector values from example, not measurements',
      'span_limit_km':args.max_span_km,
      'roadm':'GNPy default ROADM equipment library variety; not measured hardware',
      'topology_directionality':'Each undirected edge becomes two independent directed line systems',
      'limits':'No real inventory, site coordinates, spectral occupancy, measured losses, ROADM degree constraints, or validated transceiver mode',
      'reference_routes':routes,'directed_chains':chains,
      'counts':{'sites':len(node_types),'links':graph.number_of_edges(),
                'elements':len(elements),'connections':len(connections)}}
    dump(Path(args.output).with_suffix('.assumptions.json'),assumptions)
    print(f'Wrote {args.output}: {len(node_types)} ROADMs, {graph.number_of_edges()} links, {len(elements)} GNPy elements')
    for route in routes:
        print('Route:', ' -> '.join(route['sites']),f"({route['length_km']:g} km)")
    print('No ILA or transceiver proxy switching nodes. Physical parameters remain assumptions.')


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--graph',type=Path,required=True)
    p.add_argument('--reference',type=Path,required=True)
    p.add_argument('--output',type=Path,required=True)
    p.add_argument('--source',default='A')
    p.add_argument('--target',default='C')
    p.add_argument('--max-span-km',type=float,default=80)
    p.add_argument('--k-paths',type=int,default=2)
    args=p.parse_args()
    if not 1 <= args.k_paths <= 10:
        p.error('--k-paths must be 1..10')
    convert(args)

if __name__=='__main__':
    main()
