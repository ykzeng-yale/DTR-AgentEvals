"""Shared real/fake A6 call sequencing and guaranteed owned cleanup."""
from contextlib import contextmanager
@contextmanager
def owned_scope(cleanup):
    try:yield
    finally:cleanup()
def execute_calls(dispatch):
    for index in (0,1):dispatch(index)
