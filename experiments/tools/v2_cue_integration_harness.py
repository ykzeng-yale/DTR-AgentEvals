"""Pinned-venv harness for experiments/tools/test_v2_cue_integration.py (DTR-REQ-005 cue-v1 acceptance fixtures).

    work/venvs/minisweagent_04d809c/bin/python experiments/tools/v2_cue_integration_harness.py <config.json>

It runs ONE episode driver, unmodified, and records what reached the (stub) sender. It asserts nothing.

  mode "frozen"  the frozen yaml-v1 driver: experiments/v2_agent/pilot_episode.py of THIS checkout, main() itself
  mode "cue"     the cue-v1 driver of a disposable tree: <tree>/experiments/v2_agent/cue_episode.py, main() itself

Both drivers run their real code paths (mini-swe-agent 04d809c DefaultAgent + LitellmTextbasedModel + the pinned
DockerEnvironment, litellm 1.102.0 -> openai 2.54.0 -> httpx 0.28.1). Only these in-process stand-ins exist:

  * the SENDER: httpx.HTTPTransport.handle_request is replaced, at the class, by a scripted terminal that records the
    exact body bytes and headers it receives (terminal/NNN.body, terminal.jsonl) and answers from the scenario
    script by arrival order. The frozen driver reaches it through litellm's own default client; the cue driver
    through cue_transport's capture wrapping a real httpx.HTTPTransport. No socket is opened: a tripwire refuses and
    records any connect or DNS lookup.
  * the llama-server /props lookup (requests.get) returns a fixed props object.
  * `docker` is a fake executable under the scenario's own HOME (pilot_episode.DOCKER is ~/.local/dtr-runtime/bin/
    docker): it starts no container, answers `image inspect`/`run`/`stop`/`container inspect`/`rm`, and runs `exec`
    commands in a disposable Git repository the test created (with /testbed rewritten to that path). The commands
    are the scenario's own scripted fixture commands and the frozen capture commands, never benchmark-generated code.
  * shutil.disk_usage reports a fixed free space, switched to a low value after a given number of sends when a
    scenario asks for a storage refusal.
  * a scenario may make one send raise KeyboardInterrupt (an operator abort) to show the terminal phase still runs.

LITELLM_LOCAL_MODEL_COST_MAP is set so litellm fetches no remote cost map.
"""
import json
import socket
import sys
from pathlib import Path

CONFIG = json.loads(Path(sys.argv[1]).read_text())
OUT = Path(CONFIG['out'])
(OUT / 'terminal').mkdir(parents=True, exist_ok=True)
NETWORK_ATTEMPTS = []


def _tripwire(name):
    def deny(*_a, **_k):
        NETWORK_ATTEMPTS.append(name)
        raise OSError('cue integration fixture network tripwire: %s refused' % name)
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
DISK = CONFIG.get('disk') or {}
GiB = 1024 ** 3


def answer(entry):
    if entry.get('status', 200) == 200:
        body = {'id': 'chatcmpl-fixture-%d' % len(RECEIVED), 'object': 'chat.completion', 'created': 1790000000,
                'model': CONFIG['alias'],
                'choices': [{'index': 0, 'finish_reason': 'stop',
                             'message': {'role': 'assistant', 'content': entry['content']}}],
                'usage': {'prompt_tokens': 100 + len(RECEIVED), 'completion_tokens': 10, 'total_tokens':
                          110 + len(RECEIVED)}}
        return 200, body
    if entry.get('kind') == 'context':
        return 400, {'error': {'code': 400, 'type': 'exceed_context_size_error', 'n_prompt_tokens': 16610,
                               'n_ctx': 16384, 'message': 'request (16610 tokens) exceeds the available context '
                                                          'size (16384 tokens), try increasing it'}}
    return entry['status'], {'error': {'code': entry['status'], 'message': 'fixture canned error',
                                       'type': 'server_error'}}


def terminal(self, request):
    body = b''.join(request.stream)
    number = len(RECEIVED) + 1
    (OUT / 'terminal' / ('%03d.body' % number)).write_bytes(body)
    RECEIVED.append(dict(number=number, transport=type(self).__name__, url=str(request.url), bytes=len(body),
                         headers=sorted([k.lower(), '<redacted>' if k.lower() == 'authorization' else v]
                                        for k, v in request.headers.multi_items()),
                         timeout=request.extensions.get('timeout')))
    entry = SCRIPT.pop(0) if SCRIPT else dict(content='THOUGHT: script exhausted\n\n'
                                                      '```mswea_bash_command\necho exhausted\n```')
    if entry.get('raise') == 'KeyboardInterrupt':
        raise KeyboardInterrupt('fixture operator abort inside the send')
    status, payload = answer(entry)
    return httpx.Response(status, content=json.dumps(payload).encode(), headers={'content-type': 'application/json'},
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
_DISK_CALLS = []


def disk_usage(path):
    _DISK_CALLS.append(str(path))
    reserve = DISK.get('reserve', GiB)
    low = len(_DISK_CALLS) > 2 and DISK.get('low_after_sends') is not None and \
        len(RECEIVED) >= DISK['low_after_sends']
    free = reserve + (64 * 1024 if low else 7 * GiB)
    return shutil._ntuple_diskusage(free * 2, free, free)


shutil.disk_usage = disk_usage


def run():
    argv = CONFIG['argv']
    if CONFIG['mode'] == 'frozen':
        sys.path.insert(0, CONFIG['frozen_module_dir'])
        import pilot_episode as PE
        sys.argv = ['pilot_episode.py'] + argv
        try:
            PE.main()
            return 0
        except SystemExit as e:  # noqa: BLE001  recorded, never hidden
            return e.code if isinstance(e.code, int) else 1
    sys.path.insert(0, CONFIG['module_dir'])
    import cue_episode as E
    if CONFIG.get('call_run_assignment'):
        try:
            E.run_assignment(dict(assignment_id='fixture-row'), {})
        except E.LiveReleaseHeld as e:
            return dict(live_release_held=str(e))
    try:
        return E.main(argv)
    except KeyboardInterrupt as e:                 # re-raised by the driver only after its terminal phase
        return dict(raised=type(e).__name__, detail=str(e))


if __name__ == '__main__':
    code = run()
    (OUT / 'terminal.jsonl').write_text(''.join(json.dumps(r, sort_keys=True) + '\n' for r in RECEIVED))
    (OUT / 'harness.json').write_text(json.dumps(dict(
        mode=CONFIG['mode'], exit_code=code, received=len(RECEIVED), network_attempts=NETWORK_ATTEMPTS,
        disk_probes=len(_DISK_CALLS), script_left=len(SCRIPT),
        versions={p: __import__('importlib.metadata').metadata.version(p)
                  for p in ('litellm', 'openai', 'httpx', 'tenacity', 'mini-swe-agent')}), indent=1) + '\n')
    sys.exit(0)
