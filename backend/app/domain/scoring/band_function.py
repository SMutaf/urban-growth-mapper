from typing import List, Tuple

# A band function is a list of (distance_km, value) breakpoints sorted by
# distance. banded_value piecewise-linearly interpolates between them, and
# clamps to the first/last value outside the defined range. This is how the
# non-monotonic distance/value curves from the real-estate hedonic-pricing
# literature (e.g. a rail station's inverted-U: negative right next to it,
# peak value at a mid-distance, decaying to neutral further out) are
# expressed - a plain inverse-distance-decay formula can't represent that
# shape, since it's always monotonically decreasing.
BandFunction = List[Tuple[float, float]]


def banded_value(distance_km: float, breakpoints: BandFunction) -> float:
    if not breakpoints:
        return 0.0
    if distance_km <= breakpoints[0][0]:
        return breakpoints[0][1]
    if distance_km >= breakpoints[-1][0]:
        return breakpoints[-1][1]

    for (d0, v0), (d1, v1) in zip(breakpoints, breakpoints[1:]):
        if d0 <= distance_km <= d1:
            if d1 == d0:
                return v1
            t = (distance_km - d0) / (d1 - d0)
            return v0 + t * (v1 - v0)

    return breakpoints[-1][1]  # unreachable given the checks above
