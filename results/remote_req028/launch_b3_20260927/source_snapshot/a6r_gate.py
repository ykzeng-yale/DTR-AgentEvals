"""A6R actual one-shot pre-Popen gate and once-only setup orchestration."""
from admission_window import reason
def setup_then_run(setup,run):
    prepared=setup()
    return run(prepared)
def admit(sample,now,sleep,observe,launch,deadline):
    previous=None;count=0
    while count<31 and now()<deadline:
        s=sample();count+=1;failure=reason(s);observe(s,failure,count,'scheduled')
        t=now()
        if t>=deadline:break
        if failure:previous=None
        elif previous is None:previous=t
        elif t-previous>=60:
            if count>=31:break
            final=sample();count+=1;failure=reason(final);observe(final,failure,count,'final_pre_popen')
            if not failure and now()<deadline:
                # No retry: a raising Popen propagates directly out of this gate.
                return launch(final)
            previous=None
        remaining=deadline-now()
        if remaining<=0:break
        sleep(min(60,remaining))
    raise TimeoutError('ADMISSION_WINDOW_EXPIRED')
