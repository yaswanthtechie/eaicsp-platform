import numpy as np
def create_sequences(series,lookback=30,horizon=7):
    """converts a time series into supervised learning sequences.
    input:
    series: scaled time series data
    lookback: prior days to use for prediction
    horizon: number of days to predict
    returns:
    X: input sequences
    y: target values"""
    X,y=[],[]
    for i in range(len(series)-lookback-horizon+1):     
        X.append(series[i:i+lookback])                  
        y.append(series[i+lookback:i+lookback+horizon]) 
    return np.array(X),np.array(y) 