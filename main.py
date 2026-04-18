"""Smart Bird — entry point.

Boots the Telegram bot, opens the shared Birdeye client, initialises the
SQLite database, and runs four concurrent loops:

    * Layer 1 — graduation predictor
    * Layer 2 — smart money tracker
    * Layer 3 — liquidity stress monitor
    * Alert dispatcher — combines the three into entry alerts

SIGTERM / SIGINT gracefully cancels the loops, closes the HTTP session, stops
the Telegram bot and closes the DB.
"""
from __future__ import annotations

import asyncio
import logging
import signal

from birdeye.client import BirdeyeClient
from birdeye.liquidity import LiquidityMonitor
from birdeye.new_listings import GraduationPredictor
from birdeye.smart_money import SmartMoneyTracker
from bot.formatter import format_entry_alert, format_exit_alert
from bot.telegram_bot import SmartBirdBot
from config import (
    ALERT_DEDUP_WINDOW_SECONDS,
    LIQUIDITY_POLL_SECONDS,
    POLL_INTERVAL_SECONDS,
    SMART_MONEY_POLL_SECONDS,
    SMART_MONEY_WALLETS,
    TELEGRAM_BOT_TOKEN,
    TELEGRAM_CHAT_ID,
)
from db.database import Database

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(name)s: %(message)s',
)
log = logging.getLogger('smart-bird')


# --------------------------------------------------------------------------- #
# Monitoring loops
# --------------------------------------------------------------------------- #

async def layer1_loop(
    predictor: GraduationPredictor,
    db: Database,
    signal_queue: 'asyncio.Queue[tuple[str, dict]]',
) -> None:
    """Periodically pull new listings, score them, and queue passers."""
    del db  # Layer 1 persists via predictor.run_once itself.
    while True:
        try:
            passed = await predictor.run_once()
            for token in passed:
                await signal_queue.put(('layer1', token))
        except asyncio.CancelledError:
            raise
        except Exception as e:
            log.exception('layer1_loop error: %s', e)
        await asyncio.sleep(POLL_INTERVAL_SECONDS)


async def layer2_loop(
    tracker: SmartMoneyTracker,
    db: Database,
    signal_queue: 'asyncio.Queue[tuple[str, dict]]',
) -> None:
    """For every Layer-1 token, check if smart money entered recently."""
    while True:
        try:
            tokens = await db.get_tracked_tokens(['layer1'])
            for t in tokens:
                address = t.get('address')
                if not address:
                    continue
                hit = await tracker.check_token(address)
                if hit:
                    await db.mark_layer2_confirmed(address, hit['wallet'])
                    await signal_queue.put(
                        ('layer2', {'token': t, 'smart_money': hit})
                    )
        except asyncio.CancelledError:
            raise
        except Exception as e:
            log.exception('layer2_loop error: %s', e)
        await asyncio.sleep(SMART_MONEY_POLL_SECONDS)


async def layer3_loop(
    monitor: LiquidityMonitor,
    db: Database,
    bot: SmartBirdBot,
) -> None:
    """Snapshot liquidity and fire exit alerts when stress is detected."""
    while True:
        try:
            tokens = await db.get_tracked_tokens(
                ['layer1', 'layer2', 'alerted'],
            )
            for t in tokens:
                address = t.get('address')
                if not address:
                    continue
                await monitor.snapshot(address)
                stress = await monitor.detect_stress(address)
                if not stress:
                    continue
                if await db.was_alerted_recently(
                    address, 'exit', ALERT_DEDUP_WINDOW_SECONDS,
                ):
                    continue
                msg = format_exit_alert(
                    t.get('symbol') or '???',
                    stress['drop_pct'],
                    stress['window_minutes'],
                    stress['lp_concentration'],
                )
                await bot.send_alert(msg)
                await db.record_alert_sent(address, 'exit')
        except asyncio.CancelledError:
            raise
        except Exception as e:
            log.exception('layer3_loop error: %s', e)
        await asyncio.sleep(LIQUIDITY_POLL_SECONDS)


async def alert_dispatcher(
    signal_queue: 'asyncio.Queue[tuple[str, dict]]',
    db: Database,
    monitor: LiquidityMonitor,
    bot: SmartBirdBot,
    predictor: GraduationPredictor,
) -> None:
    """Combine layer outputs into entry alerts, deduped on (address, 'entry')."""
    while True:
        try:
            kind, payload = await signal_queue.get()
            if kind != 'layer2':
                continue
            token = payload.get('token') or {}
            smart_money = payload.get('smart_money') or {}
            address = token.get('address')
            if not address:
                continue

            if await db.was_alerted_recently(
                address, 'entry', ALERT_DEDUP_WINDOW_SECONDS,
            ):
                continue

            liq = await monitor.snapshot(address)
            if not liq:
                continue

            score, breakdown = await predictor.score_token(address)
            token_for_msg = {
                'address': address,
                'symbol': token.get('symbol') or breakdown.get('symbol') or '???',
                'price': breakdown.get('price', 0.0),
                'market_cap': breakdown.get('market_cap', 0.0),
            }
            msg = format_entry_alert(
                token_for_msg, score, breakdown, smart_money,
                {'current_liquidity': liq['liquidity_usd']},
            )
            await bot.send_alert(msg)
            await db.record_alert_sent(address, 'entry')
            await db.mark_alerted(address)
        except asyncio.CancelledError:
            raise
        except Exception as e:
            log.exception('alert_dispatcher error: %s', e)


async def smoke_test(client: BirdeyeClient) -> None:
    """Confirm Birdeye connectivity at startup.

    Also counts toward the BIP Sprint 1 minimum-API-call total.
    """
    log.info('Running Birdeye smoke test...')
    trending = await client.get_trending(limit=5)
    if trending:
        log.info('Birdeye smoke test OK — received %d trending tokens', len(trending))
    else:
        log.warning('Birdeye smoke test failed — check API key and network')


# --------------------------------------------------------------------------- #
# Orchestration
# --------------------------------------------------------------------------- #

async def main() -> None:
    """Wire everything together and run until a termination signal arrives."""
    db = Database()
    await db.init()
    client = BirdeyeClient()
    predictor = GraduationPredictor(client, db)
    tracker = SmartMoneyTracker(client, db, SMART_MONEY_WALLETS)
    monitor = LiquidityMonitor(client, db)
    bot = SmartBirdBot(TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID, db)

    await bot.start()
    await smoke_test(client)
    log.info('Smart Bird bot started — monitoring Solana for graduation signals')

    signal_queue: asyncio.Queue = asyncio.Queue()
    stop_event = asyncio.Event()

    loop = asyncio.get_running_loop()
    for sig in (signal.SIGTERM, signal.SIGINT):
        try:
            loop.add_signal_handler(sig, stop_event.set)
        except NotImplementedError:
            # Some platforms (Windows) can't attach signal handlers — fall back
            # to the default KeyboardInterrupt path for SIGINT.
            pass

    tasks = [
        asyncio.create_task(layer1_loop(predictor, db, signal_queue)),
        asyncio.create_task(layer2_loop(tracker, db, signal_queue)),
        asyncio.create_task(layer3_loop(monitor, db, bot)),
        asyncio.create_task(
            alert_dispatcher(signal_queue, db, monitor, bot, predictor)
        ),
    ]

    await stop_event.wait()
    log.info('Shutdown signal received — cleaning up...')
    for t in tasks:
        t.cancel()
    await asyncio.gather(*tasks, return_exceptions=True)
    await bot.stop()
    await client.aclose()
    await db.aclose()
    log.info('Smart Bird stopped cleanly')


if __name__ == '__main__':
    asyncio.run(main())
