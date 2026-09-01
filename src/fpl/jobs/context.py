"""Shared job setup — one place that builds config, client, squad, dispatcher."""
from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path

from ..api.client import FPLClient
from ..api.model import Bootstrap, Player
from ..config import Config, LOG_DIR
from ..engine import squad as squad_engine
from ..notify import Dispatcher, build_notifier


def setup_logging(verbose: bool = False) -> None:
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    handlers = [logging.FileHandler(LOG_DIR / "fpl-assistant.log")]
    if verbose:
        handlers.append(logging.StreamHandler())
    logging.basicConfig(
        level=logging.DEBUG if verbose else logging.INFO,
        format="%(asctime)s %(levelname)-7s %(name)s %(message)s",
        handlers=handlers, force=True,
    )


@dataclass
class Context:
    cfg: Config
    client: FPLClient
    bs: Bootstrap
    dispatcher: Dispatcher

    @property
    def squad(self) -> squad_engine.Squad:
        if not hasattr(self, "_squad"):
            self._squad = squad_engine.resolve(self.cfg, self.client, self.bs)
        return self._squad

    @property
    def owned(self) -> list[Player]:
        return self.squad.players

    @property
    def watched(self) -> list[Player]:
        owned_ids = {p.id for p in self.owned}
        return [p for p in self.bs.players(self.cfg.watchlist_ids())
                if p.id not in owned_ids]


def build(dry_run: bool = False, verbose: bool = False,
          notifier: str | None = None, force_refresh: bool = False) -> Context:
    setup_logging(verbose)
    cfg = Config.load()
    client = FPLClient(cfg)
    bs = Bootstrap(client.bootstrap(force=force_refresh))
    n = build_notifier(cfg, notifier or ("console" if dry_run else None))
    return Context(cfg, client, bs, Dispatcher(cfg, n, dry_run=dry_run))
