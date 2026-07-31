from dataclasses import dataclass


@dataclass(frozen=True)
class Point:
    x: float
    y: float

    def distance_to(self, other: "Point") -> float:
        return ((self.x - other.x) ** 2 + (self.y - other.y) ** 2) ** 0.5


def midpoint(a: Point, b: Point) -> Point:
    return Point((a.x + b.x) / 2, (a.y + b.y) / 2)
