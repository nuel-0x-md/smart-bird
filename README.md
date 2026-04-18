# Smart Bird 🐦

> Three-layer Solana token intelligence bot — graduation predictor + smart money tracker + liquidity stress monitor, powered by Birdeye Data API

---

## 🏆 Built for Birdeye Data BIP Competition — Sprint 1 (April 2026)

A unified signal pipeline that stacks three distinct on-chain intelligence layers into a single, high-conviction Telegram alert. Every Birdeye call is logged to `api_calls.log`, and the stack is packaged as a reproducible `docker compose` deployment.

> Tags: `#BirdeyeAPI` `@birdeye_data`

---

## 🧠 What it does

Smart Bird runs three asynchronous loops in parallel and stitches them into two distinct alert types:

1. **Layer 1 — Graduation Predictor.** Scans newly-listed Solana tokens and scores them 0–100 on volume velocity, holder base, buy pressure and short-window price trajectory. Honeypot / mintable / top-holder-concentrated rugs are filtered out before scoring.
2. **Layer 2 — Smart Money Tracker.** Watches the recent swap history of every Layer-1 passer for entries by a curated alpha-wallet set (configurable via env). Validates the wallet still holds the token via portfolio lookup before confirming.
3. **Layer 3 — Liquidity Stress Monitor.** Snapshots liquidity and LP concentration every minute for every active token. Powers **independent exit alerts** whenever liquidity drops >20% in a 5-minute window or the top-10 holder share exceeds 80%.

**Entry alert** fires when **Layer 1 + Layer 2** both pass for the same token (Layer 3 then runs a fresh liquidity snapshot for the alert body but is not a gate). **Exit alert** fires from Layer 3 alone whenever a watched token's liquidity collapses or concentration spikes. Both alert types are deduped on `(address, alert_type)` over a rolling 1-hour window.

---

## 🏗️ Architecture

```
        ┌──────────────────────────────────────────────┐
        │              Birdeye Data API                │
        │   /defi/v2/tokens/new_listing                │
        │   /defi/token_security                       │
        │   /defi/token_overview                       │
        │   /defi/token_trending                       │
        │   /defi/ohlcv                                │
        │   /defi/txs/token                            │
        │   /v1/wallet/token_list                      │
        │   /defi/v3/token/holder                      │
        └────────────────────┬─────────────────────────┘
                             │ async aiohttp
                             ▼
        ┌──────────────────────────────────────────────┐
        │            BirdeyeClient (client.py)         │
        │   • shared session  • exp backoff            │
        │   • api_calls.log writer                     │
        └──────┬─────────────┬─────────────┬───────────┘
               │             │             │
      ┌────────▼─────┐ ┌─────▼──────┐ ┌────▼─────────┐
      │  Layer 1     │ │  Layer 2   │ │  Layer 3     │
      │  Graduation  │ │  Smart $   │ │  Liquidity   │
      │  Predictor   │ │  Tracker   │ │  Stress      │
      └────────┬─────┘ └─────┬──────┘ └────┬─────────┘
               │             │             │
               └──────┬──────┴──────┬──────┘
                      ▼             ▼
              ┌──────────────┐ ┌──────────┐
              │ Signal Queue │ │ SQLite DB│
              └──────┬───────┘ └──────────┘
                     ▼
              ┌──────────────┐
              │ Alert        │
              │ Dispatcher   │──► Telegram (entry / exit alerts)
              └──────────────┘
```

---

## 🔌 Birdeye endpoints used

| Endpoint | Purpose |
|---|---|
| `GET /defi/v2/tokens/new_listing` | Layer 1 candidate pool — freshly listed Solana tokens. |
| `GET /defi/token_security` | Layer 1 filter — drops honeypots, mintable tokens, and top-10-concentrated rugs. |
| `GET /defi/token_overview` | Price, market cap, liquidity, holder count, and short-window price deltas. |
| `GET /defi/token_trending` | Sanity smoke test at startup — also counts toward total API usage. |
| `GET /defi/ohlcv` | 1-minute OHLCV candles for Layer 1's volume-velocity score. |
| `GET /defi/txs/token` | Recent trades — drives buy/sell ratio **and** smart-money detection. |
| `GET /v1/wallet/token_list` | Layer 2 confirmation — verify the smart wallet still holds the token. |
| `GET /defi/v3/token/holder` | Layer 3 — top-10 holder share as an LP-concentration proxy. |

