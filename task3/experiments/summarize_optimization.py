"""Audit and summarize paired optimization logs without excluding failed runs.

Bootstrap resamples whole scenarios, computing sum(time)/sum(source_count).
Different development groups are compared only on their explicitly reported
shared seeds. Incomplete groups cannot silently become a promotion claim.
"""

from __future__ import annotations

import argparse
import csv
import gzip
import json
import math
from pathlib import Path

import numpy as np


def audit_actions(row, physical):
    """Post-run truth audit only; no simulator truth enters any controller."""
    if 'actions' not in row:
        return
    position = (0., 0.)
    channel = 1
    elapsed = 0.
    cleared = set()
    sources = {s['channel']: s for s in row['sources']}
    for action in row['actions']:
        if action['path'] not in ('/measure', '/clear'):
            continue
        point = action['position']
        elapsed += math.dist(position, point)/physical['speed_mps']
        position = point
        source = sources.get(action['channel'])
        distance = math.inf if source is None else math.dist(point, source['position'])
        active = source is not None and action['channel'] not in cleared
        response = action['response']
        if action['path'] == '/measure':
            elapsed += physical['measure_s'] + (physical['switch_s'] if channel != action['channel'] else 0.)
            channel = action['channel']
            if not active or distance > source['reception_radius_m']:
                assert response['measure_result'] == 'no_signal'
            elif distance <= physical['near_radius_m']:
                assert response['measure_result'] == 'near'
            else:
                assert response['measure_result'] == 'direction'
                truth = math.degrees(math.atan2(source['position'][1]-point[1], source['position'][0]-point[0]))
                error = abs((response['svd_deg']-truth+180.) % 360.-180.)
                assert error <= physical['bearing_error_deg']+1e-7
        else:
            hit = active and distance <= physical['clear_radius_m']+1e-9
            assert (response['clear_result'] == 'success') == hit
            elapsed += physical['optical_s'] + (physical['laser_s'] if hit else 0.)
            if hit:
                cleared.add(action['channel'])
        assert abs(response['virtual_time_s']-elapsed) < 1e-6
    assert len(cleared) == row['result']['cleared_count']
    if row['result']['success']:
        assert cleared == set(sources)


def read_runs(paths):
    runs = {}
    metadata = []
    truths = {}
    for path in paths:
        with gzip.open(path, 'rt', encoding='utf-8') as handle:
            meta = json.loads(next(handle))
            metadata.append({'path': str(path), 'metadata': meta})
            seen = set()
            for line in handle:
                row = json.loads(line)
                seed = row['scenario_seed']
                key = (row['policy'], seed, row['source_count'])
                if key in runs:
                    raise ValueError(f'duplicate run: {key}')
                truth_key = (seed, row['source_count'])
                truth = json.dumps(row['sources'], sort_keys=True)
                if truth_key in truths and truths[truth_key] != truth:
                    raise ValueError(f'unpaired scenario truth: {truth_key}')
                truths[truth_key] = truth
                result = row['result']
                audit_actions(row, meta['configuration']['PhysicalConfig'])
                if abs(sum(result['time_breakdown'].values()) - result['virtual_time_s']) > 1e-6:
                    raise ValueError(f'time accounting mismatch: {key}')
                operations = sorted((d for d in result['diagnostics']
                    if d['type'] == 'actual_operation'), key=lambda d: d['operation_id'])
                if operations:
                    if [d['operation_id'] for d in operations] != list(range(1, result['action_count']+1)):
                        raise ValueError(f'operation identity mismatch: {key}')
                    if abs(sum(d['cost_s'] for d in operations) - result['virtual_time_s']) > 1e-6:
                        raise ValueError(f'operation accounting mismatch: {key}')
                runs[key] = row
                seen.add((row['policy'], seed))
            expected = {(policy, meta['paired_scenario_seed_start']+i)
                for policy in meta['policies'] for i in range(meta['case_count'])}
            if seen != expected:
                raise ValueError(f'incomplete batch {path}: missing={expected-seen}, extra={seen-expected}')
    return runs, metadata


