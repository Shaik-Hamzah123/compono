"""Core geometry/result types shared across the resolver package."""

from __future__ import annotations

from dataclasses import dataclass, field

from compono.schema import PrimitiveBase


@dataclass(frozen=True)
class Rect:
    x: int
    y: int
    w: int
    h: int


@dataclass(frozen=True)
class ConnectorPoints:
    start: tuple[int, int]
    end: tuple[int, int]
    # Intermediate bend points, in order from `start` to `end`, for a
    # connector routed around an obstacle (empty for a clean direct line —
    # `.start`/`.end` alone still describe that common case). render.py draws
    # one straight segment per consecutive pair in (start, *waypoints, end).
    waypoints: tuple[tuple[int, int], ...] = ()


@dataclass
class LayoutResult:
    page_width: int
    page_height: int
    rects: dict[str, Rect] = field(default_factory=dict)
    connectors: dict[str, ConnectorPoints] = field(default_factory=dict)
    # The primitive that produced each rect, keyed by the same id — a single
    # source of truth so render.py never has to re-derive the id scheme above.
    items: dict[str, PrimitiveBase] = field(default_factory=dict)
    # Real parent-child id relationships (child id -> parent grid's id), captured
    # during grid recursion — a grid's rect legitimately contains its children's
    # rects, so consumers checking for overlap need real containment, not a
    # string-prefix guess (explicit `id` override on a primitive breaks any
    # such guess).
    parents: dict[str, str] = field(default_factory=dict)
