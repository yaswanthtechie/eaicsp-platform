# Data Profiling & Quality Report

This project performs data profiling on a dataset using Python and Pandas. It generates a detailed HTML report containing dataset information, column statistics, missing values, data types, outlier detection, and automatic column role identification.



# Features

Dataset Summary
Column Summary
Missing Value Analysis
Unique Value Count
Automatic Column Role Detection
  ID
  Category
  Measure
  Text
Distribution Statistics
IQR Based Outlier Detection
HTML Report Generation


# Project Structure

profiling/
│
├── data/
├── reports/
├── src/
├── README.md
└── requirements.txt


# Technologies Used

Python
Pandas
NumPy
Matplotlib


## Challenges Faced

Understanding different data types.
Implementing automatic column role detection.
Detecting outliers using the IQR method.
Converting date columns correctly.
Generating the HTML report dynamically using Python.



# Output

The project generates:

HTML Data Profiling Report
Histogram Before Outlier Removal
Histogram After Outlier Removal
Box Plot
