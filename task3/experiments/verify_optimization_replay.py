"""Re-run frozen historical/batch cases and compare every executed action."""

from dataclasses import asdict
import gzip
import hashlib
import json
from pathlib import Path

import numpy as np

from task3.src.config import PhysicalConfig, PlannerConfig
from task3.src.dynamic_open_route_controller import DynamicOpenRouteController
from task3.src.mock_simulator import MockSimulator, Scenario, Source
from task3.src.optimized_controller import OptimizedController


def main():
    root = Path('task3/results/raw/optimization')
    references = [
        ('dynamic_open_route_041_random20_seed20261016.jsonl.gz',
         'candidate_041_dynamic_open_route_deferred_cross_view', [20261016]),
        ('optimization_049_validation30.jsonl.gz', 'candidate_049_joint_completion',
         [20261210, 20261211]),
        ('optimization_057_validation30.jsonl.gz', 'candidate_057_posterior_free',
         [20261210]),
    ]
    checks = []
    for file, policy, seeds in references:
        with gzip.open(root/file, 'rt', encoding='utf-8') as handle:
            meta = json.loads(next(handle))
            rows = [json.loads(line) for line in handle]
        selected = [r for r in rows if r['policy'] == policy and r['scenario_seed'] in seeds]
        assert len(selected) == len(seeds)
        for row in selected:
            physical = PhysicalConfig(**meta['configuration']['PhysicalConfig'])
            planner = PlannerConfig(**row['planner'])
            scenario = Scenario(row['scenario_id'], row['scenario_seed'], tuple(
                Source(s['channel'], tuple(s['position']), s['reception_radius_m']) for s in row['sources']))
            mock = MockSimulator(scenario, physical)
            controller = OptimizedController if row['controller'] == 'optimized_open_route' else DynamicOpenRouteController
            result = controller(mock, physical, planner, known_total=None).run()
            assert result.success and result.cleared_count == row['source_count']
            assert abs(result.virtual_time_s-row['result']['virtual_time_s']) < 1e-6
            assert len(mock.actions) == len(row['actions'])
            for actual, expected in zip(mock.actions, row['actions']):
                assert actual['path'] == expected['path']
                assert actual.get('channel') == expected.get('channel')
                if 'position' in actual:
                    np.testing.assert_allclose(actual['position'], expected['position'], rtol=0., atol=1e-8)
                for field in ('measure_result', 'svd_deg', 'clear_result', 'virtual_time_s'):
                    a, e = actual['response'].get(field), expected['response'].get(field)
                    if isinstance(a, (float, int)):
                        assert abs(a-e) < 1e-6
                    else:
                        assert a == e
            check = {'policy': policy, 'seed': row['scenario_seed'], 'reference': file,
                     'virtual_time_s': result.virtual_time_s, 'actions': result.action_count,
                     'all_actions_match': True, 'planner': asdict(planner)}
            checks.append(check)
            print(policy, row['scenario_seed'], 'all actions match', flush=True)
    output = Path('task3/results/tables/optimization_replay.json')
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps({'checks': checks, 'implementation_sha256': {
        str(p.as_posix()): hashlib.sha256(p.read_bytes()).hexdigest()
        for p in sorted(Path('task3/src').glob('*.py'))}}, indent=2), encoding='utf-8')


if __name__ == '__main__':
    main()
