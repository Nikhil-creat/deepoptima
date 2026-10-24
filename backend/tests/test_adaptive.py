from app.nas.adaptive import adapt_weights, OP_NAMES

def _t(op, rank): return {"genotype": {"ops": [op]}, "pareto_rank": rank}

def test_successful_operator_gets_more_weight():
    trials = [_t("width", 0)] * 8 + [_t("add", 2)] * 8
    w = dict(zip(OP_NAMES, adapt_weights(trials)))
    assert w["width"] > w["add"]

def test_floor_and_normalisation():
    w = adapt_weights([_t("skip", 3)] * 50)
    assert min(w) > 0 and abs(sum(w) / len(w) - 1) < 1e-6

def test_prior_blend():
    prior = [0.0] * 7 + [10.0]
    assert adapt_weights([], prior)[-1] > adapt_weights([])[-1]
