"""
Data Science Laboratory - Experiment 1
Exploratory Data Analysis & Feature Correlation on California Housing Dataset
Student: Lohith Goud (22DS101)
"""

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns

# 1. Dataset Ingestion
print("[STEP 1] Loading California Housing Dataset...")
df = pd.read_csv("california_housing.csv")
print("Dataset Dimensions:", df.shape)
print("\nFirst 5 Records:")
print(df.head())

# 2. Inspecting Nulls and Imputation
print("\n[STEP 2] Checking Missing Values:")
missing = df.isnull().sum()
print(missing[missing > 0])

# Impute median value for missing numerical entries
median_bedrooms = df['total_bedrooms'].median()
df['total_bedrooms'] = df['total_bedrooms'].fillna(median_bedrooms)
print(f"-> Imputed missing total_bedrooms with median: {median_bedrooms}")

# 3. Descriptive Statistical Breakdown
print("\n[STEP 3] Summary Statistics of Numerical Features:")
print(df.describe().T[['mean', 'std', 'min', '50%', 'max']])

# 4. Pearson Correlation Analysis
print("\n[STEP 4] Correlation with Median House Value:")
corr_matrix = df.corr(numeric_only=True)
target_corr = corr_matrix['median_house_value'].sort_values(ascending=False)
print(target_corr)

# 5. Output Visualization: Correlation Heatmap
print("\n[STEP 5] Generating Seaborn Correlation Heatmap...")
plt.figure(figsize=(10, 7))
sns.heatmap(
    corr_matrix, 
    annot=True, 
    cmap="coolwarm", 
    fmt=".2f", 
    linewidths=0.5,
    cbar_kws={'label': 'Pearson Correlation'}
)
plt.title("California Housing - Feature Correlation Heatmap", fontsize=14, weight='bold')
plt.tight_layout()
plt.savefig("output_heatmap.png", dpi=300)
print("-> Plot saved to output_heatmap.png")
print("[COMPLETED] Experiment 1 executed successfully.")
