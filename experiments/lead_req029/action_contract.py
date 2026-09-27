"""Prospective source-only text action contract; never executes command content."""
import re,sys
from pathlib import Path
FROZEN=Path(__file__).resolve().parents[1]/'remote_req028'
sys.path.insert(0,str(FROZEN))
from b4_protocol import parser_binding,REGEX
CONTRACT='req029d-upstream-text-command-v1'

def parse_complete(content,finish_reason):
    """Same upstream extraction/count semantics; retain terminal/nonempty gates.

    Think delimiters in message.content are prose, not an additional authorization
    channel. Separate reasoning fields are never concatenated into content.
    This function returns data only. No shell, model, or sandbox invocation exists.
    """
    if not isinstance(content,str) or finish_reason!='stop':
        raise ValueError('complete text response required')
    provenance,expression=parser_binding()
    actions=eval(expression,{'re':re,'action_regex':REGEX,'content':content})
    if len(actions)!=1 or not actions[0]:raise ValueError('exactly one nonempty upstream action required')
    return {'contract':CONTRACT,'command':actions[0],'raw_content':content,
            'parser_revision':provenance['revision'],'source_hashes':provenance['source_hashes']}
