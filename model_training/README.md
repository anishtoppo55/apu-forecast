# Model Training

This folder contains the notebooks, helper script, datasets, and exported artifacts used to train the power-consumption forecasting models.

> [!WARNING]
> Some notebooks may not render correctly on GitHub. Clone the repository and open them locally in JupyterLab for the best viewing experience.

## Contents

- `Utlity_final_LGBM.ipynb` trains and evaluates LightGBM forecasting models for total demand and the three feeder targets.
- `best_param_F3.ipynb` uses Optuna to tune LightGBM hyperparameters for the F3 feeder model.
- `history_seed.py` saves the most recent feature rows to `history_seed.csv` for initializing forecasts.
- `Utility_consumption_cleaned.csv` is the cleaned dataset used during the modeling workflow.
- `history_seed.csv` provides recent historical observations required by lag-based forecasting.
- `trained_models_bundle/` contains the exported models and their metadata; `trained_models_bundle.zip` is its packaged copy.

