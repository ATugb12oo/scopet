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


class STx_StakeTooLow(ScopeTBaseFault):
    pass


class STx_CooldownActive(ScopeTBaseFault):
    pass


class STx_ShotBudgetExhausted(ScopeTBaseFault):
    pass


class STx_CalibrationIncomplete(ScopeTBaseFault):
    pass


class STx_LoadoutOverflow(ScopeTBaseFault):
    pass


class STx_ReticleOutOfBounds(ScopeTBaseFault):
    pass


class STx_FeeBasisExceeded(ScopeTBaseFault):
    pass


class STx_PhaseTransitionBlocked(ScopeTBaseFault):
    pass


class STx_SessionExpired(ScopeTBaseFault):
    pass


class STx_DuplicateEnrollment(ScopeTBaseFault):
    pass


class STx_WindTableLocked(ScopeTBaseFault):
    pass


class STx_SettlementPending(ScopeTBaseFault):
    pass


class STx_OracleMismatch(ScopeTBaseFault):
    pass


# ---------------------------------------------------------------------------
# Records
# ---------------------------------------------------------------------------


@dataclass
class ST_ShotTelemetry:
    shot_id: str
    player_id: str
    lane_id: int
    match_id: str
    aim_x: float
    aim_y: float
    wind_band: int
    drift_x: float
    drift_y: float
    impact_x: float
    impact_y: float
    ring_tier: int
    score_delta: int
    fired_at_tick: int


@dataclass
class ST_ReticleProfile:
    zoom_level: int
    parallax_offset: float
    calibration_progress: int
    last_adjust_tick: int
    zeroed: bool


@dataclass
class ST_LoadoutPiece:
    slot_index: int
    scope_name: str
    magnification: int
    wind_comp: float
    weight_grams: int


@dataclass
class ST_PlayerCard:
    player_id: str
    wallet_ref: str
    enrolled_lanes: List[int] = field(default_factory=list)
    total_score: int = 0
    matches_played: int = 0
    bullseyes: int = 0
    reticle: ST_ReticleProfile = field(
        default_factory=lambda: ST_ReticleProfile(1, 0.0, 0, 0, False)
    )
    loadout: List[ST_LoadoutPiece] = field(default_factory=list)
    stake_wei: int = 0
    last_seen: float = 0.0


@dataclass
class ST_LaneRecord:
    lane_id: int
    phase: int
    opened_at_tick: int
    spotter_ref: str
    enrolled_count: int
    bounty_pool_wei: int
    wind_band: int
    frozen: bool
    epoch_index: int


@dataclass
class ST_MatchRecord:
    match_id: str
    lane_id: int
    state: int
    start_tick: int
    end_tick: int
    shot_budget: int
    shots_fired: int
    participants: List[str] = field(default_factory=list)
    scoreboard: Dict[str, int] = field(default_factory=dict)
    winner_id: Optional[str] = None


@dataclass
class ST_LeaderRow:
    rank: int
    player_id: str
    wallet_ref: str
    score: int
    bullseyes: int
    matches: int


@dataclass
class ST_ChainEvent:
    event_name: str
    indexed_a: str
    indexed_b: str
    payload: Dict[str, Any]
    block_tick: int


@dataclass
class ST_WindSample:
    band: int
    vector_x: float
    vector_y: float
    sampled_tick: int


# ---------------------------------------------------------------------------
# In-memory ledger (mirrors on-chain layout without custody)
# ---------------------------------------------------------------------------


class ST_LedgerStore:
    def __init__(self) -> None:
        self.lanes: Dict[int, ST_LaneRecord] = {}
        self.matches: Dict[str, ST_MatchRecord] = {}
        self.players: Dict[str, ST_PlayerCard] = {}
        self.shots: Dict[str, ST_ShotTelemetry] = {}
        self.wind_history: Dict[int, List[ST_WindSample]] = {}
        self.events: List[ST_ChainEvent] = []
        self.lane_counter: int = 0
        self.global_tick: int = 0
        self.match_serial: int = 0
        self.fee_bps: int = 125
        self.grid_frozen: bool = False
        self.pending_range_master: Optional[str] = None
        self.range_master: str = ST_ADDRESS_A
        self.spotter: str = ST_ADDRESS_D
        self.oracle: str = ST_ADDRESS_C
        self.fee_desk: str = ST_ADDRESS_E
        self.beacon: str = ST_ADDRESS_G


