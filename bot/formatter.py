"""Markdown alert formatters for Smart Bird.

Formatters are defensive: they lean on ``dict.get`` with sensible defaults so
missing Birdeye fields don't produce ``KeyError`` at alert-fire time.
"""
from __future__ import annotations


def format_entry_alert(
    token: dict,
    score: int,
    breakdown: dict,
    smart_money: dict,
    liquidity: dict,
) -> str:
    """Build the entry alert message.

    Parameters
    ----------
    token:        Layer 1 token dict — must contain at least ``address`` and ``symbol``.
    score:        Layer 1 graduation score (0-100).
    breakdown:    Scoring breakdown (unused by the message body today but passed
                  through so callers can log / attach it later).
    smart_money:  Layer 2 hit — ``wallet`` and ``minutes_ago`` required.
    liquidity:    Layer 3 snapshot — ``current_liquidity`` in USD.
    """
    address = token.get('address', '')
    symbol = token.get('symbol') or '???'
    price = float(token.get('price') or 0.0)
    market_cap = float(token.get('market_cap') or 0.0)

    wallet = smart_money.get('wallet') or ''
    short_wallet = (
        f'{wallet[:4]}...{wallet[-4:]}' if len(wallet) >= 8 else (wallet or 'unknown')
    )
    minutes_ago = int(smart_money.get('minutes_ago') or 0)

    current_liquidity = float(liquidity.get('current_liquidity') or 0.0)

    strength = (
        'STRONG' if score >= 85 else ('MODERATE' if score >= 70 else 'WEAK')
    )

    # Keep a defensive reference to ``breakdown`` so linters don't flag the
    # parameter as unused — callers expect us to accept the full signature.
    _ = breakdown

    return (
        f"🚨 *SMART BIRD ALERT*\n"
        f"Token: ${symbol} (`{address}`)\n"
        f"Price: ${price:.6f} | MCap: ${market_cap:,.0f}\n"
        f"✅ Graduation Score: {score}/100\n"
        f"✅ Smart Money: {short_wallet} entered {minutes_ago}min ago\n"
        f"✅ Liquidity: Healthy (${current_liquidity/1000:.1f}k depth)\n"
        f"⚡ Signal Strength: *{strength}*\n"
        f"🔗 Birdeye: https://birdeye.so/token/{address}"
    )


def format_exit_alert(
    symbol: str,
    drop_pct: float,
    window_minutes: int,
    lp_concentration: float,
) -> str:
    """Build the exit alert message."""
    symbol = symbol or '???'
    try:
        drop_pct_f = float(drop_pct)
    except (TypeError, ValueError):
        drop_pct_f = 0.0
    try:
        lp_f = float(lp_concentration)
    except (TypeError, ValueError):
        lp_f = 0.0
    return (
        f"🔴 *EXIT SIGNAL* — ${symbol}\n"
        f"Liquidity dropped {drop_pct_f*100:.0f}% in {int(window_minutes)}min\n"
        f"LP concentration: {lp_f*100:.0f}%"
    )
