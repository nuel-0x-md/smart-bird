"""Smart Bird configuration — env-driven constants and the smart money wallet list.

Every knob that controls the three-layer pipeline lives here: API credentials,
scoring thresholds, polling cadence, dedup windows, and on-disk paths. Keeping
these in one place makes tuning from ``.env`` trivial and keeps the rest of the
codebase declarative.
"""
import os

from dotenv import load_dotenv

load_dotenv()

# ---------------------------------------------------------------------------
# Credentials
# ---------------------------------------------------------------------------
BIRDEYE_API_KEY = os.getenv('BIRDEYE_API_KEY', '')
BIRDEYE_BASE_URL = 'https://public-api.birdeye.so'

TELEGRAM_BOT_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN', '')
TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID', '')

# ---------------------------------------------------------------------------
# Layer 1 — Graduation predictor
# ---------------------------------------------------------------------------
GRADUATION_SCORE_THRESHOLD = int(os.getenv('GRADUATION_SCORE_THRESHOLD', '65'))
MIN_HOLDER_COUNT = 100
MIN_BUY_PRESSURE = 0.60  # 60%

# ---------------------------------------------------------------------------
# Layer 2 — Smart money tracker
# ---------------------------------------------------------------------------
SMART_MONEY_LOOKBACK_MINUTES = 15
_raw_wallets = os.getenv('SMART_MONEY_WALLETS', '')
DEFAULT_SMART_MONEY_WALLETS = [
    # Publicly known alpha wallets (seed list — override via env).
    # These are example/illustrative addresses; replace with your own curated list.
    'AAaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa',
    'BBbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb',
    'CCccccccccccccccccccccccccccccccccccccccccccc',
    'DDddddddddddddddddddddddddddddddddddddddddddd',
    'EEeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeee',
    'FFffffffffffffffffffffffffffffffffffffffffff',
    'GGgggggggggggggggggggggggggggggggggggggggggg',
    'HHhhhhhhhhhhhhhhhhhhhhhhhhhhhhhhhhhhhhhhhhhh',
    'JJjjjjjjjjjjjjjjjjjjjjjjjjjjjjjjjjjjjjjjjjjj',
    'KKkkkkkkkkkkkkkkkkkkkkkkkkkkkkkkkkkkkkkkkkkk',
    'LLllllllllllllllllllllllllllllllllllllllllll',
    'MMmmmmmmmmmmmmmmmmmmmmmmmmmmmmmmmmmmmmmmmmmm',
]
SMART_MONEY_WALLETS = (
    [w.strip() for w in _raw_wallets.split(',') if w.strip()]
    if _raw_wallets else DEFAULT_SMART_MONEY_WALLETS
)

# ---------------------------------------------------------------------------
# Layer 3 — Liquidity stress monitor
# ---------------------------------------------------------------------------
LIQUIDITY_DROP_THRESHOLD = float(os.getenv('LIQUIDITY_DROP_THRESHOLD', '0.20'))  # 20%
LIQUIDITY_WINDOW_SECONDS = 5 * 60  # 5 min
LP_CONCENTRATION_THRESHOLD = 0.80  # 80%

# ---------------------------------------------------------------------------
# Polling cadence
# ---------------------------------------------------------------------------
POLL_INTERVAL_SECONDS = int(os.getenv('POLL_INTERVAL_SECONDS', '60'))
LIQUIDITY_POLL_SECONDS = 60
SMART_MONEY_POLL_SECONDS = 45

# ---------------------------------------------------------------------------
# Dedup
# ---------------------------------------------------------------------------
ALERT_DEDUP_WINDOW_SECONDS = 60 * 60  # 1 hour

# ---------------------------------------------------------------------------
# Database & logging
# ---------------------------------------------------------------------------
DB_PATH = os.getenv('DB_PATH', '/data/smart-bird.db')
API_CALLS_LOG = os.getenv('API_CALLS_LOG', '/data/api_calls.log')

# ---------------------------------------------------------------------------
# Rate limiting
# ---------------------------------------------------------------------------
MAX_RETRIES = 5
BASE_BACKOFF_SECONDS = 1.5
