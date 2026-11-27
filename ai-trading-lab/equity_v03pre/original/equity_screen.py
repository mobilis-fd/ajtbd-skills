"""Offline exploratory ETF event screen. No broker or network access."""
import argparse, hashlib, json
from pathlib import Path
import numpy as np
import pandas as pd

SYMS = ['SPY','IEF','TLT']
COSTS = [0,5,10,25,40]
PERIODS = {'T3':('2003-01-01','2016-12-31'), 'T2':('2017-10-01','2024-04-30'), 'T1':('2024-06-01','2026-10-31')}
SEED=20261127

def load(folder):
    def dates(frame):
        d=pd.DatetimeIndex(pd.to_datetime(frame.pop('date'),format='%Y-%m-%d',errors='raise'))
        if d.has_duplicates or not d.is_monotonic_increasing: raise ValueError('Dates must be unique and sorted')
        frame.index=d
        return frame
    cal=dates(pd.read_csv(folder/'sessions.csv')).index
    if len(cal)==0 or cal[0]>pd.Timestamp('2002-12-31') or cal[-1]<pd.Timestamp('2026-11-05'):
        raise ValueError('Supply calendar and prices including Dec 2002 and first week Nov 2026')
    data={}
    for s in SYMS:
        f=dates(pd.read_csv(folder/f'{s}.csv'))
        f=f.loc[:,['adj_open','adj_close']].astype(float)
        if not f.index.equals(cal): raise ValueError(f'{s}: session coverage mismatch; no filling permitted')
        if not np.isfinite(f.values).all() or (f.values<=0).any(): raise ValueError(f'{s}: invalid price')
        data[s]=f
    return cal,data

def events(cal,data):
    months=cal.to_period('M'); rows=[]
    def ret(s,i,j): return data[s].adj_close.iloc[j]/data[s].adj_open.iloc[i]-1
    def add(name,s,i,j,month,ctrl):
        # Require the entire event and comparison windows to fit the reporting segment later.
        rows.append(dict(hypothesis=name,month=str(month),symbol=s,entry=cal[i],exit=cal[j], gross=ret(s,i,j),control=ctrl))
    for m in months.unique():
        ids=np.flatnonzero(months==m)
        if len(ids)<15 or ids[0]==0: continue
        a,b=int(ids[0]),int(ids[-1]); i=b-4
        if b+3>=len(cal):continue
        # SA01: prior month-end to close before entry. Buy relative laggard; no shorts.
        r={s:data[s].adj_close.iloc[i-1]/data[s].adj_close.iloc[a-1]-1 for s in ['SPY','IEF']}
        selected=min(r,key=r.get)
        add('EQ01',selected,i,b,m,(ret('SPY',i,b)+ret('IEF',i,b))/2)
        # Same asset, all feasible four-session windows starting in anchor month;
        # comparison may include the event itself; no cherry-picked random dates.
        add('EQ02','SPY',b,b+3,m,np.mean([ret('SPY',k,k+3) for k in range(a,b+1)]))
        add('EQ03','TLT',i,b,m,np.mean([ret('TLT',k,k+4) for k in range(a,b-3)]))
    return pd.DataFrame(rows)

def bootstrap(values,block,seed):
    # Circular block bootstrap of monthly paired differences. Descriptive only;
    # assumptions include local stationarity and weak dependence.
    x=np.asarray(values,float); n=len(x)
    if n<max(24,2*block):return (None,None,None)
    rng=np.random.default_rng(seed)
    idx=(rng.integers(0,n,size=(4000,int(np.ceil(n/block)),1))+np.arange(block))%n
    means=x[idx.reshape(4000,-1)[:,:n]].mean(axis=1)
    p=(1+np.count_nonzero(means-x.mean()>=x.mean()))/(len(means)+1)
    lo,hi=np.quantile(means,[.025,.975]);return float(lo),float(hi),float(p)

