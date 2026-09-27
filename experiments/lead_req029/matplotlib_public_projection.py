import hashlib,json
from pathlib import Path
import pyarrow.parquet as pq
p=Path('work/benchmark_inputs/swebench_verified_c104f840/test-00000-of-00001.parquet')
h=hashlib.file_digest(p.open('rb'),'sha256').hexdigest()
assert h=='a45b1fe4e2f0c8390b2b2938ac83e92ed5979000856808f3679c07812e9e6dcd'
cols=['instance_id','base_commit','problem_statement']
rows=pq.read_table(p,columns=cols,filters=[('instance_id','=','matplotlib__matplotlib-20826')]).to_pylist()
assert len(rows)==1 and set(rows[0])==set(cols)
out=Path('docs/source_snapshots/req029s_public');out.mkdir(exist_ok=False)
raw=(json.dumps(rows[0],ensure_ascii=False,indent=2)+'\n').encode()
(out/'public_task.json').write_bytes(raw)
(out/'provenance.json').write_text(json.dumps(dict(dataset_sha256=h,columns=cols,task_sha256=hashlib.sha256(raw).hexdigest(),model_dispatched=False,scope='Projected public columns only; no hints, reference patch, test patch or evaluator statuses read.'),indent=2)+'\n')
print(hashlib.sha256(raw).hexdigest())
