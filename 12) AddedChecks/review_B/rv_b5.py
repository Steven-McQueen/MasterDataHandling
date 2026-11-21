"""
Reviewer check of B5 (written before running; post hoc, after B5 was seen).
(1) Where does the Roasted excess sit? Purchases split, in each world, by the sign of the
    prior 20-trading-day ar_mkt return (B5's definition) and by |prior| above/below 5%.
    Count Roasted hits per bin, real vs shifted. Tax-loss reading (falls) predicts the
    excess in the prior<0 bin.
(2) Recent sale of the same stock: flag purchases preceded by a sale of the same ticker in
    the 60 calendar days before the trade date (whole trading record moves with the shift,
    so the flag is fixed per purchase). Also 'loss sale': that sale's price below the price
    at the last purchase of the ticker before it (raw return compounded). Count Roasted hits
    among flagged and unflagged, real vs shifted.
(3) 'All purchases follow falls': B5's S_all with the prior return demeaned by the
    cross-sectional mean prior return of the 1,502 sample tickers on the same day 0; and
    with ar_capm in place of ar_mkt.
"""
import sys; from pathlib import Path
import numpy as np, pandas as pd
HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]          # repo root (this file is in 12) AddedChecks/review_B/)
sys.path.insert(0, str(REPO / "12) AddedChecks"))
from _common import R, P1, load_part2, part1_count_cums, shifted, pvals
from B5_roasted_taxloss import prior_return
def cums_of(mat):
    avail=np.isfinite(mat).astype(float)
    ca=np.concatenate([np.zeros((mat.shape[0],1)),np.cumsum(avail,1)],1)
    cr=np.concatenate([np.zeros((mat.shape[0],1)),np.cumsum(np.nan_to_num(mat),1)],1)
    return ca,cr
d=load_part2(); p,tdays,mat,tid,trow=d["p"],d["tdays"],d["mat"],d["tid"],d["trow"]
ca,cr=cums_of(mat)
keep=sorted(set(p.ticker)); samp_rows=np.array([d["tickers"].index(t) for t in R.sample_tickers(mat,d["tickers"],tdays)])
# cross-sectional mean prior return per day index
nd=mat.shape[1]; cs=np.full(nd+1,np.nan)
for i0 in range(nd+1):
    lo=max(i0-20,0); n=ca[samp_rows,i0]-ca[samp_rows,lo]; s=cr[samp_rows,i0]-cr[samp_rows,lo]
    with np.errstate(all="ignore"): v=np.where(n>=5,20*s/n,np.nan)
    cs[i0]=np.nanmean(v) if np.isfinite(v).any() else np.nan
matc,_,_,_,_=R.read_returns("ar_capm"); cac,crc=cums_of(matc)
cums,cdays=part1_count_cums(d["posts"],d["lab_tickers"],["direct_neg50"])
# sales flags (fixed per purchase)
import importlib.util
spec=importlib.util.spec_from_file_location("OA",str(REPO / "10) Checks" / "OptionalAnalyses.py")); OA=importlib.util.module_from_spec(spec)
sys.path.insert(0,str(REPO / "10) Checks")); spec.loader.exec_module(OA)
sales,_=OA.read_sales()
raw,_,_,_,_=R.read_returns("ret"); lp=np.concatenate([np.zeros((raw.shape[0],1)),np.cumsum(np.log1p(np.nan_to_num(raw)),1)],1)
tix={t:i for i,t in enumerate(d["tickers"])}
pa=R.read_purchases()  # all purchases for 'last purchase before sale'
sale60=np.zeros(len(p),bool); loss60=np.zeros(len(p),bool)
sg={t:g.trade_date.values for t,g in sales.groupby("ticker")}
pg={t:np.sort(g.trade_date.values) for t,g in pa.groupby("ticker")}
for k,r in enumerate(p.itertuples()):
    sd=sg.get(r.ticker)
    if sd is None: continue
    m=(sd<np.datetime64(r.trade_date))&(sd>=np.datetime64(r.trade_date-pd.Timedelta(days=60)))
    if not m.any(): continue
    sale60[k]=True
    if r.ticker not in tix: continue
    row=tix[r.ticker]
    for s in sd[m]:
        prev=pg[r.ticker][pg[r.ticker]<s]
        if len(prev)==0: continue
        i_b=tdays.searchsorted(pd.Timestamp(prev[-1])); i_s=tdays.searchsorted(pd.Timestamp(s))
        # log price change from close of purchase day to close of sale day
        if lp[row,i_s+1]-lp[row,i_b+1] < 0: loss60[k]=True
