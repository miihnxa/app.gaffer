"""Spec 1.4 — form tracker and the lower-form transfer guard.

Written because Igor Jesus (form 1.5) nearly replaced Brobbey (form 2.0):
reputation and fixtures looked good, live form did not.
"""
from __future__ import annotations

from dataclasses import dataclass

from ..api.model import Player
from ..notify import Alert


@dataclass
class TransferVerdict:
    out_player: Player
    in_player: Player
    blocked: bool
    reasons: list[str]
    notes: list[str]

    @property
    def form_delta(self) -> float:
        return round(self.in_player.form - self.out_player.form, 1)

    @property
    def cost(self) -> float:
        return round(self.in_player.price - self.out_player.price, 1)

    def render(self) -> str:
        arrow = "→"
        lines = [
            f"OUT  {self.out_player.label():<34} form {self.out_player.form}",
            f"IN   {self.in_player.label():<34} form {self.in_player.form}",
            "",
            f"Form change: {self.form_delta:+.1f}   Cost: £{self.cost:+.1f}m",
        ]
        if self.reasons:
            lines += ["", "BLOCKED:"] + [f"  ✗ {r}" for r in self.reasons]
        if self.notes:
            lines += ["", "Notes:"] + [f"  • {n}" for n in self.notes]
        if not self.reasons:
            lines += ["", "✓ Passes your rules."]
        return "\n".join(lines)


def check_transfer(out_player: Player, in_player: Player, *,
                   bank: float = 0.0, gw: int | None = None,
                   no_hits_before_gw: int = 6, free_transfers: int = 1,
                   squad_clubs: dict[str, int] | None = None,
                   override: bool = False) -> TransferVerdict:
    """Run a proposed transfer past the rules in section 6 of the build spec."""
    reasons: list[str] = []
    notes: list[str] = []

    # The rule this whole feature exists for.
    if in_player.form < out_player.form:
        msg = (f"{in_player.name} form {in_player.form} is BELOW "
               f"{out_player.name} form {out_player.form} — "
               f"you'd be paying a transfer to move backwards")
        reasons.append(msg) if not override else notes.append("OVERRIDDEN: " + msg)

    if in_player.is_flagged:
        reasons.append(
            f"{in_player.name} is flagged ({in_player.status_text}"
            + (f", {in_player.effective_chance}% to play" if in_player.effective_chance < 100 else "")
            + ")"
        )

    cost = in_player.price - out_player.price
    if cost > bank + 1e-9:
        reasons.append(f"costs £{cost:.1f}m, you have £{bank:.1f}m in the bank")

    if free_transfers < 1:
        hit = "a -4 hit"
        if gw is not None and gw < no_hits_before_gw:
            reasons.append(
                f"no free transfer — this is {hit}, and your rule is no hits before GW{no_hits_before_gw}"
            )
        else:
            notes.append(f"no free transfer left — this costs {hit}")

    if squad_clubs:
        after = dict(squad_clubs)
        after[out_player.team_short] = after.get(out_player.team_short, 0) - 1
        after[in_player.team_short] = after.get(in_player.team_short, 0) + 1
        if after[in_player.team_short] > 3:
            reasons.append(
                f"would give you {after[in_player.team_short]} {in_player.team_short} "
                f"players — max is 3"
            )

    if in_player.pos != out_player.pos:
        notes.append(
            f"position change {out_player.pos} → {in_player.pos} — check your formation stays legal"
        )

    if in_player.form >= out_player.form and not reasons:
        notes.append(f"form improves by {in_player.form - out_player.form:+.1f}")

    return TransferVerdict(out_player, in_player, bool(reasons), reasons, notes)


def form_table(players: list[Player], label: str) -> str:
    rows = sorted(players, key=lambda p: -p.form)
    out = [f"{label}:"]
    for p in rows:
        flag = " ⚠️" if p.is_flagged else ""
        out.append(
            f"  {p.form:>4}  {p.name:<14} {p.team_short:<4} £{p.price:>4.1f}m  "
            f"{p.total_points:>3}pts{flag}"
        )
    return "\n".join(out)


def collapse_alerts(owned: list[Player], threshold: float = 2.0) -> list[Alert]:
    """Flag 'keep unless form collapses' players whose form has fallen away."""
    alerts = []
    for p in owned:
        if p.form < threshold and not p.is_flagged and p.raw.get("minutes", 0) > 90:
            alerts.append(Alert(
                title=f"📉 {p.name} form {p.form}",
                body=(f"{p.label()} has form {p.form} over the last 30 days "
                      f"({p.total_points} pts total).\nWorth a look on the Wildcard."),
                priority="low", tags=["chart_with_downwards_trend"],
                dedupe_key=f"form-collapse:{p.id}:{int(p.form*10)}",
            ))
    return alerts
