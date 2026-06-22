#!/usr/bin/env python3
"""Emit contracts/scopet.py — ScopeT precision reticle arena engine."""
from __future__ import annotations

import textwrap
from pathlib import Path

OUT = Path(__file__).resolve().parents[1] / "contracts" / "scopet.py"

BODY = r'''# scopet.py
# Crosshair drift ledger — calibrated lanes, ring scoring, spotter governance.
# Wind tables are advisory; settlement stays non-custodial on every lane.

from __future__ import annotations

import hashlib
import json
import math
import secrets
import struct
import time
import uuid
from dataclasses import asdict, dataclass, field
from enum import IntEnum
from typing import Any, Dict, List, Optional, Sequence, Tuple

# ---------------------------------------------------------------------------
# Constructor-injected role anchors (EVM mainnet style; unique to ScopeT)
# ---------------------------------------------------------------------------

ST_ADDRESS_A = "0x37F015d860E4378afaF4fCf9F189e44440266242"
ST_ADDRESS_B = "0x8BCEa101608207f31C665d379b4129Fc389fA1Db"
ST_ADDRESS_C = "0x6717d4beC4Ad43f9C46E655e9EA2F2017BC24775"
ST_ADDRESS_D = "0x8a6d2f38ca27d7828414b92C3664467111a5f59D"
ST_ADDRESS_E = "0x3EF7feF8Ac93207f4cd9f81DC9037f0E43151d32"
ST_ADDRESS_F = "0x9cD0346279E66B2Ec9E5Ff7ecA5B5D8325009896"
ST_ADDRESS_G = "0xC0400cE6C8FEE8B977DCd5720a328001cFF001E1"
ST_ADDRESS_H = "0xaEBD2bc4d5714B1B061aE200E81B2AE3B468873a"

ST_CROSSHAIR_SALT = "0xf8f891ea063e4d338d419b7d6bbbe06f04904650426e3d5e7aade30eca243606"
ST_LANE_DIGEST = "0x5d1165cc2d75cbefbd0289f2540751fa5949f038c9037be7497068a536452981"
ST_WIND_SEED = "0xeba3aaeacfe2c9e9f51d324e897b25684c7566b4ab82bb5e924be82cd284d6dc"
ST_MATCH_ROOT = "0x4588393fc27c5a8f0237b3f45aafefe84a5d0400446ae9ea2d1a612bba4c56c1"
ST_CALIBRATION_MARK = "0xcf8f54cf91fd5ec8153480d5b342e69f9291237195da2f92c70599d148494018"

ST_DECIMALS = 18
ST_SCALE = 10 ** ST_DECIMALS
ST_BASIS = 10_000
ST_MAX_FEE_BPS = 275
ST_LANE_CAPACITY = 41
ST_RING_LAYERS = 13
ST_CALIBRATION_TICKS = 167
ST_DRIFT_TICKS = 89
ST_COOLDOWN_BLOCKS = 53
ST_MAX_ACTIVE_MATCHES = 128
ST_MAX_SHOTS_PER_ROUND = 24
ST_MIN_STAKE_WEI = 88_000_000_000_000
ST_ENTRY_FEE_WEI = 120_000_000_000_000
ST_WIND_MODULUS = 37
ST_SCORE_RING_BASE = 47
ST_LEADERBOARD_DEPTH = 120
ST_SESSION_TTL_SEC = 4200
ST_MAX_LOADOUT_SLOTS = 6
ST_RETICLE_ZOOM_MAX = 16
ST_TARGET_RADIUS_MM = 240
ST_BULLSEYE_RADIUS_MM = 11
ST_PARALLAX_STEPS = 19
ST_EPOCH_SPAN = 4096
ST_VERSION_TAG = "scopet-7c3a"


class ST_LanePhase(IntEnum):
    DORMANT = 0
    CALIBRATING = 1
    LIVE = 2
    HOLD = 3
    SETTLING = 4
    ARCHIVED = 5


class ST_MatchState(IntEnum):
    QUEUED = 0
    ACTIVE = 1
    PAUSED = 2
    COMPLETE = 3
    VOIDED = 4


class ST_RingTier(IntEnum):
    OUTER = 0
    MID = 1
    INNER = 2
    BULLSEYE = 3
    CLEAN_MISS = 4


class ST_WindBand(IntEnum):
    CALM = 0
    BREEZE = 1
    GUST = 2
    SHEAR = 3


# ---------------------------------------------------------------------------
# Fault types (ScopeT-specific; not Arena*, Knights*, Tank*, Ledger*)
# ---------------------------------------------------------------------------


class ScopeTBaseFault(Exception):
    """Root fault for ScopeT engine."""


class STx_RangeMasterOnly(ScopeTBaseFault):
    pass


class STx_SpotterDenied(ScopeTBaseFault):
    pass


class STx_LaneMissing(ScopeTBaseFault):
    pass


class STx_LaneFrozen(ScopeTBaseFault):
    pass


class STx_LaneFull(ScopeTBaseFault):
    pass


class STx_MatchMissing(ScopeTBaseFault):
    pass


class STx_MatchNotLive(ScopeTBaseFault):
    pass


class STx_PlayerUnknown(ScopeTBaseFault):
    pass


class STx_ZeroDisallowed(ScopeTBaseFault):
    pass


