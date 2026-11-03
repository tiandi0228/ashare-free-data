"""Research-only scenario performance ledger; never certified returns or trades.

Only fully closed explicitly supplied hypothetical scenarios that pass BOTH
the offline fill replay and exact-final-bar plausibility join are included.
The series is sequential fixed-capital closed-trade P&L, NOT a time-weighted
market equity curve or a historically authenticated backtest.
"""
import argparse
import datetime as dt
import json
from pathlib import Path

from collector.ashare_trade_risk_preflight import D, money, strict_positive
from collector.p2_backtest_fill_evidence import join
from collector.p2_offline_fill_machine import simulation

PHASE="P2_OFFLINE_PERFORMANCE_LEDGER"
MAX_CASES=40

def evaluate(payload):
    base={"phase":PHASE,"status":"REJECTED","trade_gate":"BLOCKED",
          "orders":[],"executable_candidates":[],
          "buy_recommendations_authorized":False,
          "historical_PIT_verified":False,"simulated_fill_verified":False,
          "strategy_backtest_certified":False}
    def reject(reason):
        return dict(base,reason=reason)
    if not isinstance(payload,dict) or not isinstance(payload.get("cases"),list):
        return reject("MISSING_SCENARIOS")
    cases=payload["cases"]
    if not 1<=len(cases)<=MAX_CASES:
        return reject("EMPTY_OR_UNBOUNDED_SCENARIOS")
    try:
        initial=money(strict_positive(payload["initial_capital_cny"]))
        if initial< D("100.00"):
            return reject("INVALID_INITIAL_CAPITAL")
        cash_equity=initial
        peak=initial
        max_drawdown=D("0")
        pnl_rows=[]
        identifiers=set()
        previous_end=None
        for i,item in enumerate(cases):
            if not isinstance(item,dict) or not isinstance(item.get("id"),str) or not (
                1<=len(item["id"])<=64 and item["id"].isascii() and
                all(c.isalnum() or c in "_-" for c in item["id"])):
                return reject("INVALID_CASE_ID")
            if item["id"] in identifiers:
                return reject("DUPLICATE_CASE_ID")
            identifiers.add(item["id"])
            s=item.get("scenario")
            bars=item.get("bars")
            if not isinstance(s,dict) or not isinstance(s.get("events"),list):
                return reject("INVALID_SCENARIO")
            if s.get("initial_cash_cny") != str(initial):
                return reject("CAPITAL_BASELINE_MISMATCH")
            if join(s,bars).get("status")!="STRUCTURAL_REPLAY_PLAUSIBLE_NOT_EXECUTABLE":
                return reject("FILL_BAR_EVIDENCE_NOT_PLAUSIBLE")
            replay=simulation(s)
            if replay.get("status")!="OFFLINE_SCENARIO_REPLAYED_NOT_EXECUTABLE":
                return reject("OFFLINE_REPLAY_REJECTED")
            if replay.get("remaining_shares")!=0 or replay.get("open_simulated_order") is not None:
                return reject("INCOMPLETE_POSITION_OR_ORDER")
            events=s["events"]
            buy=[e for e in events if e["type"]=="BUY_FILL"]
            sell=[e for e in events if e["type"]=="SELL_FILL"]
            if not buy or not sell or sum(e["shares"] for e in buy)!=sum(e["shares"] for e in sell):
                return reject("NO_FULLY_CLOSED_ROUND_TRIP")
            # No exit intent -> not a validated strategy exit, even if explicit
            # sell fills were supplied.
            if not replay.get("exit_intent_observed"):
                return reject("EXIT_REASON_NOT_RECORDED")
            begin=min(e["date"] for e in buy)
            end=max(e["date"] for e in sell)
            if previous_end is not None and begin<=previous_end:
                return reject("OVERLAPPING_OR_UNORDERED_CASES")
            previous_end=end
            final=D(replay["remaining_cash_cny"])
            pnl=money(final-initial)
            cash_equity=money(cash_equity+pnl)
            peak=max(peak,cash_equity)
            dd=(peak-cash_equity)/peak
            max_drawdown=max(max_drawdown,dd)
            pnl_rows.append({
                "id":item["id"],"code":s["code"],
                "entry_day":begin,"exit_day":end,
                "net_pnl_cny":str(pnl),
                "return_on_fixed_initial_capital_pct":str(
                    (100*pnl/initial).quantize(D("0.0001"))),
                "closed_trade_equity_cny":str(cash_equity),
            })
        winners=[D(v["net_pnl_cny"]) for v in pnl_rows if D(v["net_pnl_cny"])>0]
        losers=[D(v["net_pnl_cny"]) for v in pnl_rows if D(v["net_pnl_cny"])<0]
        net=money(sum((D(v["net_pnl_cny"]) for v in pnl_rows),D("0")))
        return dict(base,status="OFFLINE_CLOSED_SCENARIOS_ONLY_NOT_CERTIFIED",
                    case_count=len(pnl_rows),win_count=len(winners),
                    loss_count=len(losers),flat_count=len(pnl_rows)-len(winners)-len(losers),
                    win_rate_pct=str((D(100)*len(winners)/len(pnl_rows)).quantize(D("0.01"))),
                    net_pnl_cny=str(net),
                    fixed_capital_return_pct=str((D(100)*net/initial).quantize(D("0.0001"))),
                    max_closed_trade_drawdown_pct=str((D(100)*max_drawdown).quantize(D("0.0001"))),
                    profit_factor=(str((sum(winners)/-sum(losers)).quantize(D("0.0001")))
                                   if losers else None),
                    profit_factor_reason=("NO_LOSING_CLOSED_SCENARIOS" if not losers else None),
                    realized_equity_curve=pnl_rows,
                    limitations=[
                        "HYPOTHETICAL_USER_SUPPLIED_FILLS_NOT_EXCHANGE_ATTESTED",
                        "NO_DAILY_MARK_TO_MARKET_OR_UNREALIZED_DRAWDOWN",
                        "NO_INDEPENDENT_BAR_PROVENANCE_OR_PIT_VERIFICATION",
                        "SEQUENTIAL_FIXED_CAPITAL_NONOVERLAPPING_CASES_ONLY",
                        "NOT_AN_OUT_OF_SAMPLE_STRATEGY_RESULT",
                    ])
    except (ValueError,TypeError,KeyError,ArithmeticError,OverflowError):
        return reject("INVALID_OR_INCONSISTENT_SCENARIO_EVIDENCE")

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--input",required=True)
    p.add_argument("--out",required=True)
    a=p.parse_args()
    try:result=evaluate(json.loads(Path(a.input).read_text()))
    except (OSError,ValueError,UnicodeError):result=evaluate(None)
    dest=Path(a.out);dest.parent.mkdir(parents=True,exist_ok=True)
    dest.write_text(json.dumps(result,ensure_ascii=False,indent=2)+"\n")
    print(json.dumps({"status":result["status"],"trade_gate":"BLOCKED",
                      "reason":result.get("reason")},ensure_ascii=False))
if __name__=="__main__":main()
