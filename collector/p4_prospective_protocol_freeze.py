"""Create a prospective P4 research protocol fingerprint, never trading permission.

A locally declared creation timestamp and SHA are *claims*, not independent
proof of time, frozen execution policy, point-in-time data, or broker fills.
"""
import hashlib
import json
import re
from datetime import date, datetime, timezone
from decimal import Decimal, InvalidOperation

SHA40 = re.compile(r"[0-9a-f]{40}\Z")
SHA64 = re.compile(r"[0-9a-f]{64}\Z")
PHASE = "P4_PROSPECTIVE_RESEARCH_PROTOCOL_FREEZE"


def _decimal(value, *, positive=False):
    if not isinstance(value, str) or not re.fullmatch(r"(?:0|[1-9][0-9]*)(?:\.[0-9]+)?", value):
        raise ValueError("noncanonical numeric assumption")
    number = Decimal(value)
    if not number.is_finite() or (positive and number <= 0):
        raise ValueError("invalid numeric assumption")
    return number


def freeze(*, source_commit, baseline_artifact_sha256, created_at_utc,
           window_start, window_end, strategy_id, fee_model, strategy_rules):
    base = {
        "phase": PHASE, "status": "REJECTED",
        "historical_PIT_verified": False, "historical_OOS_validated": False,
        "prospective_freeze_externally_attested": False,
        "fees_observed_in_real_trades": False, "broker_fills_verified": 0,
        "trade_authorized": False, "trade_gate": "BLOCKED",
        "orders": [], "executable_candidates": [], "actionable_buy_signals": [],
    }
    def reject(reason):
        return dict(base, reason=reason)
    try:
        if (not isinstance(source_commit, str) or not SHA40.fullmatch(source_commit)
            or not isinstance(baseline_artifact_sha256, str)
            or not SHA64.fullmatch(baseline_artifact_sha256)):
            return reject("SOURCE_NOT_IMMUTABLY_PINNED")
        if not isinstance(strategy_id, str) or not re.fullmatch(r"[A-Z][A-Z0-9_]{3,63}", strategy_id):
            return reject("INVALID_STRATEGY_ID")
        if not isinstance(created_at_utc, str) or not re.fullmatch(
            r"[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}Z", created_at_utc
        ):
            return reject("CREATION_INSTANT_NOT_CANONICAL_UTC")
        created = datetime.fromisoformat(created_at_utc.replace("Z", "+00:00"))
        if created.tzinfo != timezone.utc or created.isoformat(timespec="seconds").replace("+00:00", "Z") != created_at_utc:
            return reject("CREATION_INSTANT_NOT_CANONICAL_UTC")
        start, end = date.fromisoformat(window_start), date.fromisoformat(window_end)
        if (start.isoformat() != window_start or end.isoformat() != window_end
            or end <= start):
            return reject("INVALID_FUTURE_WINDOW")
        if created.date() >= start:
            return reject("RETROSPECTIVE_OR_SAME_DAY_FREEZE")
        fields = ("commission_rate", "commission_min_cny", "sell_stamp_rate",
                  "slippage_bps_each_side", "capital_cny", "maximum_net_loss_fraction",
                  "minimum_net_reward_risk")
        if not isinstance(fee_model, dict) or set(fee_model) != set(fields):
            return reject("FEE_MODEL_FIELDS_NOT_FROZEN")
        values = {k: _decimal(fee_model[k], positive=k in (
            "commission_min_cny", "capital_cny", "maximum_net_loss_fraction",
            "minimum_net_reward_risk")) for k in fields}
        if (values["commission_rate"] >= 1 or values["sell_stamp_rate"] >= 1
            or values["slippage_bps_each_side"] >= 10000
            or values["maximum_net_loss_fraction"] > 1):
            return reject("UNSAFE_FEE_OR_RISK_ASSUMPTION")
        # A cost-only fingerprint is not a frozen strategy: lock every
        # entry/exit, timing and barrier input that determines a candidate.
        rule_fields = {
            "signal_rule", "entry_rule", "stop_fraction", "target_fraction",
            "min_holding_sessions", "max_holding_sessions",
            "friday_exit_rule", "same_day_sale_allowed",
        }
        if not isinstance(strategy_rules, dict) or set(strategy_rules) != rule_fields:
            return reject("STRATEGY_RULES_NOT_COMPLETELY_FROZEN")
        if (strategy_rules["signal_rule"] != "COMPLETED_CLOSE_CROSSES_ABOVE_MA20"
            or strategy_rules["entry_rule"] != "NEXT_VENDOR_OPEN_PROXY_NOT_FILL"
            or strategy_rules["friday_exit_rule"] != "FRIDAY_FORCE_EXIT_RESEARCH_ONLY"
            or strategy_rules["same_day_sale_allowed"] is not False):
            return reject("UNSAFE_OR_UNKNOWN_STRATEGY_RULES")
        if (type(strategy_rules["min_holding_sessions"]) is not int
            or type(strategy_rules["max_holding_sessions"]) is not int
            or not 1 <= strategy_rules["min_holding_sessions"]
                 <= strategy_rules["max_holding_sessions"] <= 5):
            return reject("INVALID_HOLDING_WINDOW")
        stop = _decimal(strategy_rules["stop_fraction"], positive=True)
        target = _decimal(strategy_rules["target_fraction"], positive=True)
        if stop >= 1 or target >= 1:
            return reject("INVALID_BARRIER_FRACTIONS")
        # Detach mutable caller-owned dictionaries before hashing and returning.
        # Otherwise callers can mutate displayed frozen fields without moving SHA.
        fees_snapshot = dict(fee_model)
        rules_snapshot = dict(strategy_rules)
        fixed = {
            "schema_version": 2, "strategy_id": strategy_id,
            "frozen_strategy_rules": rules_snapshot,
            "source_commit": source_commit,
            "negative_baseline_artifact_sha256": baseline_artifact_sha256,
            "claimed_created_at_utc": created_at_utc,
            "window_start": window_start, "window_end": window_end,
            "fee_model_assumptions_not_observed": fees_snapshot,
            "minimum_lot_shares": 100, "signal_use": "RESEARCH_ONLY",
            "trade_gate": "BLOCKED",
        }
        digest = hashlib.sha256(json.dumps(
            fixed, sort_keys=True, ensure_ascii=False, separators=(",", ":")
        ).encode()).hexdigest()
        return dict(base, status="CANDIDATE_FINGERPRINT_ONLY_NOT_OOS",
                    candidate_sha256=digest, candidate=fixed,
                    missing_evidence=[
                        "INDEPENDENT_PRE_WINDOW_COMMIT_AND_TIMESTAMP_ATTESTATION",
                        "PROSPECTIVE_UNTOUCHED_HOLDOUT_RESULTS",
                        "HISTORICAL_PIT_ISSUER_AND_TRADING_CALENDAR_AUTHENTICATION",
                        "REAL_BROKER_EXECUTION_FEE_AND_FILL_PROOF",
                    ])
    except (TypeError, ValueError, InvalidOperation, OverflowError):
        return reject("INVALID_PROTOCOL_INPUT")
