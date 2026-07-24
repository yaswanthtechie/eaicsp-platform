import numpy as np 
import pandas as pd 

np.random.seed(42)

def make_sample_data():
    
    date_range = pd.date_range(start="2024-01-01", end="2025-12-31",freq="D")

    skus = [f"SKU{i:03d}" for i in range(1,51)]
    
    warehouses = [f"WH{i}" for i in range(1,6)]
    
    dates=np.random.choice(date_range,size=5000)
    
    sku_ids=np.random.choice(skus,size=5000)
    
    warehouse_id=np.random.choice(warehouses, size=5000)
    
    quantity_sold=np.random.randint(1, 101, size=5000)
    
    unit_price=np.random.randint(100, 1001, size=5000)
    
    df = pd.DataFrame({
        "date":dates,
        "sku_id":sku_ids,
        "warehouse_id":warehouse_id,
        "quantity_sold":quantity_sold,
        "unit_price":unit_price
    })
    
    missing_count=int(len(df)*0.03)
    
    missing_rows=np.random.choice(df.index, size=missing_count, replace=False)
    
    df.loc[missing_rows, "quantity_sold"] = np.nan
    
    missing_rows=np.random.choice(df.index, size=missing_count, replace=False)
    df.loc[missing_rows, "unit_price"]=np.nan
    
    outlier_count=int(len(df)*0.01)
    
    outlier_rows=np.random.choice(df.index, size=outlier_count, replace=False)
    df.loc[outlier_rows, "quantity_sold"] = 99999
    
    df.to_csv("data/sales_data.csv", index=False)
    
    return df

df=make_sample_data()

a=df.head()
print(a)

print("Shape",a.shape)

print("Missing Values: ")

print(a.isna().sum()) #Missing the values

print("Maximum Quantity:")

print(a["quantity_sold"].max())