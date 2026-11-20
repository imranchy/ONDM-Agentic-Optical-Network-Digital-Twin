"""First ONDM proof of concept: convert ONE annotated link to a GNPy line.

This intentionally does not model full ROADM/ILA behavior or a network digital twin.
Uses installed GNPy reference equipment and a reproducible span assumption.
"""
import argparse
import copy
import json
import math
from pathlib import Path


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--graph', required=True, type=Path)
    p.add_argument('--reference', required=True, type=Path,
                   help='Installed GNPy edfa_example_network.json')
    p.add_argument('--source', default='A')
    p.add_argument('--target', default='B')
    p.add_argument('--max-span-km', type=float, default=80.0)
    p.add_argument('--output', required=True, type=Path)
    a = p.parse_args()
    if a.max_span_km <= 0:
        p.error('--max-span-km must be positive')
    graph = json.loads(a.graph.read_text(encoding='utf-8'))
    ref = json.loads(a.reference.read_text(encoding='utf-8'))
    nodes = {n['id'] for n in graph['nodes']}
    if a.source not in nodes or a.target not in nodes:
        p.error('Source/target node not found in graph')
    edge = next((e for e in graph['edges'] if {e['source'],e['target']} == {a.source,a.target}), None)
    if edge is None:
        p.error('This proof of concept only supports directly connected endpoints')
    distance = float(edge['distance_km'])
    if not math.isfinite(distance) or distance <= 0:
        p.error('Invalid fiber length')
    n_spans = math.ceil(distance / a.max_span_km)
    span_length = distance / n_spans
    templates = {x['type']: x for x in ref['elements']}
    for required in ('Transceiver', 'Fiber', 'Edfa'):
        if required not in templates:
            p.error(f'Reference example missing {required} template')
    elements, connections = [], []
    def add(element):
        if elements:
            connections.append({'from_node': elements[-1]['uid'], 'to_node': element['uid']})
        elements.append(element)
    src = copy.deepcopy(templates['Transceiver'])
    src['uid'] = f'Trx_{a.source}'
    add(src)
    for i in range(n_spans):
        fiber = copy.deepcopy(templates['Fiber'])
        fiber['uid'] = f'Fiber_{i+1}'
        fiber['params']['length'] = round(span_length, 6)
        fiber['params']['length_units'] = 'km'
        add(fiber)
        if i < n_spans - 1:
            amp = copy.deepcopy(templates['Edfa'])
            amp['uid'] = f'Edfa_{i+1}'
            # Let GNPy autodesign determine gain where supported.
            amp.pop('operational', None)
            add(amp)
    dst = copy.deepcopy(templates['Transceiver'])
    dst['uid'] = f'Trx_{a.target}'
    add(dst)
    result = {'network_name': f'ONDM_poc_{graph["sample_id"]}_{a.source}_{a.target}',
              'elements': elements, 'connections': connections}
    a.output.parent.mkdir(parents=True, exist_ok=True)
    a.output.write_text(json.dumps(result, indent=2), encoding='utf-8')
    assumptions = {
        'source_graph': str(a.graph), 'source': a.source, 'target': a.target,
        'diagram_edge_distance_km': distance, 'fiber_span_count': n_spans,
        'fiber_span_length_km': span_length,
        'modeling_scope': 'One directed optical line, not full network or ROADM/ILA mapping',
        'endpoint_assumption': 'Test transceivers replace original node equipment semantics',
        'fiber_and_edfa_assumption': 'Parameters copied from installed GNPy example',
        'validation_status': 'Generated schema only; GNPy simulation must be executed and checked'
    }
    a.output.with_suffix('.assumptions.json').write_text(json.dumps(assumptions, indent=2), encoding='utf-8')
    print(f'Generated {a.output} | {distance:g} km | {n_spans} spans of {span_length:g} km')
    print('Next: run gnpy-transmission-example with this topology and reference equipment library.')

if __name__ == '__main__':
    main()
