"""Full pipeline experiment runner."""
import os, json, time, sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

with open(os.path.join(os.path.dirname(__file__), '..', '..', '.env')) as f:
    for line in f:
        if line.startswith('OPENROUTER_API_KEY='):
            os.environ['OPENROUTER_API_KEY'] = line.split('=',1)[1].strip()
            break

from kdna_lab.domain_runner import DomainRunner
from kdna_lab.cases import load_cases_list
from kdna_lab.checks import check_must_include, check_must_not_include
from kdna_lab.paths import LAB_ROOT
from kdna_lab.evidence_store import EvidenceStore
from kdna_lab.report import generate_l1_report

CASES = 8
DOMAIN = '@aikdna/writing'
MODEL = 'deepseek-v4-pro'
CONDITION = 'kdna_full'
CASE_FILE = f'examples/writing/cases.jsonl'

config = {
    'api': {'provider': 'openai_compatible', 'model': 'deepseek/deepseek-v4-pro',
            'base_url': 'https://openrouter.ai/api/v1', 'api_key_env': 'OPENROUTER_API_KEY',
            'temperature': 0.3, 'max_tokens': 1500},
    'domain': {'name': DOMAIN},
    'output': {'dir': 'outputs'},
    'runners': {'domain': {'rate_limit': 0.5}},
}

runner = DomainRunner(LAB_ROOT, config)
domain_prompt = runner.load_domain_prompt(DOMAIN)
print(f'Domain: {DOMAIN} ({len(domain_prompt)} chars)')
print(f'Model: {MODEL}')
print(f'Cases: {CASES}')
print()

cases = load_cases_list(CASE_FILE)[:CASES]
results = []
passed = 0

for i, case in enumerate(cases):
    prompt = runner._build_prompt(domain_prompt, CONDITION, case)
    
    output = None
    for attempt in range(3):
        output = runner.call_api(prompt)
        if output: break
        time.sleep(2)
    
    if not output:
        print(f'[{i+1}/{CASES}] NET_ERR {case["id"]}')
        results.append({'case_id': case['id'], 'L1_pass': False, 'error': 'network'})
        continue
    
    mi_pass, mi = check_must_include(output, case.get('must_include', []))
    mni_pass, mni = check_must_not_include(output, case.get('must_not_include', []))
    l1_pass = mi_pass and mni_pass
    missing = [r['item'] for r in mi if not r['found']]
    violations = [] if mni_pass else mni
    
    if l1_pass: passed += 1
    
    extra = ''
    if missing: extra += f' miss:{missing}'
    if violations: extra += f' viol:{violations}'
    status = 'PASS' if l1_pass else 'FAIL'
    print(f'[{i+1}/{CASES}] {status} {case["id"]}{extra}')
    
    results.append({
        'case_id': case['id'], 'L1_pass': l1_pass,
        'missing': missing, 'violations': violations,
        'condition': CONDITION,
    })
    
    time.sleep(0.3)

print(f'\n{passed}/{CASES} passed ({round(passed/CASES*100)}%)')

# Generate report
scores = [{'case_id': r['case_id'], 'score': {'L1': {'passed': r['L1_pass'], 'checks': {
    'must_include': {'missing': r.get('missing', [])},
    'must_not_include': {'violations': r.get('violations', [])},
}}}} for r in results]
report_path = generate_l1_report(scores, 'reports/')
print(f'Report: {report_path}')

# Archive
store = EvidenceStore(LAB_ROOT / 'evidence')
store.ingest_run(run_id=runner.run_id, run_type='domain', target=DOMAIN, results=results,
                 conditions=[CONDITION], models=[MODEL])
print(f'Archived: {runner.run_id}')
