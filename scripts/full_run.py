"""KDNA Lab — Resilient Experiment Runner.

Designed for VPN/proxy environments with:
  - Automatic health check before starting
  - Retry with exponential backoff on every API call
  - Checkpoint after every case (resume on restart)
  - Provider fallback chain
  - Progress reporting with ETA
"""

import os, json, time, sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

# Load all API keys from .env
ENV_PATH = os.path.join(os.path.dirname(__file__), '..', '..', '.env')
if os.path.exists(ENV_PATH):
    with open(ENV_PATH) as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith('#') and '=' in line:
                key, val = line.split('=', 1)
                key = key.strip()
                val = val.strip().strip("'").strip('"')
                if key.endswith('_API_KEY') or key.endswith('_BASE_URL'):
                    os.environ[key] = val

from kdna_lab.domain_runner import DomainRunner
from kdna_lab.cases import load_cases_list
from kdna_lab.checks import check_must_include, check_must_not_include
from kdna_lab.paths import LAB_ROOT
from kdna_lab.evidence_store import EvidenceStore
from kdna_lab.report import generate_l1_report

# === CONFIGURATION ===
import argparse
parser = argparse.ArgumentParser(description='KDNA Lab Resilient Runner')
parser.add_argument('--cases', type=int, default=None, help='Number of cases to run (default: from CASES env or all)')
parser.add_argument('--domain', default=None)
parser.add_argument('--skip-health', action='store_true', help='Skip network health check')
parser.add_argument('--from-checkpoint', action='store_true', help='Resume from last checkpoint')
args = parser.parse_args()

DOMAIN = args.domain or '@aikdna/writing'
MODEL = 'deepseek-v4-pro'
CONDITIONS = ['kdna_full']
CASE_FILE = 'examples/writing/cases.jsonl'
CASES = args.cases or int(os.environ.get('CASES', '0')) or 0  # 0 = all
CHECKPOINT_EVERY = 1

config = {
    'api': {
        'provider': 'openai_compatible',
        'model': 'deepseek/deepseek-v4-pro',
        'base_url': 'https://openrouter.ai/api/v1',
        'api_key_env': 'OPENROUTER_API_KEY',
        'temperature': 0.3,
        'max_tokens': 1500,
        # Fallback: if OpenRouter fails, try DeepSeek directly
        'fallback_providers': [
            {
                'provider': 'openai_compatible',
                'model': 'deepseek-chat',
                'base_url': 'https://api.deepseek.com/v1',
                'api_key_env': 'DEEPSEEK_API_KEY',
            },
        ],
    },
    'domain': {'name': DOMAIN},
    'output': {'dir': 'outputs'},
    'runners': {'domain': {'retries': 5, 'rate_limit': 0.5}},
}

# === INIT ===
runner = DomainRunner(LAB_ROOT, config)
print(f'KDNA Lab — Resilient Runner')
print(f'{"─" * 50}')
print(f'Domain:  {DOMAIN}')
print(f'Model:   {MODEL}')
print(f'Cases:   {CASES if CASES > 0 else "ALL"} (from {CASE_FILE})')
print(f'Run ID:  {runner.run_id}')
print()

# Health check (optional — skip in VPN environments)
if not args.skip_health:
    ok = runner.health_check()
    if not ok:
        print('[WARN] Health check failed — relying on per-call retry')
else:
    print('[SKIP] Health check skipped (--skip-health)')

# Load cases
cases = load_cases_list(CASE_FILE)
if CASES > 0:
    cases = cases[:CASES]

# Load domain
domain_prompt = runner.load_domain_prompt(DOMAIN)
if not domain_prompt:
    print(f'[ERROR] Failed to load domain: {DOMAIN}')
    sys.exit(1)
print(f'Domain prompt: {len(domain_prompt)} chars')

# === RESUME CHECK ===
checkpoint = runner.load_checkpoint()
start_idx = 0
existing_results = []
if checkpoint and checkpoint.get('run_id') == runner.run_id:
    start_idx = checkpoint.get('completed_count', 0)
    existing_results = checkpoint.get('results', [])
    print(f'[RESUME] Continuing from case {start_idx + 1}/{len(cases)}')
elif checkpoint:
    runner.clear_checkpoint()

