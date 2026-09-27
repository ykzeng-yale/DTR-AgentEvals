import tempfile
import unittest
from pathlib import Path
from exposure_local_runs import selected_paths


class SelectionTests(unittest.TestCase):
    def test_tracked_independence_and_exclusions(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            wanted = ['results/v2_agent/pilot/a/trajectory.json',
                      'results/v2_agent/pilot/a/receipts/001.request.json',
                      'results/remote_req028/c6_runtime/run/controller/role/request/01.json']
            excluded = ['results/v2_agent/confirm/a/trajectory.json',
                        'results/v2_agent/pilot/evaluator.json',
                        'results/remote_req028/c6_runtime/run/controller/git-cache/trajectory.json',
                        'results/local_req029/reference_runtime/reference.json',
                        'results/code_routing/trajectory.json']
            for name in wanted + excluded:
                p = root / name
                p.parent.mkdir(parents=True, exist_ok=True)
                p.write_text('{}')
            self.assertEqual([str(p.relative_to(root)) for p in selected_paths(root)], sorted(wanted))


if __name__ == '__main__':
    unittest.main()
