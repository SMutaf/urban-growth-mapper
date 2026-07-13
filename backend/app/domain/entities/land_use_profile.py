from enum import Enum


class LandUseProfile(str, Enum):
    """Which land use the heatmap is being scored for. Von Thünen (1826) /
    Alonso (1964): different land uses have genuinely different bid-rent
    curves - a parcel that's excellent for a warehouse (highway junction
    access, cheap land far from the CBD) can be mediocre for housing (same
    junction access reads as noise/heavy-truck-traffic exposure). BALANCED
    is the unweighted case (every contributor at its default strength) -
    the same behavior the model had before profiles existed.
    """

    BALANCED = "balanced"
    RESIDENTIAL = "residential"
    COMMERCIAL = "commercial"
    INDUSTRIAL = "industrial"
