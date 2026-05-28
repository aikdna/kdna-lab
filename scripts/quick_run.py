"""Quick experiment runner for KDNA Lab."""
import os, json, time, sys

# Load API key
with open(os.path.join(os.path.dirname(__file__), '..', '..', '.env')) as f:
    for line in f:
        if line.startswith('OPENROUTER_API_KEY='):
            os.environ['OPENROUTER_API_KEY'] = line.split('=',1)[1].strip()
            break

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from kdna_lab.domain_runner import DomainRunner
from kdna_lab.cases import load_cases_list
from kdna_lab.checks import check_must_include, check_must_not_include
from kdna_lab.paths import LAB_ROOT
from kdna_lab.evidence_store import EvidenceStore

config = {
    'api': {'provider': 'openai_compatible', 'model': 'deepseek/deepseek-v4-pro',
            'base_url': 'https://openrouter.ai/api/v1', 'api_key_env': 'OPENROUTER_API_KEY',
            'temperature': 0.3, 'max_tokens': 1500},
    'domain': {'name': '@aikdna/writing'},
    'output': {'dir': 'outputs'},
    'runners': {'domain': {'rate_limit': 0.5}},
}

runner = DomainRunner(LAB_ROOT, config)
domain_prompt = runner.load_domain_prompt('@aikdna/writing')

cases = load_cases_list('examples/writing/cases.jsonl')[:3]
passed = 0

for i, case in enumerate(cases):
    prompt = runner._build_prompt(domain_prompt, 'kdna_full', case)
    
    output = None
    for attempt in range(3):
        output = runner.call_api(prompt)
        if output: break
        time.sleep(2)
    
    if not output:
        print(f'[{i+1}/3] {case["id"]} NETWORK FAIL')
        continue
    
    mi_pass, mi = check_must_include(output, case.get('must_include', []))
    mni_pass, mni = check_must_not_include(output, case.get('must_not_include', []))
    l1_pass = mi_pass and mni_pass
    missing = [r['item'] for r in mi if not r['found']]
    
    if l1_pass: passed += 1
    status = 'PASS' if l1_pass else 'FAIL'
    extra = ''
    if missing: extra += ' miss:' + str(missing)
    if mni: extra += ' viol:' + str(mni)
    print(f'[{i+1}/3] {status} {case["id"]}{extra}')
    time.sleep(0.5)

print(f'\n{passed}/{len(cases)} passed')
