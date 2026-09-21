"""The prepared OR confirmation variant must reproduce the standard plug-in when given the FITTED stage-2 table."""
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'v2_sim'))
import dev_batch_dr_diagnose as X  # noqa: E402
import dr_bridge as DB  # noqa: E402
import repair_generator as G  # noqa: E402
import repair_logger as L  # noqa: E402
import sampler as S  # noqa: E402


def test_variant_with_fitted_stage2_equals_standard_plugin():
    cell = G.Cell(2, 'crossing', 'informative')
    tasks = [('t%04d' % g, g % 2) for g in range(40)]
    log = S.run_blocks(tasks, cell, 4, S.SeededDraws(11), 'cfg=test|rep=0', 'log',
                       logger=L.LOGGERS['feedback_dependent_floor_0.2'], logger_name='fb')
    logs = DB.to_logs(log, cell.K)
    idx = np.arange(len(logs.task)); train, test = logs.subset(idx[: 100]), logs.subset(idx[100:])
    for name in ('history_large_after_exception', 'prompt_only_large_if_hard', 'fixed_LS'):
        pol = {p.name: p for p in G.catalog(2)}[name]
        Q, fb, _ = DB.EA.fit_q(train, DB.prob_policy(pol))
        stage2 = {k: {a: v.get(a, fb[1][a]) for a in (0, 1)} for k, v in Q[1].items()}
        # units whose stage-1 key is absent from training use the fitted fallback in fit_q: supply it the same way
        for i in np.nonzero(train.elig[:, 1])[0]:
            stage2.setdefault(train.key[i, 1], {a: fb[1][a] for a in (0, 1)})
        _, v0_std = DB.EA.dr_scores(test, DB.prob_policy(pol), Q, fb)
        v0_var = X.or_plugin_with_stage2_q(train, test, pol, stage2)
        assert np.allclose(v0_var, v0_std, atol=1e-12), name


def test_missing_stage2_value_raises_instead_of_defaulting():
    import pytest
    cell = G.Cell(2, 'crossing', 'informative')
    tasks = [('t%04d' % g, g % 2) for g in range(20)]
    log = S.run_blocks(tasks, cell, 4, S.SeededDraws(12), 'cfg=test|rep=0', 'log',
                       logger=L.LOGGERS['uniform_floor_0.5'], logger_name='u')
    logs = DB.to_logs(log, cell.K)
    if not logs.elig[:, 1].any():
        pytest.skip('no second-stage decision in this tiny block')
    with pytest.raises(KeyError):
        X.or_plugin_with_stage2_q(logs, logs, {p.name: p for p in G.catalog(2)}['fixed_LS'], {})
