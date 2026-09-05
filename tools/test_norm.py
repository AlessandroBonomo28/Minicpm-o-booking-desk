#!/usr/bin/env python3
"""Batteria di test del normalizzatore/verificatore del gateway (ore, date, giorni). Senza GPU, senza servizi.
  python3 tools/test_norm.py"""
import re, sys, os
src = open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "gateway.py")).read(); ns = {"re": re}
exec(src[src.index("_MONTHS = ["):src.index("def _hud_time_span")], ns)
T = ns["_hud_norm_time"]; D = ns["_hud_norm_date"]; TV = ns["_hud_time_valid"]
cases_time = [("15:00", "15:00"), ("09:30", "09:30"), ("3 p.m.", "15:00"), ("3 P.M.", "15:00"), ("3pm", "15:00"), ("3 pm", "15:00"), ("7 p.m.", "19:00"),
              ("15", "15:00"), ("19", "19:00"), ("3", "15:00"), ("9 am", "09:00"), ("12:02", "12:02"), ("10.30", "10:30"), ("10.30 pm", "22:30"),
              ("7 o'clock", "19:00"), ("nine", "09:00"), ("nine thirty", "09:30"), ("half past ten", "10:30"), ("quarter past nine", "09:15"),
              ("three in the afternoon", "15:00"), ("noon", "12:00"), ("at 15", "15:00"), ("3-17", "15:00-17:00"), ("15:00-17:00", "15:00-17:00"),
              ("", "all-day"), ("all day", "all-day"), ("6:00 PM", "18:00"), ("6 p.m", "18:00")]
bad_time = ["soonish", "tomorrow", "of", "time", "the second", "3 p:m:"]
cases_date = [("April 20th", "april 20"), ("the second of April", "april 2"), ("2 April", "april 2"), ("april", "april"), ("twenty-first of may", "may 21"), ("March 31st", "march 31")]
ok = 0; n = 0
for x, want in cases_time:
    n += 1; got = T(x)
    if got == want and TV(got, "check"): ok += 1
    else: print(f"  FAIL time {x!r}: atteso {want!r}, ottenuto {got!r}")
for x in bad_time:
    n += 1; got = T(x)
    if not TV(got, "book"): ok += 1
    else: print(f"  FAIL time {x!r} doveva essere respinto, ottenuto {got!r}")
for x, want in cases_date:
    n += 1; got = D(x)
    if got == want: ok += 1
    else: print(f"  FAIL date {x!r}: atteso {want!r}, ottenuto {got!r}")
print(f"{ok}/{n} normalizzazioni corrette"); sys.exit(0 if ok == n else 1)
