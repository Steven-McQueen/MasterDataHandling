# Reviewer, post hoc: Roasted hits after purchases, split by whether a Roasted post about the company fell in trading days -10..-1 (Check 11 window).
import sys; import numpy as np, pandas as pd
from pathlib import Path
HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]          # repo root (this file is in 12) AddedChecks/review_B/)
sys.path.insert(0,str(REPO / "12) AddedChecks"))
from _common import R, P1, load_part2, part1_count_cums, shifted, pvals
d=load_part2(); p,tdays,tid=d["p"],d["tdays"],d["tid"]
cums,cdays=part1_count_cums(d["posts"],d["lab_tickers"],["direct_neg50"]); cum=cums["direct_neg50"]
rec=[]
for _,w in d["worlds"].iterrows():
    dates=shifted(p["trade_date"],w); day0,end=P1.windows(dates,tdays)
    i0=tdays.searchsorted(day0); start=tdays[np.maximum(i0-10,0)]
    after=P1.window_counts(cum,tid,day0,end,cdays)>0
    c0=cdays.get_indexer(start); c1=cdays.get_indexer(day0)   # [start, day0)
    c0=np.where(c0<0,0,c0); before=(cum[tid,c1]-cum[tid,c0])>0
    rec.append((after.sum(),(after&before).sum(),(after&~before).sum(),before.sum()))
a=np.array(rec,float)
for j,n in enumerate(["Roasted after (all)","after & Roasted before","after & none before","purchases with Roasted before"]):
    pu,pl,_=pvals(a[:,j],a[0,j]); print(f"{n:32s} real {a[0,j]:7.0f} expected {a[1:,j].mean():8.1f} p_upper {pu:.3f} p_lower {pl:.3f}")
