import pandas as pd

df=pd.read_csv("data/sales_data.csv")

print(df.head())

Q1=df["quantity_sold"].quantile(0.25) #Quantile divide parts
print(Q1)

Q3=df["quantity_sold"].quantile(0.75)
print(Q3)

IQR=Q3-Q1  # Interquartile Range

print(IQR)

lower_limit=Q1 - (1.5 * IQR)

print(lower_limit)

upper_limit=Q3 + (1.5 * IQR) 

print(upper_limit)


outliers = df[df["quantity_sold"]>upper_limit]

print(len(outliers))


# uses the data from csv