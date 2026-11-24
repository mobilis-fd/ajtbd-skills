"""Run Freqtrade CLI commands OFFLINE with static market metadata.

Why: Freqtrade loads markets from api.binance.com at start-up; from this host the endpoint answers
"Service unavailable from a restricted location". We do not route around that restriction. Instead,
for offline historical backtesting only, the market metadata is replaced (at runtime, no Freqtrade
source change) by a static description built from the ASSUMED exchange filters in configs/mvp.yaml.
No network request to Binance is made. Results are labelled "offline-markets (assumed filters)".

Usage: python -m src.ftbridge.run_offline <freqtrade args...>
"""
from __future__ import annotations

import sys

from src.config import load_config


def static_markets(cfg: dict) -> dict:
    mk = {}
    for sym in cfg["data"]["symbols"]:
        f = cfg["exchange_filters"][sym]
        base = sym.replace("USDT", "")
        pair = f"{base}/USDT"
        mk[pair] = {
            "id": sym, "symbol": pair, "base": base, "quote": "USDT", "settle": None,
            "baseId": base, "quoteId": "USDT", "settleId": None, "active": True, "type": "spot",
            "spot": True, "margin": False, "swap": False, "future": False, "option": False, "contract": False,
            "linear": None, "inverse": None, "contractSize": None, "taker": 0.001, "maker": 0.001,
            "precision": {"amount": f["step_size"], "price": f["tick_size"]},
            "limits": {"amount": {"min": f["step_size"], "max": 1e9}, "price": {"min": f["tick_size"], "max": 1e9},
                       "cost": {"min": f["min_notional"], "max": None}, "leverage": {"min": None, "max": None}},
            "info": {"offline_static_market": True},
        }
    return mk


def patch(cfg: dict) -> None:
    from freqtrade.exchange.exchange import Exchange
    markets = static_markets(cfg)

    def reload_markets(self, force: bool = False, *, load_leverage_tiers: bool = True) -> None:
        self._markets = markets
        self._api.set_markets(list(markets.values()))
        self._api_async.set_markets(list(markets.values()))
        import time
        self._last_markets_refresh = int(time.time())

    Exchange.reload_markets = reload_markets


def main(argv=None):
    cfg = load_config()
    patch(cfg)
    from freqtrade.main import main as ft_main
    ft_main(argv if argv is not None else sys.argv[1:])


if __name__ == "__main__":
    main()
