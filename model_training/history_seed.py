import pandas as pd

df = pd.read_csv("Utility_features_engineered.csv", parse_dates=["Datetime"])
df = df.set_index("Datetime").sort_index()
history_seed = df.iloc[-1500:].copy()
history_seed.to_csv("history_seed.csv")
print(df["CloudCover"].describe())  # should show min~0, max~100