# === RUN ===
results = list(existing_results)
passed = sum(1 for r in results if r.get('L1_pass'))
total_runs = len(cases) * len(CONDITIONS)
start_time = time.time()

print(f'\nRunning {len(cases)} cases × {len(CONDITIONS)} conditions ...')
print(f'{"─" * 50}')

completed_indices = list(range(start_idx))

for case_idx in range(start_idx, len(cases)):
    case = cases[case_idx]

    for cond in CONDITIONS:
        # Build prompt
        if cond == 'no_kdna':
            prompt = case['input']
        elif cond == 'best_prompt':
            from kdna_lab.domain_runner import BEST_PROMPT_TEMPLATE
            prompt = f"{BEST_PROMPT_TEMPLATE}\n\n[USER INPUT]\n{case['input']}"
        else:
            prompt = runner._build_prompt(domain_prompt, cond, case)

        # Call with retry built-in
        output = runner.call_api(prompt)

        if not output:
            elapsed = time.time() - start_time
            progress = f'{case_idx + 1}/{len(cases)}'
            if case_idx > 0:
                eta = (elapsed / case_idx) * (len(cases) - case_idx)
                progress += f' (ETA {eta:.0f}s)'
            print(f'[{progress}] NET_ERR {case["id"]}')

            results.append({
                'case_id': case['id'], 'L1_pass': False,
                'condition': cond, 'error': 'network_exhausted',
            })

            # Save checkpoint so we can resume
            runner.save_checkpoint(results, list(range(case_idx)))
            continue

        mi_pass, mi = check_must_include(output, case.get('must_include', []))
        mni_pass, mni = check_must_not_include(output, case.get('must_not_include', []))
        l1_pass = mi_pass and mni_pass
        missing = [r['item'] for r in mi if not r['found']]
        violations = [] if mni_pass else mni

        if l1_pass:
            passed += 1

        # Progress
        elapsed = time.time() - start_time
        progress = f'{case_idx + 1}/{len(cases)}'
        if case_idx > 0:
            eta = (elapsed / (case_idx + 1)) * (len(cases) - case_idx - 1)
            progress += f' | {eta:.0f}s left'

        status = 'PASS' if l1_pass else 'FAIL'
        detail = ''
        if missing:
            detail += f' miss:{missing}'
        if violations:
            detail += f' viol:{violations}'

        print(f'[{progress}] {status} {case["id"]}{detail}')

        results.append({
            'case_id': case['id'], 'L1_pass': l1_pass,
            'condition': cond, 'missing': missing, 'violations': violations,
        })

        # Save checkpoint
        if (case_idx + 1) % CHECKPOINT_EVERY == 0:
            completed_indices.append(case_idx)
            runner.save_checkpoint(results, completed_indices)

    time.sleep(0.3)

# === REPORT ===
elapsed = time.time() - start_time
total = len(results)
rate = round(passed / total * 100) if total else 0

print(f'\n{"─" * 50}')
print(f'RESULTS: {passed}/{total} passed ({rate}%)')
print(f'Time:    {elapsed:.0f}s ({elapsed/total:.1f}s per case)')
metrics = runner.network_metrics()
print(f'Network: {metrics["api_calls"]} calls, {metrics["api_failures"]} failures ({metrics["reliability"]}% reliable)')
print()

# Generate L1 report
scores = [{
    'case_id': r['case_id'],
    'score': {'L1': {'passed': r['L1_pass'], 'checks': {
        'must_include': {'missing': r.get('missing', [])},
        'must_not_include': {'violations': r.get('violations', [])},
    }}}
} for r in results]
report_path = generate_l1_report(scores, 'reports/')
print(f'Report:  {report_path}')

# Archive
store = EvidenceStore(LAB_ROOT / 'evidence')
store.ingest_run(
    run_id=runner.run_id, run_type='domain', target=DOMAIN,
    results=results, conditions=CONDITIONS, models=[MODEL],
    extra_meta={'elapsed_s': round(elapsed), 'network': metrics},
)
print(f'Archive: evidence/runs/{runner.run_id}/')

# Clean checkpoint on success
runner.clear_checkpoint()
print(f'\n✅ Experiment complete — {runner.run_id}')