print(f"purchases with a sale of the same ticker in the 60 days before: {sale60.sum()} of {len(p)}; at a loss vs last purchase: {loss60.sum()}")
recs=[]
for _,w in d["worlds"].iterrows():
    dates=shifted(p["trade_date"],w); i0=R.day0_index(dates,tdays); day0,end=P1.windows(dates,tdays)
    ro=P1.window_counts(cums["direct_neg50"],tid,day0,end,cdays)>0
    pr,_=prior_return(ca,cr,trow,i0); prc,_=prior_return(cac,crc,trow,i0)
    dm=pr-cs[i0]
    rec={"world":int(w.world),"ro":ro.sum(),
         "ro_neg":(ro&(pr<0)).sum(),"ro_pos":(ro&(pr>=0)).sum(),"n_neg":(pr<0).sum(),
         "ro_big":(ro&(np.abs(pr)>0.05)).sum(),"ro_small":(ro&(np.abs(pr)<=0.05)).sum(),
         "ro_sale":(ro&sale60).sum(),"ro_nosale":(ro&~sale60).sum(),"ro_loss":(ro&loss60).sum(),
         "S_all":np.nanmean(pr),"S_all_dm":np.nanmean(dm),"S_all_capm":np.nanmean(prc),"cs_at_purchases":np.nanmean(cs[i0]),
         "S_ro_dm":np.nanmean(dm[ro])}
    recs.append(rec)
ws=pd.DataFrame(recs); ws.to_csv(HERE / "rv_b5_worlds.csv",index=False)
real=ws.iloc[0]; sh=ws.iloc[1:]
for c in ws.columns[1:]:
    pu,pl,p2=pvals(ws[c],real[c])
    print(f"{c:16s} real {real[c]:10.4f} shifted {sh[c].mean():10.4f} excess {real[c]-sh[c].mean():+9.4f} p_upper {pu:.3f} p_lower {pl:.3f}")
# ---- extra: shares, n_big, by ticker
print("---- extra")
recs=[]; byt=[]
for _,w in d["worlds"].iterrows():
    dates=shifted(p["trade_date"],w); i0=R.day0_index(dates,tdays); day0,end=P1.windows(dates,tdays)
    ro=P1.window_counts(cums["direct_neg50"],tid,day0,end,cdays)>0
    pr,_=prior_return(ca,cr,trow,i0)
    recs.append({"world":int(w.world),"n_big":(np.abs(pr)>0.05).sum(),"share_sale":(ro&sale60).sum()/ro.sum(),
                 "rate_big":(ro&(np.abs(pr)>0.05)).sum()/(np.abs(pr)>0.05).sum(),"rate_small":(ro&(np.abs(pr)<=0.05)).sum()/(np.abs(pr)<=0.05).sum(),
                 "rate_neg":(ro&(pr<0)).sum()/(pr<0).sum(),"rate_pos":(ro&(pr>=0)).sum()/(pr>=0).sum()})
    byt.append(pd.Series(ro,index=p.ticker).groupby(level=0).sum().rename(int(w.world)))
ws=pd.DataFrame(recs); real=ws.iloc[0]; sh=ws.iloc[1:]
for c in ws.columns[1:]:
    pu,pl,p2=pvals(ws[c],real[c]); print(f"{c:12s} real {real[c]:.5f} shifted {sh[c].mean():.5f} p_upper {pu:.3f} p_lower {pl:.3f}")
bt=pd.concat(byt,axis=1).fillna(0); ex=(bt[0]-bt.iloc[:,1:].mean(1)).sort_values()
print("ticker excess (real - expected) top/bottom:"); print(ex.tail(8).round(2).to_string()); print(ex.head(5).round(2).to_string())
tot=bt.drop(index=["WBD"]).sum(); print("without WBD: real",tot[0],"expected",tot.iloc[1:].mean().round(1),"p_upper",(tot>=tot[0]).mean())
