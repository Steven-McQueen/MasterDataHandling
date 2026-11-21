import sys, warnings; import numpy as np, pandas as pd
from pathlib import Path
HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]          # repo root (this file is in 12) AddedChecks/review_B/)
sys.path.insert(0, str(REPO / "7) Part1b_Talk")); import TalkSettings as T
import pyfixest as pf
panel=pd.read_csv(T.PANEL_FILE, parse_dates=["date"])
tickers=list(panel.ticker.unique()); days=pd.DatetimeIndex(panel.date.unique())
y=panel.n_direct.to_numpy().reshape(len(tickers),len(days))
tk=y.sum(1)>0; dk=y.sum(0)>0
pur,_=T.read_purchases(); w=T.read_worlds().iloc[0]
dates=T.shift_dates(pur["Traded"], int(w.shift_days), w.shift_start, int(w.L))
lots,amt=T.purchase_matrix(pur,dates,tickers,days); tr=T.treatments(lots,amt)
x=tr["recent_10"]
df=pd.DataFrame({"ticker":np.repeat(np.array(tickers)[tk],dk.sum()),"date":np.tile(days[dk],tk.sum()),
  "n":y[np.ix_(tk,dk)].ravel(),"x":x[np.ix_(tk,dk)].ravel()}); df["y"]=(df.n>0).astype(float)
with warnings.catch_warnings():
    warnings.simplefilter("ignore")
    for f,m in [("y ~ x | ticker + date","lpm indicator"),("n ~ x | ticker + date","lpm count")]:
        r=pf.feols(f,data=df,vcov={"CRV1":"ticker+date"}); print(m,"Poisson sample",r.coef().iloc[0]*100,"pp p",r.pvalue().iloc[0], r._N)
    r=pf.fepois("y ~ x | ticker + date",data=df,vcov={"CRV1":"ticker+date"}); print("poisson indicator",r.coef().iloc[0],r.pvalue().iloc[0])
    r=pf.fepois("n ~ x | ticker + date",data=df,vcov={"CRV1":"ticker+date"}); print("poisson count",r.coef().iloc[0],r.pvalue().iloc[0])
print("max count",df.n.max(),"share >1 among positives",(df.n>1).sum()/(df.n>0).sum())
