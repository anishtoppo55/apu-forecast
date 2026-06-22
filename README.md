# APU Forecast

APU Forecast is an electricity-demand forecasting project that uses historical utility consumption, weather conditions, calendar information, and machine-learning models to predict total and feeder-wise power demand.
## 🌐 Live Demo

Access the deployed application here:

👉 https://apu-forecast-192u.onrender.com

> Note: The app may take 30–60 seconds to load on first visit due to cold start (Render free tier).
## Project Folders

- **`assets/`** contains the assignment document and holiday reference files used during the project.
- **`EDA/`** contains the raw utility dataset and notebooks for preprocessing, data-quality checks, visualization, and exploratory analysis, including holiday-based analysis.
- **`feature engineering/`** contains the notebook that creates time, weather, holiday, lag, and rolling features, along with its input and generated datasets.
- **`model_training/`** contains LightGBM training and tuning notebooks, the history-seed helper script, modeling datasets, and exported trained-model files.
- **`main/`** contains the deployable forecasting application: a FastAPI backend, model artifacts, a Chart.js dashboard, and Docker configuration. See its own README for setup and usage instructions.

## Workflow

The project follows this general sequence:

1. Clean and explore the consumption data in `EDA/`.
2. Generate model-ready variables in `feature engineering/`.
3. Train, evaluate, and export forecasting models in `model_training/`.
4. Serve predictions and display them through the application in `main/`.

## Requirements

The root `requirements.txt` contains the Python packages needed to run the scripts and notebooks in `EDA/`, `feature engineering/`, and `model_training/`. The application in `main/` has a separate requirements file.

Create an environment and install the project dependencies from the repository root:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
pip install -r requirements.txt
```

Start JupyterLab after installation:

```bash
jupyter lab
```

The preprocessing notebook retrieves weather data from Open-Meteo, so an internet connection is required when running that step.
