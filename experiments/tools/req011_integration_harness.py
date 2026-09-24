"""Pinned-venv harness for tests/test_req011_pair.py (DTR-REQ-011 entry fixtures). It runs req011_entry.main() of this
checkout, unmodified, against in-process stand-ins, and records what reached the stub sender. It asserts nothing.

    work/venvs/minisweagent_04d809c/bin/python experiments/tools/req011_integration_harness.py <config.json>

Stand-ins follow experiments/tools/v2_cue_integration_harness.py (not edited, not imported):
  * httpx.HTTPTransport.handle_request is a scripted sender that records every body and answers by arrival order; an
    entry {"sleep": s} blocks inside the send, so the episode's own SIGALRM deadline fires mid-inference;
  * a tripwire refuses and records any socket connect or DNS lookup;
  * requests.get answers the /props lookup; shutil.disk_usage reports reserve + 7 GiB free;
  * `docker` is the scenario's fake executable under its own HOME (commands run in a disposable Git repository);
  * cue_admission.ROOT points at a disposable root, so private receipts never enter the checkout.
LITELLM_LOCAL_MODEL_COST_MAP is set only while litellm is imported, then removed: the entry refuses any LITELLM_*
variable. The heavy imports happen before the episode deadline is computed, so the deadline measures the episode.
"""
import json
import os
import socket
import sys
import time
from pathlib import Path

CONFIG = json.loads(Path(sys.argv[1]).read_text())
OUT = Path(CONFIG['out'])
(OUT / 'terminal').mkdir(parents=True, exist_ok=True)
NETWORK_ATTEMPTS = []


def _tripwire(name):
    def deny(*_a, **_k):
        NETWORK_ATTEMPTS.append(name)
        raise OSError('req011 fixture network tripwire: %s refused' % name)
    return deny


socket.socket.connect = _tripwire('socket.connect')
socket.socket.connect_ex = _tripwire('socket.connect_ex')
socket.create_connection = _tripwire('socket.create_connection')
socket.getaddrinfo = _tripwire('socket.getaddrinfo')

import shutil  # noqa: E402

import httpx  # noqa: E402
import requests  # noqa: E402

RECEIVED = []
SCRIPT = list(CONFIG['script'])
GiB = 1024 ** 3


def terminal(self, request):
    body = b''.join(request.stream)
    RECEIVED.append(dict(number=len(RECEIVED) + 1, bytes=len(body), url=str(request.url)))
    (OUT / 'terminal' / ('%03d.body' % len(RECEIVED))).write_bytes(body)
    entry = SCRIPT.pop(0) if SCRIPT else dict(content='THOUGHT: exhausted\n\n```mswea_bash_command\necho x\n```')
    if entry.get('sleep'):
        time.sleep(entry['sleep'])
    if entry.get('status', 200) != 200:
        payload = {'error': {'code': entry['status'], 'message': 'fixture canned error', 'type': 'server_error'}}
        return httpx.Response(entry['status'], content=json.dumps(payload).encode(),
                              headers={'content-type': 'application/json'}, request=request)
    payload = {'id': 'chatcmpl-req011-%d' % len(RECEIVED), 'object': 'chat.completion', 'created': 1790000000,
               'model': CONFIG['alias'], 'choices': [{'index': 0, 'finish_reason': 'stop', 'message': {
                   'role': 'assistant', 'content': entry['content']}}],
               'usage': {'prompt_tokens': 100 + len(RECEIVED), 'completion_tokens': 10,
                         'total_tokens': 110 + len(RECEIVED)}}
    return httpx.Response(200, content=json.dumps(payload).encode(), headers={'content-type': 'application/json'},
                          request=request)


httpx.HTTPTransport.handle_request = terminal


class _Props:
    def json(self):
        return {'total_slots': 1, 'default_generation_settings': {'n_ctx': 16384},
                'model_path': '/models/' + CONFIG['model_file']}


def props(url, timeout=None):
    if not url.endswith('/props'):
        raise AssertionError('unexpected GET %s' % url)
    return _Props()


requests.get = props
shutil.disk_usage = lambda path: shutil._ntuple_diskusage(16 * GiB, 8 * GiB, 8 * GiB)


def run():
    sys.path.insert(0, CONFIG['module_dir'])
    import req011_entry as E                       # imports cue_episode first (MSWEA_* before minisweagent)
    E.A.ROOT = Path(CONFIG['layout_root'])
    import litellm  # noqa: F401
    import pandas  # noqa: F401
    import yaml  # noqa: F401
    from minisweagent.agents.default import DefaultAgent  # noqa: F401
    from minisweagent.environments.docker import DockerEnvironment  # noqa: F401
    from minisweagent.models.litellm_textbased_model import LitellmTextbasedModel  # noqa: F401
    os.environ.pop('LITELLM_LOCAL_MODEL_COST_MAP', None)
    control = CONFIG['control']
    now = time.time()
    control['namespace'].update(episode_deadline=now + CONFIG['deadline_in'], block_deadline=now + 3000.0)
    path = Path(CONFIG['control_path'])
    path.write_text(json.dumps(control))
    try:
        return E.main([str(path)])
    except BaseException as e:  # noqa: BLE001  recorded, never hidden
        return dict(raised=type(e).__name__, detail=str(e)[:300])


if __name__ == '__main__':
    code = run()
    (OUT / 'harness.json').write_text(json.dumps(dict(exit_code=code, received=RECEIVED,
                                                      network_attempts=NETWORK_ATTEMPTS, script_left=len(SCRIPT)),
                                                 indent=1) + '\n')
    sys.exit(0)
