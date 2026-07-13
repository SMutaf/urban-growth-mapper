from app.domain.scoring.multiplier_utils import penalty_sum_to_multiplier, positive_sum_to_multiplier


def test_positive_sum_zero_is_neutral():
    assert positive_sum_to_multiplier(0.0, max_total=3.0, max_multiplier=1.6) == 1.0


def test_positive_sum_at_cap_hits_max_multiplier():
    assert positive_sum_to_multiplier(3.0, max_total=3.0, max_multiplier=1.6) == 1.6


def test_positive_sum_beyond_cap_does_not_exceed_max():
    assert positive_sum_to_multiplier(100.0, max_total=3.0, max_multiplier=1.6) == 1.6


def test_positive_sum_is_monotonic():
    low = positive_sum_to_multiplier(1.0, max_total=3.0, max_multiplier=1.6)
    high = positive_sum_to_multiplier(2.0, max_total=3.0, max_multiplier=1.6)
    assert high > low


def test_penalty_sum_zero_is_neutral():
    assert penalty_sum_to_multiplier(0.0, max_total=3.0, min_multiplier=0.25) == 1.0


def test_penalty_sum_at_cap_hits_min_multiplier():
    assert penalty_sum_to_multiplier(3.0, max_total=3.0, min_multiplier=0.25) == 0.25


def test_penalty_sum_never_reaches_zero():
    result = penalty_sum_to_multiplier(1000.0, max_total=3.0, min_multiplier=0.25)
    assert result > 0.0
    assert result == 0.25
