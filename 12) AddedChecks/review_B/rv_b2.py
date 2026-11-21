import pandas as pd, numpy as np
from pathlib import Path
HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]          # repo root (this file is in 12) AddedChecks/review_B/)
d=pd.read_csv(REPO / "12) AddedChecks" / "out" / "B2_cumulative_treatments.csv")
e=pd.read_csv(REPO / "7) Part1b_Talk" / "3) Inference" / "world_estimates.csv")
m=d.merge(e[["world","direct|exposure|beta","direct|owned|beta","direct|recent_10|beta"]],on="world")
real=m[m.world==0].iloc[0]; sh=m[m.world!=0]
for t,x in [("owned","owned_share"),("exposure","exposure_mean"),("owned","first_purchase_day_mean"),("exposure","first_purchase_day_mean")]:
    y=sh[f"direct|{t}|beta"]; X=np.column_stack([np.ones(len(sh)),sh[x]])
    b,*_=np.linalg.lstsq(X,y,rcond=None); res=y-X@b
    pred=b[0]+b[1]*real[x]; rr=real[f"direct|{t}|beta"]-pred
    print(f"{t:9s} on {x:24s} corr {np.corrcoef(sh[x],y)[0,1]:+.3f}; real {real[f'direct|{t}|beta']:.3e} pred {pred:.3e}; resid p_lower {(np.r_[res,rr]<=rr).mean():.3f}")
# small-shift worlds
for lo,hi in [(30,60),(30,90),(468,528),(30,528)]:
    s=sh[(sh.shift_days>=lo)&(sh.shift_days<=hi)]
    for t in ["exposure","owned","recent_10"]:
        c=f"direct|{t}|beta"; r=real[c]
        print(f"shift {lo}-{hi} n={len(s)} {t:9s} real {r:.3e} mean {s[c].mean():.3e} p_lower {(np.r_[s[c],r]<=r).mean():.3f}")
# also shift 528 near-symmetric: worlds with large shifts s ~ L-30 are like small negative shifts
