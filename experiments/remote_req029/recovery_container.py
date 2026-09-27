"""Fixed container helper: preserve bounded import diagnostics inside JSON."""
from comparator_container import CODE as FROZEN_CODE
CAPTURE = '''
import contextlib,io
class DiagnosticBuffer(io.StringIO):
    def write(self,text):
        if len(self.getvalue().encode())+len(text.encode())>65536:
            raise ValueError('import diagnostic cap')
        return super().write(text)
def captured_import(name):
    output,error=DiagnosticBuffer(),DiagnosticBuffer()
    with contextlib.redirect_stdout(output),contextlib.redirect_stderr(error):
        module=importlib.import_module(name)
    return module,{'stdout':output.getvalue(),'stderr':error.getvalue()}
'''
assert FROZEN_CODE.count("    module=importlib.import_module(s['import_module'])")==1
CODE=FROZEN_CODE.replace("s=json.loads",CAPTURE+"\ns=json.loads",1).replace(
    "    module=importlib.import_module(s['import_module'])",
    "    module,diagnostics=captured_import(s['import_module'])").replace(
    "'import_path':module.__file__,'writable':True,'limits_verified':True}",
    "'import_path':module.__file__,'writable':True,'limits_verified':True,'import_diagnostics':diagnostics}")