def summarize(runs, baseline, bootstrap, seed):
    rng = np.random.default_rng(seed)
    groups = {}
    for (policy, scenario_seed, count), row in runs.items():
        groups.setdefault(policy, {})[(scenario_seed, count)] = row
    summaries, paired, strata = [], [], []
    for policy, group in sorted(groups.items()):
        selected = [group[k] for k in sorted(group)]
        t = np.array([r['result']['virtual_time_s'] for r in selected])
        n = np.array([r['source_count'] for r in selected])
        ids = rng.integers(0, len(t), (bootstrap, len(t)))
        ratios = t[ids].sum(axis=1) / n[ids].sum(axis=1)
        success = sum(r['result']['success'] and r['result']['cleared_count'] == r['source_count'] for r in selected)
        info = {'policy': policy, 'cases': len(t), 'sources': int(n.sum()),
            'successful_cases': success, 'all_clear': success == len(t),
            'mean_case_s': float(t.mean()), 'total_time_per_source_s': float(t.sum()/n.sum()),
            'ratio_ci_low_s': float(np.quantile(ratios, .025)),
            'ratio_ci_high_s': float(np.quantile(ratios, .975)),
            'p90_case_s': float(np.quantile(t, .9)), 'p95_case_s': float(np.quantile(t, .95)),
            'max_case_s': float(t.max()),
            'mean_wall_s': float(np.mean([r['result']['wall_runtime_s'] for r in selected])),
            'max_wall_s': float(max(r['result']['wall_runtime_s'] for r in selected)),
            'unexpected_clear_failures': sum(d['type'] == 'unexpected_clear_failure'
                for r in selected for d in r['result']['diagnostics'])}
        for key in selected[0]['result']['time_breakdown']:
            info['mean_'+key] = float(np.mean([r['result']['time_breakdown'][key] for r in selected]))
        summaries.append(info)
        for count in sorted(set(n)):
            values = t[n == count]
            strata.append({'policy': policy, 'sources_per_case': int(count), 'cases': len(values),
                           'mean_time_per_source_s': float(values.mean()/count)})
        if policy == baseline or baseline not in groups:
            continue
        common = sorted(group.keys() & groups[baseline].keys())
        if not common:
            continue
        delta = np.array([groups[baseline][k]['result']['virtual_time_s'] - group[k]['result']['virtual_time_s'] for k in common])
        counts = np.array([k[1] for k in common])
        ids = rng.integers(0, len(common), (bootstrap, len(common)))
        improvement = delta[ids].sum(axis=1)/counts[ids].sum(axis=1)
        paired.append({'policy': policy, 'baseline': baseline, 'paired_cases': len(common),
            'candidate_unpaired_cases': len(group)-len(common),
            'baseline_unpaired_cases': len(groups[baseline])-len(common),
            'mean_saved_case_s': float(delta.mean()),
            'saved_per_source_s': float(delta.sum()/counts.sum()),
            'saved_ratio_ci_low_s': float(np.quantile(improvement,.025)),
            'saved_ratio_ci_high_s': float(np.quantile(improvement,.975)),
            'case_win_rate': float(np.mean(delta>1e-6)),
            'worst_regression_s': float(max(0.,-delta.min())),
            'paired_seeds': ';'.join(str(k[0]) for k in common)})
    return summaries, paired, strata


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--inputs', nargs='+', type=Path, required=True)
    parser.add_argument('--output-dir', type=Path, required=True)
    parser.add_argument('--baseline', default='candidate_041_dynamic_open_route_deferred_cross_view')
    parser.add_argument('--bootstrap', type=int, default=5000)
    parser.add_argument('--seed', type=int, default=20261201)
    args = parser.parse_args()
    if args.bootstrap < 1:
        parser.error('bootstrap must be positive')
    runs, metadata = read_runs(args.inputs)
    summary, paired, strata = summarize(runs,args.baseline,args.bootstrap,args.seed)
    args.output_dir.mkdir(parents=True,exist_ok=True)
    for name, rows in [('summary',summary),('paired',paired),('strata',strata)]:
        if not rows:
            continue
        with (args.output_dir/f'{name}.csv').open('w',newline='',encoding='utf-8') as handle:
            writer=csv.DictWriter(handle,fieldnames=list(rows[0]))
            writer.writeheader()
            writer.writerows(rows)
    (args.output_dir/'audit.json').write_text(json.dumps({
        'bootstrap':args.bootstrap,'bootstrap_seed':args.seed,
        'baseline':args.baseline,'inputs':metadata,'summary':summary,'paired':paired,
        'note':'Selection/development results are not independent holdout evidence.'},
        ensure_ascii=False,indent=2),encoding='utf-8')
    for row in summary:
        print(row['policy'],row['successful_cases'], '/',row['cases'],
              f"{row['total_time_per_source_s']:.2f} s/source",
              f"CI [{row['ratio_ci_low_s']:.2f}, {row['ratio_ci_high_s']:.2f}]")


if __name__ == '__main__':
    main()