# ---------------------------------------------------------------------------
# Wind and scoring helpers
# ---------------------------------------------------------------------------


def st_wind_vector(band: int, tick: int) -> Tuple[float, float]:
    seed = int(ST_WIND_SEED, 16) ^ (tick * ST_WIND_MODULUS) ^ (band << 9)
    vx = ((seed & 0xFFFF) / 65535.0 - 0.5) * (band + 1) * 0.42
    vy = (((seed >> 16) & 0xFFFF) / 65535.0 - 0.5) * (band + 1) * 0.38
    return round(vx, 6), round(vy, 6)


def st_ring_from_impact(dx: float, dy: float) -> Tuple[int, int]:
    dist = math.hypot(dx, dy)
    if dist <= ST_BULLSEYE_RADIUS_MM:
        return int(ST_RingTier.BULLSEYE), ST_SCORE_RING_BASE * 8
    if dist <= ST_TARGET_RADIUS_MM * 0.18:
        return int(ST_RingTier.INNER), ST_SCORE_RING_BASE * 5
    if dist <= ST_TARGET_RADIUS_MM * 0.42:
        return int(ST_RingTier.MID), ST_SCORE_RING_BASE * 3
    if dist <= ST_TARGET_RADIUS_MM:
        return int(ST_RingTier.OUTER), ST_SCORE_RING_BASE
    return int(ST_RingTier.CLEAN_MISS), 0


def st_digest_lane(lane_id: int, phase: int, epoch: int) -> str:
    packed = struct.pack(">IQI", lane_id, epoch, phase)
    return hashlib.sha256(packed + bytes.fromhex(ST_LANE_DIGEST[2:])).hexdigest()


def st_digest_match(match_id: str, lane_id: int, tick: int) -> str:
    raw = f"{ST_MATCH_ROOT}{match_id}{lane_id}{tick}".encode()
    return hashlib.sha256(raw).hexdigest()


def st_is_zero_address(addr: str) -> bool:
    if not addr or not addr.startswith("0x"):
        return True
    try:
        return int(addr, 16) == 0
    except ValueError:
        return True


def st_normalize_wallet(addr: str) -> str:
    if st_is_zero_address(addr):
        raise STx_ZeroDisallowed()
    if len(addr) != 42:
        raise STx_ZeroDisallowed()
    return addr


# ---------------------------------------------------------------------------
# Core engine
# ---------------------------------------------------------------------------


class ScopeTReticleArena:
    """Precision scope arena: lanes, calibration, matches, non-custodial scoring."""

    def __init__(
        self,
        range_master: str = ST_ADDRESS_A,
        spotter: str = ST_ADDRESS_D,
        oracle: str = ST_ADDRESS_C,
        fee_desk: str = ST_ADDRESS_E,
        beacon: str = ST_ADDRESS_G,
    ) -> None:
        self.store = ST_LedgerStore()
        self.store.range_master = st_normalize_wallet(range_master)
        self.store.spotter = st_normalize_wallet(spotter)
        self.store.oracle = st_normalize_wallet(oracle)
        self.store.fee_desk = st_normalize_wallet(fee_desk)
        self.store.beacon = st_normalize_wallet(beacon)

    def _tick(self) -> int:
        self.store.global_tick += 1
        return self.store.global_tick

    def _emit(self, name: str, a: str, b: str, payload: Dict[str, Any]) -> None:
        self.store.events.append(
            ST_ChainEvent(name, a, b, payload, self.store.global_tick)
        )

    def _require_range_master(self, caller: str) -> None:
        if caller != self.store.range_master:
            raise STx_RangeMasterOnly()

    def _require_spotter(self, caller: str) -> None:
        if caller != self.store.spotter:
            raise STx_SpotterDenied()

    def _require_oracle(self, caller: str) -> None:
        if caller != self.store.oracle:
            raise STx_OracleMismatch()

    def propose_range_master(self, caller: str, nominee: str) -> None:
        self._require_range_master(caller)
        self.store.pending_range_master = st_normalize_wallet(nominee)
        self._emit(
            "ScopeT_RolePending",
            caller,
            nominee,
            {"role": "range_master"},
        )

    def accept_range_master(self, nominee: str) -> None:
