"""Five-fold walk-forward comparison: global LSTM vs per-SKU LSTMs.
Run from ml-services/demand-forecast/lstm: python -m src.walk_forward_comparison
"""
import copy, json, random, time
from pathlib import Path
import numpy as np
import pandas as pd
import torch
from torch import nn
from torch.utils.data import DataLoader, TensorDataset
from sklearn.preprocessing import StandardScaler
from src.global_model import GlobalDemandLSTM

DATA=Path('data/global_sku_demand_synthetic.csv'); OUT=Path('output')
LOOKBACK=45; HORIZON=7; FOLDS=5; EPOCHS=50; PATIENCE=8; BATCH=32; MIN_TRAIN=20; SEED=42

class PerSKUModel(nn.Module):
    def __init__(self, input_size=4, hidden_size=64, num_layers=2, horizon=7, dropout=.2):
        super().__init__()
        self.lstm=nn.LSTM(input_size,hidden_size,num_layers,batch_first=True,dropout=dropout if num_layers>1 else 0.)
        self.head=nn.Sequential(nn.Linear(hidden_size,64),nn.ReLU(),nn.Dropout(dropout),nn.Linear(64,horizon))
    def forward(self,x):
        out,_=self.lstm(x); return self.head(out[:,-1,:])

def seed_all(seed):
    random.seed(seed); np.random.seed(seed); torch.manual_seed(seed)
    if torch.cuda.is_available(): torch.cuda.manual_seed_all(seed)

def score(a,p):
    a=np.asarray(a,dtype=float).reshape(-1); p=np.asarray(p,dtype=float).reshape(-1)
    if not len(a): return {'MAE':None,'RMSE':None,'MAPE_percent':None}
    e=p-a; nz=np.abs(a)>1e-8
    return {'MAE':float(np.mean(np.abs(e))),'RMSE':float(np.sqrt(np.mean(e**2))),
            'MAPE_percent':float(np.mean(np.abs(e[nz]/a[nz]))*100) if nz.any() else None}

def inv(s,x):
    x=np.asarray(x); shape=x.shape; return s.inverse_transform(x.reshape(-1,1)).reshape(shape)

def make_data(df, train_end, val_end, test_end):
    scaler=StandardScaler(); scaler.fit(df.loc[df.date<=train_end,['sales']])
    w=df.copy(); w['scaled_sales']=scaler.transform(w[['sales']]).ravel()
    dow=w.date.dt.dayofweek.astype(float); w['dow_sin']=np.sin(2*np.pi*dow/7); w['dow_cos']=np.cos(2*np.pi*dow/7)
    skus=sorted(w.sku_id.unique()); cats=sorted(w.category.unique()); whs=sorted(w.warehouse_id.unique())
    sm={v:i for i,v in enumerate(skus)}; cm={v:i for i,v in enumerate(cats)}; wm={v:i for i,v in enumerate(whs)}
    parts={k:[[],[],[],[],[]] for k in ('train','validation','test')}; counts={s:{k:0 for k in parts} for s in skus}
    for sku,g in w.groupby('sku_id',sort=True):
        g=g.sort_values('date').reset_index(drop=True); dates=g.date.to_numpy()
        features=g[['scaled_sales','promotion','dow_sin','dow_cos']].to_numpy(np.float32); targets=g.scaled_sales.to_numpy(np.float32)
        sid=sm[sku]; cid=cm[g.category.iloc[0]]; wid=wm[g.warehouse_id.iloc[0]]
        for i in range(LOOKBACK,len(g)-HORIZON+1):
            first=pd.Timestamp(dates[i]); last=pd.Timestamp(dates[i+HORIZON-1])
            if last<=train_end: split='train'
            elif first>train_end and last<=val_end: split='validation'
            elif first>val_end and last<=test_end: split='test'
            else: continue
            x,s,c,wh,y=parts[split]; x.append(features[i-LOOKBACK:i]); s.append(sid); c.append(cid); wh.append(wid); y.append(targets[i:i+HORIZON]); counts[sku][split]+=1
    def ds(p):
        x,s,c,wh,y=p
        if not x: return TensorDataset(torch.empty((0,LOOKBACK,4)),torch.empty(0,dtype=torch.long),torch.empty(0,dtype=torch.long),torch.empty(0,dtype=torch.long),torch.empty((0,HORIZON)))
        return TensorDataset(torch.tensor(np.asarray(x),dtype=torch.float32),torch.tensor(s),torch.tensor(c),torch.tensor(wh),torch.tensor(np.asarray(y),dtype=torch.float32))
    return {'train':ds(parts['train']),'validation':ds(parts['validation']),'test':ds(parts['test']),'scaler':scaler,'sku_map':sm,'counts':counts,'n_skus':len(sm),'n_cats':len(cm),'n_wh':len(wm)}

