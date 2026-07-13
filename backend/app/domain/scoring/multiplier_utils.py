# Shared helpers for contributors that sum many independent items (every
# nearby amenity, every nearby project, every nearby hazard zone) rather
# than following a single distance band. In the multiplicative scoring
# model (see contributors/interfaces.py) every contributor must return a
# bounded multiplier, never an unbounded raw sum - these squash a capped
# sum into a safe multiplier range without ever touching 0.0.


def positive_sum_to_multiplier(total: float, max_total: float, max_multiplier: float) -> float:
    """Maps a non-negative sum in [0, max_total] linearly onto a multiplier
    in [1.0, max_multiplier]. Values beyond max_total are capped first, so
    "how many nearby things are there" can't blow up the multiplier
    unboundedly.
    """
    capped = min(max(total, 0.0), max_total)
    return 1.0 + (capped / max_total) * (max_multiplier - 1.0)


def penalty_sum_to_multiplier(total: float, max_total: float, min_multiplier: float) -> float:
    """Maps a non-negative severity sum in [0, max_total] linearly onto a
    multiplier in [min_multiplier, 1.0] - the penalty equivalent of
    positive_sum_to_multiplier. min_multiplier must be > 0: that's the worst
    case a contributor using this can ever return, so callers should pick a
    floor that's severe but never zero (e.g. 0.25, not 0.0).
    """
    capped = min(max(total, 0.0), max_total)
    return 1.0 - (capped / max_total) * (1.0 - min_multiplier)
