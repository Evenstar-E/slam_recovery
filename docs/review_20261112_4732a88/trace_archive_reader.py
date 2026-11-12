"""Read only the requested Git blobs with stdlib; never execute archived code.
Run with: python -I <this_script> --repo <repo> --output <new_json_path>
All interval matches are candidate relations, not provenance assertions.
"""
import argparse
import collections
import decimal
import gzip
import hashlib
import json
import math
import pathlib
import subprocess

COMMIT = 'ffd4b13ce86d03556e389e42236e913d4701cf8d'
BASE = 'docs/review_20261112_four_host/'
PRIMARY = 'trace_fl_native_20261112T115734Z_483777'
COMPARISON = 'trace_fl_native_20261112T115203Z_476840'
SUFFIXES = ['receipt.json', 'run_summary.json', 'availability_frames.jsonl.gz',
            'host_logs/trace_cov.txt', 'host_logs/mat_pre.txt', 'host_logs/mat_out.txt', 'SHA256SUMS']


def histogram(values):
    return dict(sorted(collections.Counter(str(v) for v in values).items()))


def duplicates(values):
    c = collections.Counter(values)
    return {'distinct_values': len(c), 'repeated_values': sum(v > 1 for v in c.values()),
            'excess_rows': sum(v - 1 for v in c.values()),
            'multiplicity_histogram': histogram(c.values()),
            'examples': [{'value': k, 'rows': v} for k, v in c.items() if v > 1][:12]}


def compact_summary(summary):
    keys = ['run_id', 'candidate_source', 'detection_enabled', 'parameters', 'pairing', 'nis', 'frames']
    result = {k: summary.get(k) for k in keys}
    result['quarantine_episode_count_claim'] = summary.get('quarantine', {}).get('episodes')
    result['decision_count_claim'] = len(summary.get('decisions', [])) if isinstance(summary.get('decisions'), list) else 'UNKNOWN'
    result['all_other_summary_sections'] = 'not evaluated; no outcome or wiring success inferred'
    return result


