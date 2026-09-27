"""Evaluator-only public dataset projection; never imported by model prompt code."""
import ast,hashlib,json,re,shutil
from pathlib import Path
import pyarrow.parquet as pq
ROOT=Path(__file__).resolve().parents[2]
def sha(b):return hashlib.sha256(b).hexdigest()
def build():
    prior=ROOT/'docs/source_snapshots/req029i_django';pins=json.loads((prior/'manifest.json').read_bytes())
    assert sha((prior/'manifest.json').read_bytes())=='41207b50e9fbec3ac59e2642a2cecee79ce367c9558635b48cb752ee9d32da17'
    sources=['LICENSE','constants.py.txt','constants_python.py.txt','grading.py.txt','log_parsers.py.txt','python_parser.py.txt','strict_rule.py.txt','test_spec_python.py.txt']
    for name in sources:assert sha((prior/name).read_bytes())==pins[name]
    dataset=ROOT/'work/benchmark_inputs/swebench_verified_c104f840/test-00000-of-00001.parquet'
    digest=hashlib.file_digest(dataset.open('rb'),'sha256').hexdigest()
    assert digest=='a45b1fe4e2f0c8390b2b2938ac83e92ed5979000856808f3679c07812e9e6dcd'
    columns=['instance_id','repo','version','base_commit','test_patch','patch','FAIL_TO_PASS','PASS_TO_PASS']
    rows=pq.read_table(dataset,columns=columns,filters=[('instance_id','=','matplotlib__matplotlib-20826')]).to_pylist();assert len(rows)==1
    d=rows[0];reference=d.pop('patch').encode()
    for k in ('FAIL_TO_PASS','PASS_TO_PASS'):d[k]=json.loads(d[k]) if isinstance(d[k],str) else d[k]
    assert len(set(d['FAIL_TO_PASS']+d['PASS_TO_PASS']))==len(d['FAIL_TO_PASS'])+len(d['PASS_TO_PASS'])
    assert d['base_commit']=='a0d2e399729d36499a1924e5ca5bc067c8396810' and d['repo']=='matplotlib/matplotlib'
    ns={'SWEbenchInstance':dict,'re':re}
    for n in ast.parse((prior/'constants.py.txt').read_text()).body:
        if isinstance(n,ast.Assign):
            try:v=ast.literal_eval(n.value)
            except (ValueError,TypeError):continue
            for t in n.targets:
                if isinstance(t,ast.Name):ns[t.id]=v
    exec(compile((prior/'constants_python.py.txt').read_text(),'pinned-python-constants','exec'),ns)
    ns['MAP_REPO_VERSION_TO_SPECS']=ns['MAP_REPO_VERSION_TO_SPECS_PY']
    # This exact patch modifies existing paths only; reject /dev/null before simplified extraction.
    assert '/dev/null' not in d['test_patch']
    ns['get_modified_files']=lambda patch:re.findall(r'^--- a/(.+)$',patch,re.M)
    ns['get_new_files']=lambda patch:[]
    tree=ast.parse((prior/'test_spec_python.py.txt').read_text());nodes=[n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name in ('get_test_directives','make_eval_script_list_py')]
    exec(compile(ast.Module(body=nodes,type_ignores=[]),'pinned-command-generation','exec'),ns)
    spec=ns['MAP_REPO_VERSION_TO_SPECS'][d['repo']][d['version']]
    command=' '.join([spec['test_cmd'],*ns['get_test_directives'](d)])
    commands=ns['make_eval_script_list_py'](d,spec,'testbed','/testbed',d['base_commit'],d['test_patch'])
    assert command in commands
    d.update(test_command=command,install_command=spec.get('install'),eval_commands=spec.get('eval_commands',[]),stock_eval_script='#!/bin/bash\nset -uxo pipefail\n'+'\n'.join(commands)+'\n')
    out=ROOT/'docs/source_snapshots/req029w_matplotlib_eval';out.mkdir(exist_ok=False)
    for name in sources:shutil.copyfile(prior/name,out/name)
    (out/'reference.diff').write_bytes(reference);(out/'evaluation_inputs.json').write_text(json.dumps(d,indent=2)+'\n')
    provenance=dict(dataset_sha256=digest,columns=columns,upstream_revision='f7bbbb2ccdf479001d6467c9e34af59e44a840f9',source_bundle_sha256=sha((prior/'manifest.json').read_bytes()),public_prompt_boundary='Evaluator-only bundle; no contents passed to a model',execution_authorized=False,source_sha256=sha(Path(__file__).read_bytes()))
    (out/'provenance.json').write_text(json.dumps(provenance,indent=2)+'\n')
    manifest={p.name:sha(p.read_bytes()) for p in sorted(out.iterdir())};(out/'manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
    print(json.dumps(dict(version=d['version'],f2p=len(d['FAIL_TO_PASS']),p2p=len(d['PASS_TO_PASS']),command=command,omitted_install=d['install_command'],eval_commands=d['eval_commands'],reference_bytes=len(reference),test_patch_bytes=len(d['test_patch'].encode()),manifest_sha256=sha((out/'manifest.json').read_bytes()))))
if __name__=='__main__':build()
