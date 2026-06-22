# Trained Model Bundle

This folder contains the serialized LightGBM forecasting models and metadata needed to load them for inference.

## Contents

- `model_*.pkl` files are trained models for total power consumption and the F1, F2, and F3 feeders.
- `feature_cols_per_target.pkl` records the input feature columns expected by each model.
- `targets.pkl` stores the list of forecast targets.

