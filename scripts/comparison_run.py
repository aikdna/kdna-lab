"""KDNA Lab — Three-Condition Experiment: no_kdna / best_prompt / kdna_full."""
import os, json, time, sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

# Load env
with open(os.path.join(os.path.dirname(__file__), '..', '..', '.env')) as f:
    for line in f:
        if line.startswith('OPENROUTER_API_KEY='):
            os.environ['OPENROUTER_API_KEY'] = line.split('=',1)[1].strip()
            break

from kdna_lab.domain_runner import DomainRunner, BEST_PROMPT_TEMPLATE
from kdna_lab.cases import load_cases_list
from kdna_lab.checks import check_must_include, check_must_not_include
from kdna_lab.paths import LAB_ROOT
from kdna_lab.evidence_store import EvidenceStore
from kdna_lab.report import generate_comparison_report

CASES = 30
MODEL = 'deepseek-v4-pro'
DOMAIN = '@aikdna/writing'
CONDITIONS_TO_RUN = ['no_kdna', 'best_prompt']  # kdna_full already done

config = {
    'api': {'provider': 'openai_compatible', 'model': 'deepseek/deepseek-v4-pro',
            'base_url': 'https://openrouter.ai/api/v1', 'api_key_env': 'OPENROUTER_API_KEY',
            'temperature': 0.3, 'max_tokens': 1500},
    'domain': {'name': DOMAIN},
    'output': {'dir': 'outputs'},
    'runners': {'domain': {'retries': 5, 'rate_limit': 0.3}},
}

runner = DomainRunner(LAB_ROOT, config)
domain_prompt = runner.load_domain_prompt(DOMAIN)
cases = load_cases_list('examples/writing/cases.jsonl')[:CASES]

# Load existing kdna_full results
existing = json.load(open('outputs/run_20260529_101408_checkpoint.json'))
all_results = list(existing['results'])
print(f'Loaded {len(all_results)} existing kdna_full results')

start_time = time.time()
total_to_run = len(cases) * len(CONDITIONS_TO_RUN)
completed = 0

for cond in CONDITIONS_TO_RUN:
    print(f'\n{"="*50}')
    print(f'Condition: {cond}')
    print(f'{"="*50}')
    
    for i, case in enumerate(cases):
        if cond == 'no_kdna':
            prompt = case['input']
        else:
            prompt = f"{BEST_PROMPT_TEMPLATE}\n\n[USER INPUT]\n{case['input']}"
        
        sys.stdout.write(f'[{i+1}/{CASES}] {case["id"]} ... ')
        sys.stdout.flush()
        
        output = runner.call_api(prompt)
        
        if not output:
            print('NET_ERR')
            all_results.append({'case_id': case['id'], 'condition': cond, 'L1_pass': False, 'error': 'network'})
            json.dump({'results': all_results}, open(f'outputs/comparison_ckpt.json', 'w'), indent=2)
            continue
        
        mi_pass, mi = check_must_include(output, case.get('must_include', []))
        mni_pass, mni = check_must_not_include(output, case.get('must_not_include', []))
        l1_pass = mi_pass and mni_pass
        missing = [r['item'] for r in mi if not r['found']]
        violations = [] if mni_pass else mni
        
        status = 'PASS' if l1_pass else 'FAIL'
        detail = ''
        if missing: detail += f' miss:{len(missing)}'
        if violations: detail += f' viol:{len(violations)}'
        print(f'{status}{detail}')
        
        all_results.append({
            'case_id': case['id'], 'condition': cond, 'L1_pass': l1_pass,
            'missing': missing, 'violations': violations,
        })
        
        # Save after each case
        json.dump({'results': all_results}, open(f'outputs/comparison_ckpt.json', 'w'), indent=2, ensure_ascii=False)
        
        completed += 1
        elapsed = time.time() - start_time
        eta = (elapsed / completed) * (total_to_run - completed) if completed > 0 else 0
        time.sleep(0.3)

# Generate comparison report
elapsed = time.time() - start_time
print(f'\n{"="*50}')
print(f'All {total_to_run} calls completed in {elapsed:.0f}s')

report_path = str(LAB_ROOT / 'reports' / 'comparison_writing_3c.md')
generate_comparison_report(all_results, report_path)
print(f'Report: {report_path}')

# Archive
store = EvidenceStore(LAB_ROOT / 'evidence')
store.ingest_run(run_id=runner.run_id, run_type='domain', target=DOMAIN,
                 results=all_results, conditions=['no_kdna', 'best_prompt', 'kdna_full'],
                 models=[MODEL])
print(f'Archived: {runner.run_id}')
