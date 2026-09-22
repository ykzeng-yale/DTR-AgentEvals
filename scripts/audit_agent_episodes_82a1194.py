"""Retrospective saved-artifact checks; no runtime, inference, sampling, or network.

Reads immutable Git blobs at 82a1194. Textually reconstructs the GNU sed append
on archived cat output and parses syntax without executing model-generated code.
"""
import ast
import collections
import hashlib
import json
import re
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
COMMIT = "82a119444b6a2b5fa28b3436e6801095053f000f"
BASE = "results/v2_agent/smoke_episode_20260922"
OUTPUT = ROOT / "docs/audits/episode_diagnosis_82a1194.json"


def git(*args):
    return subprocess.check_output(["git", "-C", str(ROOT), *args])


def read(path):
    return git("show", f"{COMMIT}:{path}")


def main():
    names = git("ls-tree", "-r", "--name-only", COMMIT, BASE).decode().splitlines()
    directories = sorted({str(Path(n).parent) for n in names})
    rows = []
    for directory in directories:
        files = {Path(n).name: read(n) for n in names if str(Path(n).parent) == directory}
        episode = json.loads(files["episode.json"])
        trajectory = json.loads(files["trajectory.json"])
        grade = json.loads(files["grade.json"])
        blob = files["submission.diff"]
        checks = [
            episode["exit_status"] == trajectory["info"]["exit_status"] == grade["exit_status"],
            episode["n_model_calls"] == trajectory["info"]["model_stats"]["api_calls"],
            len(blob) == episode["submission_bytes"] == 0,
            hashlib.sha256(blob).hexdigest() == episode["submission_sha256"] == grade["submission_sha256"],
            grade["evaluated"] is False,
        ]
        assert all(checks), directory
        actions = []
        for index, message in enumerate(trajectory["messages"]):
            if message["role"] != "assistant":
                continue
            commands = re.findall(r"```mswea_bash_command\s*\n(.*?)\n```", message["content"], re.S)
            response = message.get("extra", {}).get("response", {})
            usage = response.get("usage", {})
            next_text = trajectory["messages"][index + 1]["content"]
            rc = re.search(r"<returncode>(.*?)</returncode>", next_text)
            actions.append(dict(message_index=index, commands=commands,
                                returncode=rc.group(1) if rc else None,
                                prompt_tokens=usage.get("prompt_tokens"),
                                completion_tokens=usage.get("completion_tokens"),
                                finish_reasons=[c["finish_reason"] for c in response.get("choices", [])]))
        row = dict(directory=directory, exit_status=episode["exit_status"],
                   calls=episode["n_model_calls"], checks_passed=len(checks),
                   assistant_responses=len(actions), empty_submission=True, evaluated=False,
                   sha256={name: hashlib.sha256(value).hexdigest() for name, value in files.items()},
                   actions=actions)
        if Path(directory).name == "pallets__flask-5014__large":
            source = trajectory["messages"][9]["content"].split("<output>\n", 1)[1].rsplit("</output>", 1)[0]
            ast.parse(source)
            insertion = 'if not name: raise ValueError("Blueprint name cannot be empty")\n'
            mutant = "".join(line + (insertion if "__init__" in line else "")
                             for line in source.splitlines(keepends=True))
            diagnostic = dict(kind="pure textual reconstruction, not container re-execution",
                              source_ast_valid=True,
                              matching_source_lines=[i + 1 for i, line in enumerate(source.splitlines()) if "__init__" in line],
                              repeated_edit_actions=sum(a["commands"] == actions[4]["commands"] for a in actions))
            assert diagnostic["repeated_edit_actions"] == 20
            try:
                ast.parse(mutant)
            except SyntaxError as exc:
                diagnostic.update(single_edit_ast_valid=False, error_line=exc.lineno, error_message=exc.msg)
            else:
                raise AssertionError("Expected reconstructed first edit to be syntactically invalid")
            row["static_diagnostic"] = diagnostic
        rows.append(row)
    report = dict(source_commit=git("rev-parse", COMMIT).decode().strip(),
                  scope="one selected DEVELOPMENT pipeline-smoke task, four non-exchangeable attempts; no benchmark or routing estimate",
                  kind="independent artifact inspection and deterministic textual AST diagnostic; no runtime/model execution",
                  checks_passed=sum(r["checks_passed"] for r in rows), episodes=rows)
    OUTPUT.write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps(dict(output=str(OUTPUT), checks_passed=report["checks_passed"], source_commit=report["source_commit"])))


if __name__ == "__main__":
    main()
