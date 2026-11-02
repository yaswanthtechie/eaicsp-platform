import pandas as pd

from src.profiler import Profiler

profiler = Profiler()

df = pd.read_csv("../out/warehouses.csv")

report = profiler.profile(df)
report.save_html("../profile_report/warehouses_report.html")
