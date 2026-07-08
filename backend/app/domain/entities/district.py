from dataclasses import dataclass


@dataclass
class District:
    name: str
    city: str
    population: int
    population_year: int
    growth_rate: float