def summarize(ev):
    out=[]
    for label,(start,end) in PERIODS.items():
        for name in ['EQ01','EQ02','EQ03']:
            # EQ02 controls can extend to first 3 sessions of next month; anchor months
            # crossing regime boundaries are excluded by the event exit check.
            e=ev[(ev.hypothesis==name)&(ev.entry>=start)&(ev.exit<=end)]
            if not len(e):continue
            g=e.gross.to_numpy(); c=e.control.to_numpy(); d=g-c
            # Fee on entry and exit notional; returns per dollar entry notional.
            row={'period':label,'hypothesis':name,'months':len(e),'gross_bps':float(g.mean()*1e4), 'control_bps':float(c.mean()*1e4),'delta_bps':float(d.mean()*1e4),'break_even_rt_bps':float(2*g.mean()/(2+g.mean())*1e4),'positive_month_fraction':float((g>0).mean())}
            for cost in COSTS:
                f=cost/20000;net=g-f*(2+g);ctrl=c-f*(2+c)
                row[f'net_{cost}bps']=float(net.mean()*1e4);row[f'delta_{cost}bps']=float((net-ctrl).mean()*1e4)
            for block in (3,6,12):
                lo,hi,p=bootstrap(d*1e4,block,SEED+block)
                row[f'delta_ci_{block}m']=[lo,hi];row[f'p_{block}m']=p
            out.append(row)
    # Holm across all reported 6-month-block primary comparisons, descriptive historical only.
    valid=sorted([r for r in out if r['p_6m'] is not None],key=lambda r:r['p_6m']);prev=0
    for i,r in enumerate(valid):
        prev=max(prev,min(1,(len(valid)-i)*r['p_6m']));r['holm_p_6m']=prev
    return out

def self_test():
    cal=pd.bdate_range('2002-12-02','2026-11-10'); data={s:pd.DataFrame({'adj_open':100.,'adj_close':100.},index=cal) for s in SYMS}
    e=events(cal,data); assert len(e)>800 and (e.gross==0).all() and (e.control==0).all()
    results=summarize(e);assert len(results)==9
    assert all(abs(r['net_25bps']+25)<1e-8 for r in results)
    assert all(r['break_even_rt_bps']==0 for r in results)
    a=e[(e.hypothesis=='EQ02')&(e.month=='2024-06')].iloc[0]
    assert a.entry==pd.Timestamp('2024-06-28') and a.exit==pd.Timestamp('2024-07-03') # synthetic weekdays only
    # Future mutation cannot change EQ01 asset choice for anchor month.
    orig=e[(e.hypothesis=='EQ01')&(e.month=='2024-06')].iloc[0]
    data['IEF'].loc[orig.entry:,'adj_close']=200
    after=events(cal,data);new=after[(after.hypothesis=='EQ01')&(after.month=='2024-06')].iloc[0]
    assert orig.symbol==new.symbol
    # Bootstrap on constants, fee calculation, boundary handling.
    assert bootstrap(np.zeros(40),6,SEED)==(0.,0.,1.)
    assert all(r['months']>0 for r in results)
    print('PASS: flat prices/costs; event calendar; future mutation; bootstrap; split summaries (synthetic only)')

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--self-test',action='store_true');p.add_argument('--data',type=Path);p.add_argument('--out',type=Path)
    a=p.parse_args()
    if a.self_test:self_test();return
    if not a.data or not a.out:p.error('--data and --out required')
    cal,data=load(a.data);ev=events(cal,data);results=summarize(ev)
    a.out.mkdir(parents=True,exist_ok=False)
    ev.to_csv(a.out/'events_exploratory.csv',index=False)
    manifest={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in [a.data/'sessions.csv',*[a.data/f'{s}.csv' for s in SYMS],Path(__file__)]}
    (a.out/'summary.json').write_text(json.dumps({'status':'historical exploratory screen; no holdout or trading approval','input_sha256':manifest,'results':results},indent=2),encoding='utf8')
    print('Wrote exploratory results to',a.out)
if __name__=='__main__':main()
