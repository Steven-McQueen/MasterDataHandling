# Reviewer, descriptive, post hoc: prior 20-day ar_mkt return of SALES (Check 12 sample), real vs shifted, raw and date-demeaned.
import sys; import numpy as np, pandas as pd
from pathlib import Path
HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]          # repo root (this file is in 12) AddedChecks/review_B/)
sys.path.insert(0,str(REPO / "12) AddedChecks")); sys.path.insert(0,str(REPO / "10) Checks"))
from _common import R, P1, load_part2, shifted, pvals
from B5_roasted_taxloss import prior_return
import importlib.util
spec=importlib.util.spec_from_file_location("OA",str(REPO / "10) Checks" / "OptionalAnalyses.py")); OA=importlib.util.module_from_spec(spec); spec.loader.exec_module(OA)
d=load_part2(); tdays,mat=d["tdays"],d["mat"]
avail=np.isfinite(mat).astype(float)
ca=np.concatenate([np.zeros((mat.shape[0],1)),np.cumsum(avail,1)],1); cr=np.concatenate([np.zeros((mat.shape[0],1)),np.cumsum(np.nan_to_num(mat),1)],1)
keep=R.sample_tickers(mat,d["tickers"],tdays); rows=np.array([d["tickers"].index(t) for t in keep])
cs=np.array([np.nanmean(np.where((ca[rows,i]-ca[rows,max(i-20,0)])>=5,20*(cr[rows,i]-cr[rows,max(i-20,0)])/np.maximum(ca[rows,i]-ca[rows,max(i-20,0)],1),np.nan)) if i>=5 else np.nan for i in range(mat.shape[1]+1)])
s,_=OA.read_sales(); start=pd.Timestamp("2025-01-20"); L=558
s=s[(s.trade_date>=start)&(s.trade_date<start+pd.Timedelta(days=L))&s.ticker.isin(keep)].reset_index(drop=True)
trow=pd.Index(d["tickers"]).get_indexer(s.ticker); print("sales",len(s))
rec=[]
for _,w in d["worlds"].iterrows():
    dt=shifted(s.trade_date,w); i0=R.day0_index(dt,tdays); pr,_=prior_return(ca,cr,trow,i0)
    rec.append((np.nanmean(pr),np.nanmean(pr-cs[i0])))
a=np.array(rec)
for j,n in enumerate(["sales prior","sales prior, date-demeaned"]):
    pu,pl,_=pvals(a[:,j],a[0,j]); print(f"{n:28s} real {100*a[0,j]:+.2f}% shifted {100*a[1:,j].mean():+.2f}% p_upper {pu:.3f} p_lower {pl:.3f}")