---

## ⚙️ Setup (Docker — recommended)

```bash
git clone https://github.com/nuel-0x-md/smart-bird.git
cd smart-bird
cp .env.example .env
# edit .env with your BIRDEYE_API_KEY, TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID
docker compose up --build -d
docker compose logs -f smart-bird
```

> **Layer 2 requires `SMART_MONEY_WALLETS`** — a comma-separated list of Solana wallet addresses you want to track. Without it, Layer 2 is a no-op and no entry alerts will fire (exit alerts still work).

The SQLite database and the `api_calls.log` file are persisted in the named volume `smart-bird-data` mounted at `/data`.

### Local (non-Docker) run

```bash
pip install -r requirements.txt
python main.py
```

Local runs honour the same `.env` file. You may want to override the defaults for on-disk paths, e.g.:

```bash
DB_PATH=./smart-bird.db API_CALLS_LOG=./api_calls.log python main.py
```

---

## 🪜 How signals stack

- **Entry alert** (🚨) fires only when **Layer 1 AND Layer 2** both pass for the same token, and a fresh Layer 3 snapshot succeeds.
  - Layer 1 requires `score ≥ GRADUATION_SCORE_THRESHOLD` (default 65) AND `holders ≥ 100` AND `buy_pressure ≥ 0.60`.
  - Layer 2 requires a known alpha wallet to have bought within the last 15 minutes **and** still hold the token.
- **Exit alert** (🔴) fires independently from Layer 3 whenever a token already on the watchlist shows a >20% liquidity drop over a 5-minute window OR an LP concentration above 80%.
- The `(address, alert_type)` pair is deduped across a rolling 1-hour window so a flapping token can't spam the channel.

---

## 📟 Sample alerts

### Entry
```
🚨 *SMART BIRD ALERT*
Token: $PEPE2 (`So11111111111111111111111111111111111111112`)
Price: $0.000123 | MCap: $842,000
✅ Graduation Score: 82/100
✅ Smart Money: 9WzD...AWWM entered 4min ago
✅ Liquidity: Healthy ($42.3k depth)
⚡ Signal Strength: *MODERATE*
🔗 Birdeye: https://birdeye.so/token/So11111111111111111111111111111111111111112
```

### Exit
```
🔴 *EXIT SIGNAL* — $PEPE2
Liquidity dropped 34% in 4min
LP concentration: 87%
```

---

## 🤖 Telegram commands

| Command | Description |
|---|---|
| `/start` | Acknowledge and confirm monitoring is active. |
| `/status` | Live counters: tracked tokens, Layer 1 / 2 / alerted, alerts in last 24h. |
| `/watchlist` | List of tokens currently on the pipeline (Layer 1, Layer 2, alerted). |

---

## 📑 API usage proof

Every Birdeye call — successful, failed, rate-limited, timed out — is appended to `api_calls.log` on one line:

```
[2026-04-18T21:10:05.123456+00:00] [GET /defi/token_overview] [200] [So11...1112]
```

The log is persisted to the `smart-bird-data` Docker volume (or `./api_calls.log` locally) and trivially satisfies the **BIP Sprint 1 minimum-50-calls** auditing requirement. Tail it live with:

```bash
docker compose exec smart-bird tail -f /data/api_calls.log
```

---

## 🧾 Project layout

```
/
├── main.py                  # orchestrator + graceful shutdown
├── config.py                # env-driven constants
├── birdeye/
│   ├── client.py            # async aiohttp Birdeye wrapper
│   ├── new_listings.py      # Layer 1 — graduation predictor
│   ├── smart_money.py       # Layer 2 — alpha-wallet tracker
│   └── liquidity.py         # Layer 3 — liquidity stress monitor
├── bot/
│   ├── telegram_bot.py      # python-telegram-bot v21 wrapper
│   └── formatter.py         # Markdown entry/exit formatters
├── db/
│   └── database.py          # SQLite, async via asyncio.to_thread
├── Dockerfile
├── docker-compose.yml
├── requirements.txt
├── .env.example
└── .gitignore
```

---

## 📝 License

MIT
