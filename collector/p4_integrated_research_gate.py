"""Integrated P4 research receipt: combine independent checks, never authorize orders."""
import argparse,json
from pathlib import Path
from collector.p4_execution_arithmetic import replay
from collector.p4_exit_decision import exit_assessment
from collector.p4_calendar_limit_gate import check_execution
from collector.p4_signal_fill_audit import assess as audit_signals

def verify(fixture):
    if fixture.get("trade_gate")!="BLOCKED" or fixture.get("orders")!=[]:
        raise ValueError("upstream trade gate violated")
    cost=replay(**fixture["cost"])
    exit_gate=exit_assessment(**fixture["exit"])
    calendar=check_execution(**fixture["calendar"])
    chronology=audit_signals(fixture["signals"])
    if any(x["trade_gate"]!="BLOCKED" or x["orders"]!=[] for x in (cost,exit_gate,calendar,chronology)):
        raise ValueError("downstream gate violation")
    return {"phase":"P4_INTEGRATED_RESEARCH_ONLY","checks":{
        "cost_and_Tplus1":True,"exit_conflict_no_phantom_fill":not exit_gate["recorded_fill"],
        "calendar_limit_no_phantom_fill":not calendar["recorded_fill"],
        "signal_return_exclusion":not chronology["returns_computed"]},
        "signal_count":chronology["signal_count"],"unfilled_signal_count":chronology["unfilled_signal_count"],
        "strategy_backtest_completed":False,"historical_OOS_validated":False,
        "trade_gate":"BLOCKED","orders":[],"executable_candidates":[]}

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--fixture",required=True);p.add_argument("--out",required=True)
    args=p.parse_args()
    result=verify(json.loads(Path(args.fixture).read_text()))
    target=Path(args.out);target.parent.mkdir(parents=True,exist_ok=True)
    target.write_text(json.dumps(result,indent=2)+"\n")
    print(json.dumps(result))
if __name__=="__main__":main()
