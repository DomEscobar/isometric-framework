"""Typed terrain intent: the only thing a language model decides. Geometry is generated from it in code."""
from typing import Literal
from pydantic import Field
from hybrid_layout import Strict

Point = list[int]


class Rect(Strict):
    x: int = Field(ge=0, le=27)
    y: int = Field(ge=0, le=27)
    width: int = Field(ge=1, le=28)
    height: int = Field(ge=1, le=28)

    def cells(self):
        return {(x, y) for y in range(self.y, self.y + self.height) for x in range(self.x, self.x + self.width)}


class Pond(Rect):
    """Water cells; the organic guide rounds the rectangle into a natural shoreline."""


class Stairs(Strict):
    side: Literal['north', 'south', 'east', 'west']
    offset: int = Field(ge=0, le=27, description='Absolute x (north/south side) or y (east/west side) of the first stair cell')
    width: int = Field(ge=1, le=3)


class Plateau(Rect):
    levels: int = Field(ge=1, le=2, description='Height above the meadow in full tile heights; the stair flight has three steps per level')
    stairs: Stairs


class Path(Strict):
    waypoints: list[Point] = Field(min_length=2, max_length=12,
                                   description='Cells the path visits in order; a path starting on another path is a branch')


class TerrainSpec(Strict):
    schema: Literal['terrain-spec/1']
    width: int = Field(ge=4, le=28)
    height: int = Field(ge=4, le=28)
    ponds: list[Pond] = Field(max_length=3)
    plateaus: list[Plateau] = Field(max_length=2)
    paths: list[Path] = Field(max_length=4)
    spawn: Point = Field(min_length=2, max_length=2)
    goals: list[Point] = Field(min_length=1, max_length=6)