def fit(model,train_loader,val_loader,device,global_model):
    model.to(device); opt=torch.optim.Adam(model.parameters(),lr=.001); lossfn=nn.MSELoss(); best=copy.deepcopy(model.state_dict()); best_loss=float('inf'); wait=PATIENCE; t=time.perf_counter()
    for _ in range(EPOCHS):
        model.train()
        for b in train_loader:
            x=b[0].to(device)
            if global_model: ids=[z.to(device) for z in b[1:]]; y=ids.pop(); pred=model(x,*ids)
            else: y=b[1].to(device); pred=model(x)
            loss=lossfn(pred,y); opt.zero_grad(); loss.backward(); torch.nn.utils.clip_grad_norm_(model.parameters(),1.); opt.step()
        model.eval(); ls=[]
        with torch.no_grad():
            for b in val_loader:
                x=b[0].to(device)
                if global_model: ids=[z.to(device) for z in b[1:]]; y=ids.pop(); pred=model(x,*ids)
                else: y=b[1].to(device); pred=model(x)
                ls.append(lossfn(pred,y).item())
        vl=float(np.mean(ls)) if ls else float('inf')
        if vl<best_loss: best_loss=vl; best=copy.deepcopy(model.state_dict()); wait=PATIENCE
        else:
            wait-=1
            if wait<=0: break
    model.load_state_dict(best); return model,time.perf_counter()-t

def pred_global(model,ds,device,scaler):
    aa=[]; pp=[]; ss=[]; model.eval()
    with torch.no_grad():
        for x,s,c,w,y in DataLoader(ds,batch_size=128):
            pp.append(model(x.to(device),s.to(device),c.to(device),w.to(device)).cpu().numpy()); aa.append(y.numpy()); ss.append(s.numpy())
    if not aa: return np.array([]),np.array([]),np.array([],dtype=int)
    return inv(scaler,np.concatenate(aa)),inv(scaler,np.concatenate(pp)),np.concatenate(ss)

def pred_sku(model,ds,device,scaler):
    aa=[]; pp=[]; model.eval()
    with torch.no_grad():
        for x,y in DataLoader(ds,batch_size=128): pp.append(model(x.to(device)).cpu().numpy()); aa.append(y.numpy())
    if not aa: return np.array([]),np.array([])
    return inv(scaler,np.concatenate(aa)),inv(scaler,np.concatenate(pp))