def precision_stats(values):
    values = [v for v in values if v >= 0]
    return {'count': len(values), 'unique': len(set(values)),
            'mod_256_histogram': histogram(v % 256 for v in values),
            'binary64_exact_integer_count': sum(int(float(v)) == v for v in values),
            'binary64_ulp_ns_histogram': histogram(int(math.ulp(float(v))) for v in values),
            'gcd_of_nonzero_differences': math.gcd(*(abs(b-a) for a, b in zip(values, values[1:]) if a != b))}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--repo', required=True)
    parser.add_argument('--output', required=True)
    args = parser.parse_args()
    repo = pathlib.Path(args.repo).resolve()
    output = pathlib.Path(args.output).resolve()
    if output.exists():
        raise SystemExit('Refusing to overwrite existing output: ' + str(output))
    output.parent.mkdir(parents=True, exist_ok=True)
    cache = {}
    def git(*parts):
        return subprocess.check_output(['git', '-C', str(repo), *parts])
    def blob(path):
        if path not in cache:
            cache[path] = git('show', COMMIT + ':' + path)
        return cache[path]
    primary = {s: blob(BASE + PRIMARY + '/' + s) for s in SUFFIXES}
    comparison = {s: blob(BASE + COMPARISON + '/' + s) for s in SUFFIXES[:2]}
    receipt = json.loads(primary['receipt.json'])
    summary = json.loads(primary['run_summary.json'])
    old_receipt = json.loads(comparison['receipt.json'])
    old_summary = json.loads(comparison['run_summary.json'])
    files = []
    manifest = {}
    for line in primary['SHA256SUMS'].decode('utf-8').splitlines():
        if line.strip():
            digest, name = line.split(None, 1)
            manifest[name.lstrip('*').removeprefix('./')] = digest
    for run, data in [(PRIMARY, primary), (COMPARISON, comparison)]:
        for suffix, raw in data.items():
            expected = manifest.get(suffix) if run == PRIMARY else None
            actual = hashlib.sha256(raw).hexdigest()
            files.append({'path': BASE + run + '/' + suffix, 'bytes': len(raw),
                          'git_blob_oid': git('rev-parse', COMMIT + ':' + BASE + run + '/' + suffix).decode().strip(),
                          'sha256': actual, 'manifest_sha256': expected,
                          'manifest_status': 'MATCH' if expected == actual else 'MISMATCH' if expected else 'NOT_LISTED_OR_NOT_IN_SCOPE'})

    trace_text = primary['host_logs/trace_cov.txt'].decode('utf-8')
    trace_headers = [line for line in trace_text.splitlines() if line.startswith('#')]
    declared = next(line[1:].strip().split() for line in trace_headers if line.startswith('# idx '))
    widths = {'vec6': 6, 'Ppre6x6': 36, 'Ppost6x6': 36}
    columns = []
    spans = {}
    for name in declared:
        width = widths.get(name, 1)
        spans[name] = [len(columns), len(columns)+width]
        columns.extend([name] if width == 1 else [name+'['+str(i)+']' for i in range(width)])
    required_prefix = ['idx', 'rel_s', 'abs_ns', 'grp_idx', 'scan_first_ns', 'scan_last_ns', 'has_out', 'phase', 'eff']
    if columns[:len(required_prefix)] != required_prefix:
        raise SystemExit('Unrecognized declared trace layout; refusing positional guesses')
    trace = []
    raw_trace = []
    malformed_trace_rows = []
    trace_lines = trace_text.splitlines()
    integer_names = ['idx', 'abs_ns', 'grp_idx', 'scan_first_ns', 'scan_last_ns', 'has_out', 'phase', 'eff']
    for line_no, line in enumerate(trace_lines, 1):
        if not line.strip() or line.startswith('#'):
            continue
        tokens = line.split()
        if len(tokens) != len(columns):
            malformed_trace_rows.append({'line_no': line_no, 'actual_width': len(tokens),
                                         'expected_width': len(columns), 'prefix': tokens[:14],
                                         'final_line': line_no == len(trace_lines),
                                         'ends_in_newline': trace_text.endswith('\n')})
            if line_no != len(trace_lines) or trace_text.endswith('\n') or len(tokens) < 14:
                raise SystemExit('Non-tail trace width mismatch at line ' + str(line_no))
            # Retain only fully available prefix fields. Never pad missing covariance.
        row = {name: int(tokens[columns.index(name)]) for name in integer_names}
        row['complete'] = len(tokens) == len(columns)
        row['rel_s'] = decimal.Decimal(tokens[columns.index('rel_s')])
        row['line_no'] = line_no
        row['ordinal'] = len(trace)
        trace.append(row)
        raw_trace.append(tokens)
    groups = collections.defaultdict(list)
    for row in trace:
        groups[row['grp_idx']].append(row)
    trace_counts = {
        'row_count': len(trace), 'width_histogram': histogram(len(x) for x in raw_trace),
        'complete_rows': sum(r['complete'] for r in trace),
        'truncated_tail_rows': malformed_trace_rows,
        'complete_row_phase_counts': histogram(r['phase'] for r in trace if r['complete']),
        'complete_row_has_out_counts': histogram(r['has_out'] for r in trace if r['complete']),
        'count_policy': '1042-style physical row counts include a parseable-prefix truncated final row; missing covariance is never treated as complete',
        'phase_counts': histogram(r['phase'] for r in trace),
        'has_out_counts': histogram(r['has_out'] for r in trace),
        'phase_has_out_counts': histogram(str(r['phase'])+','+str(r['has_out']) for r in trace),
        'idx_is_contiguous_zero_based': [r['idx'] for r in trace] == list(range(len(trace))),
        'invalid_or_unknown_scan_span_count': sum(r['scan_first_ns'] < 0 or r['scan_last_ns'] < r['scan_first_ns'] for r in trace),
        'unknown_scan_first_count': sum(r['scan_first_ns'] < 0 for r in trace),
        'distinct_groups': len(groups),
        'group_multiplicity': duplicates(r['grp_idx'] for r in trace),
        'groups_with_both_live_and_replay': sum({r['phase'] for r in rows} == {0, 1} for rows in groups.values()),
        'groups_with_multiple_live_rows': sum(sum(r['phase'] == 0 for r in rows) > 1 for rows in groups.values()),
        'groups_with_multiple_replay_rows': sum(sum(r['phase'] == 1 for r in rows) > 1 for rows in groups.values()),
        'groups_with_inconsistent_span': sum(len({(r['scan_first_ns'], r['scan_last_ns']) for r in rows}) > 1 for rows in groups.values()),
        'abs_ns_repeats': duplicates(r['abs_ns'] for r in trace),
        'scan_last_ns_repeats': duplicates(r['scan_last_ns'] for r in trace),
    }
    availability = [json.loads(line) for line in gzip.decompress(primary['availability_frames.jsonl.gz']).splitlines() if line.strip()]
    matches = []
    inverse_trace = collections.defaultdict(list)
    inverse_group = collections.defaultdict(list)
    for ordinal, frame in enumerate(availability):
        stamp = frame['scan_stamp_ns']
        all_matches = [r for r in trace if r['scan_first_ns'] <= stamp <= r['scan_last_ns']]
        valid_matches = [r for r in all_matches if r['scan_first_ns'] >= 0]
        unique_groups = sorted({r['grp_idx'] for r in valid_matches})
        for row in valid_matches:
            inverse_trace[row['idx']].append(ordinal)
        for group in unique_groups:
            inverse_group[group].append(ordinal)
        nearest_abs = min(abs(r['abs_ns'] - stamp) for r in trace) if trace else None
        nearest_last = min(abs(r['scan_last_ns'] - stamp) for r in trace) if trace else None
        matches.append({'availability_ordinal': ordinal, 'kf_id': frame.get('kf_id'),
                        'scan_stamp_ns': stamp, 'pose_stamp_ns': frame.get('pose_stamp_ns'),
                        'nis_computed': frame.get('nis', {}).get('computed'),
                        'nis_source': frame.get('nis', {}).get('source'), 'nis_present': frame.get('nis_present'),
                        'literal_inclusive_span_matches': len(all_matches), 'valid_inclusive_span_matches': len(valid_matches),
                        'live_matches': sum(r['phase'] == 0 for r in valid_matches),
                        'replay_matches': sum(r['phase'] == 1 for r in valid_matches),
                        'has_out_matches': sum(r['has_out'] == 1 for r in valid_matches),
                        'unique_group_count': len(unique_groups), 'candidate_groups': unique_groups,
                        'exact_abs_ns_matches': sum(r['abs_ns'] == stamp for r in trace),
                        'exact_scan_last_ns_matches': sum(r['scan_last_ns'] == stamp for r in trace),
                        'nearest_abs_ns_delta': nearest_abs, 'nearest_scan_last_ns_delta': nearest_last,
                        'matches': [{k: r[k] for k in ['idx', 'grp_idx', 'phase', 'has_out', 'abs_ns', 'scan_first_ns', 'scan_last_ns']} for r in valid_matches]})
    availability_counts = {
        'rows': len(availability),
        'run_id_counts': histogram(f.get('run_id') for f in availability),
        'nis_computed_counts': histogram(f.get('nis', {}).get('computed') for f in availability),
        'nis_source_counts': histogram(f.get('nis', {}).get('source') for f in availability),
        'nis_selected_reference_source_counts': histogram(f.get('nis', {}).get('selected_reference_source') for f in availability),
        'nis_present_counts': histogram(f.get('nis_present') for f in availability),
        'scan_stamp_repeats': duplicates(f['scan_stamp_ns'] for f in availability),
        'pose_stamp_repeats': duplicates(f['pose_stamp_ns'] for f in availability),
        'literal_span_match_histogram': histogram(m['literal_inclusive_span_matches'] for m in matches),
        'literal_matching_frames': sum(m['literal_inclusive_span_matches'] > 0 for m in matches),
        'literal_row_ambiguous_frames': sum(m['literal_inclusive_span_matches'] > 1 for m in matches),
        'literal_candidate_edges': sum(m['literal_inclusive_span_matches'] for m in matches),
        'literal_match_count_range': [min(m['literal_inclusive_span_matches'] for m in matches), max(m['literal_inclusive_span_matches'] for m in matches)],
        'literal_many_to_one_trace_row_count_when_all_first_minus_one': sorted(matches, key=lambda m: m['scan_stamp_ns'])[1]['literal_inclusive_span_matches'] if all(r['scan_first_ns'] == -1 for r in trace) and len(availability) > 1 and len({f['scan_stamp_ns'] for f in availability}) == len(availability) else 'UNKNOWN',
        'literal_many_to_one_derivation': 'For all scan_first=-1 and distinct positive scan stamps, literal matched-row sets are nested by scan_stamp. Rows matching the second earliest stamp match at least two availability frames. These are invalid-span arithmetic candidates, not source relations.',
        'valid_span_match_histogram': histogram(m['valid_inclusive_span_matches'] for m in matches),
        'availability_missing_kf_ids_within_zero_to_max': sorted(set(range(max(f['kf_id'] for f in availability)+1)) - {f['kf_id'] for f in availability}),
        'live_match_histogram': histogram(m['live_matches'] for m in matches),
        'replay_match_histogram': histogram(m['replay_matches'] for m in matches),
        'distinct_group_match_histogram': histogram(m['unique_group_count'] for m in matches),
        'matched_frames': sum(m['valid_inclusive_span_matches'] > 0 for m in matches),
        'unmatched_frames': sum(m['valid_inclusive_span_matches'] == 0 for m in matches),
        'row_ambiguous_frames': sum(m['valid_inclusive_span_matches'] > 1 for m in matches),
        'group_ambiguous_frames': sum(m['unique_group_count'] > 1 for m in matches),
        'frames_with_both_live_and_replay_candidates': sum(m['live_matches'] > 0 and m['replay_matches'] > 0 for m in matches),
        'many_to_one_trace_row_count': sum(len(v) > 1 for v in inverse_trace.values()),
        'many_to_one_group_count': sum(len(v) > 1 for v in inverse_group.values()),
        'matched_trace_rows': len(inverse_trace), 'matched_groups': len(inverse_group),
        'trace_row_availability_multiplicity_histogram': histogram(len(v) for v in inverse_trace.values()),
        'group_availability_multiplicity_histogram': histogram(len(v) for v in inverse_group.values()),
        'exact_abs_ns_matching_frames': sum(m['exact_abs_ns_matches'] > 0 for m in matches),
        'exact_scan_last_ns_matching_frames': sum(m['exact_scan_last_ns_matches'] > 0 for m in matches),
        'nearest_scan_last_within_128ns_frames': sum(m['nearest_scan_last_ns_delta'] <= 128 for m in matches),
        'nis_computed_equals_summary': sum(f.get('nis', {}).get('computed') is True for f in availability) == summary.get('nis', {}).get('computed'),
        'rows_equal_summary_paired': len(availability) == summary.get('pairing', {}).get('paired'),
    }

    matrix_rows = {}
    matrix_checks = {}
    def rounded_stamp_matches(token, value):
        number = decimal.Decimal(token)
        half_last_place = decimal.Decimal(10) ** number.as_tuple().exponent / 2
        return abs(number-value) <= half_last_place
    for suffix in ['host_logs/mat_pre.txt', 'host_logs/mat_out.txt']:
        text = primary[suffix].decode('utf-8')
        headers = [line for line in text.splitlines() if line.startswith('#')]
        rows = [line.split() for line in text.splitlines() if line.strip() and not line.startswith('#')]
        matrix_rows[suffix] = rows
        stamps = [r[0] for r in rows]
        filtered_trace = trace if suffix.endswith('mat_pre.txt') else [r for r in trace if r['has_out'] == 1]
        counts_per_stamp = [sum(rounded_stamp_matches(s, r['rel_s']) for r in trace) for s in stamps]
        matrix_checks[suffix] = {
            'rows': len(rows), 'column_count_histogram': histogram(len(r) for r in rows), 'headers': headers,
            'layout_status': 'UNKNOWN: no header; only token widths and first-token candidate stamps checked',
            'first_token_duplicate_counts': duplicates(stamps),
            'first_token_interpreted_only_as_candidate_relative_seconds': True,
            'first_token_matching_trace_rel_s_with_half_last_printed_decimal_place_histogram': histogram(counts_per_stamp),
            'ordinal_comparison_against': 'all trace rows' if suffix.endswith('mat_pre.txt') else 'trace rows with has_out=1',
            'ordinal_comparison_trace_count': len(filtered_trace),
            'ordinal_equal_count': len(rows) == len(filtered_trace),
            'ordinal_stamp_compatible_pairs': sum(rounded_stamp_matches(row[0], tr['rel_s']) for row, tr in zip(rows, filtered_trace)),
            'ordinal_compared_pairs': min(len(rows), len(filtered_trace)),
            'physical_pre_post_identity': 'UNKNOWN: no declared group/idx/phase/source/update identity in these headerless files; count/order/stamp is insufficient',
        }
    pre = matrix_rows['host_logs/mat_pre.txt']
    out = matrix_rows['host_logs/mat_out.txt']
    pre_c = collections.Counter(r[0] for r in pre)
    out_c = collections.Counter(r[0] for r in out)
    matrix_relation = {
        'trace_rows': len(trace), 'trace_distinct_groups': len(groups),
        'trace_has_out_rows': sum(r['has_out'] == 1 for r in trace),
        'mat_pre_rows': len(pre), 'mat_out_rows': len(out),
        'complete_trace_rows': sum(r['complete'] for r in trace),
        'complete_trace_has_out_rows': sum(r['complete'] and r['has_out'] == 1 for r in trace),
        'pre_is_twice_complete_trace_rows': len(pre) == 2 * sum(r['complete'] for r in trace),
        'out_is_twice_complete_has_out_rows': len(out) == 2 * sum(r['complete'] and r['has_out'] == 1 for r in trace),
        'factor_two_count_caveat': '2082=2*1041 and 1948=2*974 are arithmetic observations only; without headers/source identity do not label rows as LIO/VIO or physical paired updates.',
        'pre_equals_all_trace_rows': len(pre) == len(trace),
        'out_equals_has_out_trace_rows': len(out) == sum(r['has_out'] == 1 for r in trace),
        'pre_equals_distinct_groups': len(pre) == len(groups), 'out_equals_distinct_groups': len(out) == len(groups),
        'pre_out_equal_row_counts': len(pre) == len(out),
        'same_first_token_ordinal_pairs': sum(a[0] == b[0] for a, b in zip(pre, out)),
        'first_token_intersection_distinct_count': len(pre_c.keys() & out_c.keys()),
        'possible_exact_stamp_occurrence_pairs_upper_bound': sum(min(pre_c[s], out_c[s]) for s in pre_c.keys() & out_c.keys()),
        'pre_rows_with_any_same_first_token_out': sum(pre_c[s] for s in pre_c.keys() & out_c.keys()),
        'out_rows_with_any_same_first_token_pre': sum(out_c[s] for s in pre_c.keys() & out_c.keys()),
        'physical_pairing_verdict': 'UNKNOWN; same first token can occur multiple times and counts disagree. No ordinal or time-based physical pre/post claim made.',
    }
    precision = {name: precision_stats(r[name] for r in trace) for name in ['abs_ns', 'scan_first_ns', 'scan_last_ns']}
    precision['availability_scan_stamp_ns'] = precision_stats(f['scan_stamp_ns'] for f in availability)
    precision['abs_ns_original_integer_ns_verdict'] = 'Not demonstrated. Binary64 lattice compatibility is checked from values only; origin conversion implementation is outside this task.'
    precision['abs_ns_quantization_evidence'] = ('All nonnegative abs_ns are exactly binary64-representable with 256 ns ULP; values are consistent with double-quantized ns, not arbitrary original integer ns.'
                                               if all(int(float(r['abs_ns'])) == r['abs_ns'] and math.ulp(float(r['abs_ns'])) == 256 for r in trace)
                                               else 'Not uniformly on the 256 ns binary64 lattice; inspect histograms.')
    result = {
        'scope': {'repo': str(repo), 'archive_commit_requested': COMMIT,
                  'archive_commit_resolved': git('rev-parse', COMMIT+'^{commit}').decode().strip(),
                  'origin_exp_trace_cov_at_read': git('rev-parse', 'origin/exp/trace-cov').decode().strip(),
                  'working_tree_head_non_target': git('rev-parse', 'HEAD').decode().strip(),
                  'read_source': 'git show commit:path bytes only; Python -I stdlib reader; no archived code executed',
                  'primary_run': PRIMARY, 'comparison_run': COMPARISON, 'sha_scope': 'requested seven primary files and two comparison files only'},
        'file_checks': files,
        'manifest_unread_out_of_scope_entries': sorted(set(manifest)-set(SUFFIXES)),
        'manifest_caveat': 'SHA256SUMS lists itself; self-entry mismatch is not automatically receipt/summary tampering. Host logs have no SHA manifest binding here; computed digests identify archived bytes only.',
        'identity': {'primary_receipt_run_id': receipt.get('run_id'), 'primary_summary_run_id': summary.get('run_id'),
                     'comparison_receipt_run_id': old_receipt.get('run_id'), 'comparison_summary_run_id': old_summary.get('run_id'),
                     'primary_receipt_summary_run_match': receipt.get('run_id') == summary.get('run_id') == PRIMARY.removeprefix('trace_'),
                     'comparison_receipt_summary_run_match': old_receipt.get('run_id') == old_summary.get('run_id') == COMPARISON.removeprefix('trace_'),
                     'primary_inputs_declared': receipt.get('inputs'), 'comparison_inputs_declared': old_receipt.get('inputs'),
                     'input_declarations_identical': receipt.get('inputs') == old_receipt.get('inputs'),
                     'launch_declarations_identical': receipt.get('launch') == old_receipt.get('launch'),
                     'primary_launch': receipt.get('launch'),
                     'input_actual_bytes_verified': False, 'identity_caveat': 'Receipt binary/library/bag/config/source digests are declarations, not independent external byte verification.'},
        'summary_claims_not_accepted_as_success': {PRIMARY: compact_summary(summary), COMPARISON: compact_summary(old_summary)},
        'trace_layout': {'verbatim_headers': trace_headers, 'declared_field_names': declared,
                         'expanded_zero_based_column_spans_stop_exclusive': spans,
                         'expanded_width': len(columns), 'phase_column_zero_based': columns.index('phase'),
                         'has_out_column_zero_based': columns.index('has_out'),
                         'phase_semantics': 'phase=0 live; phase=1 replay, per archive header',
                         'has_out_semantics': 'has_out=0 before StateEstimation; has_out=1 post available, per archive header'},
        'trace_counts': trace_counts,
        'timestamp_precision': precision,
        'availability_counts': availability_counts,
        'availability_to_trace_rows': matches,
        'many_to_one_trace_rows': [{'trace_idx': k, 'availability_ordinals': v} for k, v in inverse_trace.items() if len(v) > 1],
        'many_to_one_groups': [{'grp_idx': k, 'availability_ordinals': v} for k, v in inverse_group.items() if len(v) > 1],
        'matrix_checks': matrix_checks, 'matrix_relation': matrix_relation,
        'verdicts': {
            'span_contains_proves_source_membership': 'NO: inclusive range is only a necessary candidate test, not an enumerated source membership proof; missing/nonmember stamps may lie between endpoints.',
            'span_contains_proves_same_update': 'NO: live/replay can share group/stamps but have different idx/update; each matching availability may have multiple rows/groups and multiple availability frames may share one row/group.',
            'header_scan_last_join': 'Exact endpoint equality and interval candidates are reported separately; no successful source join inferred from interval containment.',
            'trace_abs_ns_vs_pose_time': 'Not asserted: header says last_lio_update_time/scan end, not an original ROS pose message stamp.',
            'physical_matrix_pre_post': 'UNKNOWN: no sufficient row identities in scoped files; not inferred from order or first-token stamps.',
            'experiment_success': 'NOT_EVALUATED: real bytes/counts and candidate relations only; receipt OK, SUMMARY, and wiring are not success evidence.'}}
    with output.open('x', encoding='utf-8', newline='\n') as stream:
        json.dump(result, stream, indent=2, ensure_ascii=False, allow_nan=False)
        stream.write('\n')
    print(json.dumps({'output': str(output), 'file_checks': files, 'trace_counts': trace_counts,
                      'availability_counts': availability_counts, 'matrix_checks': matrix_checks,
                      'matrix_relation': matrix_relation, 'timestamp_precision': precision}, indent=2))


if __name__ == '__main__':
    main()
