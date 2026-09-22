"""DTR-REQ-002: Docker Runtime binding for control_adapter (lead 7f9673a / bae161f). Authorized by the author on 2026-09-22.

Runs ONLY in the isolated venv work/venvs/swebench_f7bbbb2 against the approved runtime (here: Colima arm64 VM with
Rosetta-translated amd64 containers). It mirrors the pinned f7bbbb2 run_instance sequence step for step, reusing the
harness's own helpers and constants so that reference mode differs from the stock path only in who orchestrates it:
  container   client.containers.create(image, user=DOCKER_USER, detach=True, command="tail -f /dev/null",
              platform=test_spec.platform) and start (docker_build.build_container L516-L523)
  patch       copy_to_container(patch -> DOCKER_PATCH), then GIT_APPLY_CMDS in order with workdir=DOCKER_WORKDIR,
              user=DOCKER_USER, first exit 0 wins (run_evaluation L158-L184)
  eval        copy eval.sh -> /eval.sh, exec_run_with_timeout(container, "/bin/bash /eval.sh", timeout); on timeout the
              harness appends "Timeout error" to the log (L203-L214)
  repo state  `git -c core.fileMode=false diff` in DOCKER_WORKDIR (the harness's before/after diff, L188-L227) + HEAD
The pinned helper returns no exit code, so exit_code is recorded as None. Raw logs are kept in `self.logs`.
"""
from __future__ import annotations
import hashlib, tempfile
from pathlib import Path, PurePosixPath

import control_adapter as A


class DockerRuntime(A.Runtime):
    def __init__(self, client, test_spec, name_prefix):
        from swebench.harness.run_evaluation import DOCKER_PATCH, DOCKER_USER, DOCKER_WORKDIR, GIT_APPLY_CMDS
        self.client, self.ts, self.prefix, self.n = client, test_spec, name_prefix, 0
        self.PATCH, self.USER, self.WORKDIR, self.APPLY = DOCKER_PATCH, DOCKER_USER, DOCKER_WORKDIR, GIT_APPLY_CMDS
        self.logs, self.events = [], []

    def start(self, image_digest):
        self.n += 1
        img = self.client.images.get(image_digest)                       # refuses an image that is not the pinned one
        c = self.client.containers.create(img.id, name='%s-%d' % (self.prefix, self.n), user=self.USER, detach=True,
                                          command='tail -f /dev/null', platform=self.ts.platform)
        c.start()
        self.events.append(('start', c.id, img.id))
        return c

    def repo_state(self, c):
        diff = c.exec_run('git -c core.fileMode=false diff', workdir=self.WORKDIR).output.decode('utf-8', 'replace').strip()
        head = c.exec_run('git rev-parse HEAD', workdir=self.WORKDIR).output.decode('utf-8', 'replace').strip()
        return dict(head=head, diff_sha256=hashlib.sha256(diff.encode()).hexdigest(), diff_bytes=len(diff))

    def apply_patch(self, c, patch_text):
        from swebench.harness.docker_utils import copy_to_container
        with tempfile.TemporaryDirectory() as tmp:
            pf = Path(tmp) / 'patch.diff'
            pf.write_text(patch_text or '')
            copy_to_container(c, pf, PurePosixPath(self.PATCH))
        out = ''
        for cmd in self.APPLY:
            val = c.exec_run('%s %s' % (cmd, self.PATCH), workdir=self.WORKDIR, user=self.USER)
            out = val.output.decode('utf-8', 'replace')
            if val.exit_code == 0:
                self.events.append(('apply_patch', cmd, 0))
                return True, out
            self.events.append(('apply_patch', cmd, val.exit_code))
        return False, out

    def run_eval_script(self, c, script_text, timeout):
        from swebench.harness.docker_utils import copy_to_container, exec_run_with_timeout
        with tempfile.TemporaryDirectory() as tmp:
            ef = Path(tmp) / 'eval.sh'
            ef.write_text(script_text)
            copy_to_container(c, ef, PurePosixPath('/eval.sh'))
        out, timed_out, runtime = exec_run_with_timeout(c, '/bin/bash /eval.sh', timeout)
        if timed_out:
            out += '\n\nTimeout error: %d seconds exceeded.' % timeout
        self.logs.append(dict(call=self.n, text=out, timed_out=timed_out, runtime_seconds=runtime))
        return None, out, timed_out

    def stop(self, c):
        try:
            c.stop(timeout=15)
        finally:
            c.remove(force=True)
        self.events.append(('stop', c.id))


def parser_binding(test_spec):
    """The pinned get_logs_eval as the adapter's parser: (statuses, completion_ok, note). found=False (bad-code or missing
    test-output markers) means completion is NOT valid even if some lines would parse."""
    from swebench.harness.grading import get_logs_eval

    def parse(log_text):
        with tempfile.TemporaryDirectory() as tmp:
            fp = Path(tmp) / 'test_output.txt'
            fp.write_text(log_text)
            sm, found = get_logs_eval(test_spec, str(fp))
        return (sm or None), bool(found), 'get_logs_eval found=%s' % found
    return parse
