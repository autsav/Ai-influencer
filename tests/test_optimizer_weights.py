from aeloria.optimizer.weights import update_weights, DEFAULT_WEIGHTS


def _scores(fmt_lifts):
    return {"dimensions": {"content_format": {f: {"lift": l, "n": 5} for f, l in fmt_lifts.items()}}}


def test_update_from_none_starts_from_defaults_and_preserves_total():
    scores = _scores({"reel": 1.0, "carousel": 1.0, "static": 1.0})
    out = update_weights(scores, None, 0.20)
    assert sum(out["format_mix"].values()) == 10  # default total preserved
    assert out["cta_by_format"] == DEFAULT_WEIGHTS["cta_by_format"]


def test_high_lift_raises_a_format_but_bounded_and_total_preserved():
    # carousel wildly outperforms; reel/static underperform
    scores = _scores({"reel": 0.5, "carousel": 3.0, "static": 0.5})
    out = update_weights(scores, None, 0.20)
    mix = out["format_mix"]
    assert sum(mix.values()) == 10  # total preserved
    # carousel rose vs its default 3, but the per-count change was bounded (+20% => raw 3.6)
    assert mix["carousel"] >= 3
    assert mix["reel"] <= 5 and mix["static"] <= 2


def test_bounding_clamps_delta_to_max():
    from aeloria.optimizer.weights import _bounded_count
    # lift 2.0 with max_delta 0.2 -> clamped to +20% -> 5*1.2 = 6.0
    assert _bounded_count(5, 2.0, 0.20) == 6.0
    # lift 0.0 -> clamped to -20% -> 5*0.8 = 4.0
    assert _bounded_count(5, 0.0, 0.20) == 4.0
    # neutral lift 1.0 -> unchanged
    assert _bounded_count(5, 1.0, 0.20) == 5.0
