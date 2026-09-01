"""Spec 2.4 — Wildcard budget planner.

Section 4 of the plan: Isak needs +£3.0m while the Bench Boost needs the bench
upgraded from £17.0m of fodder. These compete. Show the arithmetic; don't pick.
"""
from __future__ import annotations

from dataclasses import dataclass

from ..api.model import Bootstrap, Player
from ..engine.squad import Squad


@dataclass
class ShapeCost:
    key: str
    label: str
    note: str
    forwards: list[Player]
    third_forward_budget: float
    available: float          # squad value + bank
    bench_target: float
    blocked_reason: str | None = None

    @property
    def forward_spend(self) -> float:
        return round(sum(p.price for p in self.forwards) + self.third_forward_budget, 1)

    def outfield_budget(self) -> float:
        """What's left for the other 12 once forwards and bench are paid for."""
        return round(self.available - self.forward_spend - self.bench_target, 1)

    @property
    def affordable(self) -> bool:
        if self.blocked_reason:
            return False
        # 8 remaining starters (GK + 3 DEF + 4 MID at minimum viable prices)
        return self.outfield_budget() >= 8 * 4.5


def evaluate(cfg, bs: Bootstrap, squad: Squad) -> list[ShapeCost]:
    shapes = cfg.plan.get("wildcard_shapes", {})
    brief = cfg.plan.get("wildcard_brief", {})
    bench_target = float(brief.get("bench_budget_target", 19.0))
    available = round(squad.total_value + squad.bank, 1)
    haaland = bs.player(411)

    out = []
    for key, s in shapes.items():
        blocked = None
        if s.get("requires_haaland_flagged") and haaland and not haaland.is_flagged:
            blocked = "Haaland is fit — this shape breaks the GW7 Triple Captain"
        out.append(ShapeCost(
            key=key, label=s.get("label", key), note=s.get("note", ""),
            forwards=bs.players(s.get("forwards", [])),
            third_forward_budget=float(s.get("budget_third_forward", 5.5)),
            available=available, bench_target=bench_target,
            blocked_reason=blocked,
        ))
    return out


def render(shapes: list[ShapeCost]) -> str:
    lines = []
    for s in shapes:
        fw = " + ".join(f"{p.name} £{p.price:.1f}m" for p in s.forwards)
        lines.append(f"Shape {s.key} — {s.label}")
        lines.append(f"  Forwards: {fw} + £{s.third_forward_budget:.1f}m budget "
                     f"= £{s.forward_spend:.1f}m")
        lines.append(f"  Bench target £{s.bench_target:.1f}m → "
                     f"£{s.outfield_budget():.1f}m left for the other 8 starters "
                     f"(£{s.outfield_budget()/8:.2f}m each)")
        if s.blocked_reason:
            lines.append(f"  ✗ {s.blocked_reason}")
        else:
            lines.append(f"  {'✓ affordable' if s.affordable else '✗ does not fit'}")
        lines.append("")
    return "\n".join(lines)