def main():
    if not DATA.exists(): raise FileNotFoundError(f'{DATA} not found; run from lstm folder')
    df=pd.read_csv(DATA); required={'date','sku_id','category','warehouse_id','sales','promotion'}
    if required-set(df.columns): raise ValueError(f'Missing columns: {sorted(required-set(df.columns))}')
    df['date']=pd.to_datetime(df.date); df['sales']=pd.to_numeric(df.sales); df['promotion']=pd.to_numeric(df.promotion,errors='coerce').fillna(0.)
    for c in ('sku_id','category','warehouse_id'): df[c]=df[c].astype(str)
    df=df.sort_values(['sku_id','date']).reset_index(drop=True); dates=pd.DatetimeIndex(sorted(df.date.unique()))
    chunk=int(np.ceil(len(dates)*.08)); starts=[int(len(dates)*.60)+i*chunk for i in range(FOLDS)]
    if len(starts)!=FOLDS or starts[-1]>=len(dates): raise ValueError('Not enough dates for five folds')
    device=torch.device('cuda' if torch.cuda.is_available() else 'cpu'); OUT.mkdir(parents=True,exist_ok=True)
    fold_rows=[]; sku_rows=[]; global_sku_rows=[]; folds=[]
    print(f'Device={device}; rows={len(df)}; SKUs={df.sku_id.nunique()}; dates={len(dates)}')
    for fold,test_start in enumerate(starts,1):
        val_start=test_start-chunk; train_end=pd.Timestamp(dates[val_start-1]); val_end=pd.Timestamp(dates[test_start-1]); test_end=pd.Timestamp(dates[min(test_start+chunk,len(dates))-1])
        print(f'\nFold {fold}: train <= {train_end.date()}, validation <= {val_end.date()}, test <= {test_end.date()}')
        d=make_data(df,train_end,val_end,test_end); tr,va,te=d['train'],d['validation'],d['test']
        if min(len(tr),len(va),len(te))==0: raise ValueError(f'Fold {fold} has empty split')
        seed_all(SEED+fold); gm=GlobalDemandLSTM(num_skus=d['n_skus'],num_categories=d['n_cats'],num_warehouses=d['n_wh'],num_numeric_features=4,embedding_dim=8,hidden_size=64,num_layers=2,horizon=HORIZON,dropout=.2)
        gm,gt=fit(gm,DataLoader(tr,batch_size=BATCH,shuffle=True),DataLoader(va,batch_size=128),device,True)
        ga,gp,gs=pred_global(gm,te,device,d['scaler']); eligible=set(); pa=[]; pp=[]; pst=0.
        # Report Global LSTM metrics separately for every SKU, including short-history SKUs.
        for sku, sid in d['sku_map'].items():
            counts=d['counts'][sku]; sku_mask=(gs==sid); gsku=score(ga[sku_mask],gp[sku_mask])
            global_sku_rows.append({'row_type':'global_sku_detail','fold':fold,'sku_id':sku,
                'status':'evaluated' if sku_mask.any() else 'not_evaluated',
                'reason':'' if sku_mask.any() else 'no_test_windows',
                'train_windows':counts['train'],'validation_windows':counts['validation'],
                'test_windows':counts['test'],**gsku})
        for sku,sid in d['sku_map'].items():
            counts=d['counts'][sku]; ti=torch.where(tr.tensors[1]==sid)[0]; vi=torch.where(va.tensors[1]==sid)[0]; ei=torch.where(te.tensors[1]==sid)[0]
            status='eligible'; reason=''; seconds=None; met=score([],[])
            if len(ti)<MIN_TRAIN: status,reason='not_trained','insufficient_training_windows'
            elif len(vi)==0: status,reason='not_trained','no_validation_windows'
            elif len(ei)==0: status,reason='not_evaluated','no_test_windows'
            else:
                seed_all(SEED+fold*100+sid); train=TensorDataset(tr.tensors[0][ti],tr.tensors[4][ti]); valid=TensorDataset(va.tensors[0][vi],va.tensors[4][vi]); test=TensorDataset(te.tensors[0][ei],te.tensors[4][ei]); model=PerSKUModel(horizon=HORIZON)
                model,seconds=fit(model,DataLoader(train,batch_size=BATCH,shuffle=True),DataLoader(valid,batch_size=128),device,False)
                a,p=pred_sku(model,test,device,d['scaler']); met=score(a,p); eligible.add(sid); pa.append(a); pp.append(p); pst+=seconds
            sku_rows.append({'row_type':'sku_detail','fold':fold,'sku_id':sku,'status':status,'reason':reason,'train_windows':counts['train'],'validation_windows':counts['validation'],'test_windows':counts['test'],'training_seconds':seconds,**met})
        mask=np.isin(gs,list(eligible)); gcommon=score(ga[mask],gp[mask]); pcommon=score(np.concatenate(pa) if pa else [],np.concatenate(pp) if pp else []); gall=score(ga,gp)
        fi={'fold':fold,'train_end':str(train_end.date()),'validation_end':str(val_end.date()),'test_end':str(test_end.date()),'train_windows':len(tr),'validation_windows':len(va),'test_windows':len(te),'eligible_skus':len(eligible),'global_training_seconds':float(gt),'per_sku_total_training_seconds':float(pst),'global_all_test_metrics':gall,'global_common_sku_metrics':gcommon,'per_sku_common_metrics':pcommon}; folds.append(fi)
        for name,sec,m,n in [('global_all_test_skus',gt,gall,df.sku_id.nunique()),('global_common_eligible_skus',gt,gcommon,len(eligible)),('per_sku_common_eligible_skus',pst,pcommon,len(eligible))]: fold_rows.append({'row_type':'fold_comparison','fold':fold,'model':name,'training_seconds':float(sec),'eligible_skus':n,**m})
        print(f"Global/common MAE={gcommon['MAE']}; Per-SKU/common MAE={pcommon['MAE']}; global={gt:.1f}s; per-SKU={pst:.1f}s; eligible SKUs={len(eligible)}")
    metrics_path=OUT/'walk_forward_fold_metrics.csv'; summary_path=OUT/'walk_forward_summary.json'
    pd.DataFrame(fold_rows+global_sku_rows+sku_rows).to_csv(metrics_path,index=False)
    def mean_metrics(key):
        return {m:(float(np.mean([f[key][m] for f in folds if f[key][m] is not None])) if any(f[key][m] is not None for f in folds) else None) for m in ('MAE','RMSE','MAPE_percent')}
    summary={'evaluation':'five-fold expanding-window walk-forward','dataset':str(DATA),'lookback':LOOKBACK,'horizon':HORIZON,'folds':folds,'mean_fold_metrics':{'global_all_test_skus':mean_metrics('global_all_test_metrics'),'global_common_eligible_skus':mean_metrics('global_common_sku_metrics'),'per_sku_common_eligible_skus':mean_metrics('per_sku_common_metrics')},'mean_training_seconds':{'global':float(np.mean([f['global_training_seconds'] for f in folds])),'per_sku_total':float(np.mean([f['per_sku_total_training_seconds'] for f in folds]))},'notes':['Scaler is fit only on each fold training period.','Validation and test target horizons stay inside their split.','Common-SKU metrics compare eligible per-SKU models on their same test windows.','Short-history SKUs and exclusion reasons are recorded in CSV.','Global LSTM metrics are recorded per SKU in rows with row_type=global_sku_detail, including short-history SKUs.','MAPE excludes zero-valued actuals.']}
    summary_path.write_text(json.dumps(summary,indent=2),encoding='utf-8')
    print(f'\nSaved {metrics_path}\nSaved {summary_path}')
    print(json.dumps(summary['mean_fold_metrics'],indent=2))
    print('Review results before marking Milestone 1 complete.')

if __name__=='__main__': main()
