# House Prices - Machine Learning Pipeline

A machine learning solution for predicting house prices using multiple modeling approaches and optimization techniques.

## Machine Learning Components

### Feature Engineering (`features.py`)
- **Domain-Specific Preprocessing**
  - Structural missing value handling based on domain knowledge
  - Smart imputation strategies (neighborhood-based for LotFrontage)
  - Ordinal encoding for quality features (Ex→5, Gd→4, etc.)
  - Feature creation: TotalSF, Age, TotalBath

### Model Training & Evaluation

#### Model Selection (`sweep.py`)
Evaluates and selects the best model from multiple algorithms:
- Ridge Regression (with CV for alpha)
- Lasso Regression (with CV for alpha)
- Gradient Boosting Regressor
- Random Forest
- HistGradient Boosting Regressor

Each model evaluated using:
- 5-fold cross-validation
- Log-transformed RMSE
- Full pipeline validation to prevent leakage

#### Hyperparameter Tuning (`tune_gbr.py`)
Optimizes GradientBoostingRegressor using:
- **RandomizedSearchCV with:**
  - 48 configurations
  - Intelligent parameter spaces:
    - n_estimators: 400-1100
    - learning_rate: 0.02-0.12 (log-uniform)
    - max_depth: 2-4
    - min_samples_leaf: 1-5
    - subsample: 0.75-1.0
    - max_features: [None, sqrt, log2]
- **Performance caching** using joblib Memory
- **Parallel execution** across configurations/folds

### Inference (`infer.py`)
- Loads best available model (best_pipeline.joblib or house_prices_pipeline.joblib)
- Applies identical preprocessing pipeline
- Generates competition submission format

## Model Artifacts

All models and results are saved to `models/`:
- `house_prices_pipeline.joblib`: Base model
- `best_pipeline.joblib`: Best tuned model
- `sweep_results.csv`: Performance comparison across algorithms
- `gbr_random_results.csv`: Hyperparameter tuning results

## Key Metrics
All models are evaluated using RMSE in log-space:
```python
RMSE(log1p(actual), log1p(predicted))
```
This aligns with the competition's evaluation metric and handles the right-skewed nature of house prices.

## Running the Pipeline

### Basic Commands
```make
# Compare multiple models (Ridge, Lasso, GBR, RF, HGBR)  
make sweep

# Tune GradientBoosting hyperparameters
make tune

# Generate predictions
make predict

# Clean model artifacts and cache
make clean

# Run full pipeline (sweep, tune, predict)
make all
```

### Pipeline Workflow
1. `make sweep`: Compare and select best model
   - Saves results to `models/sweep_results.csv`
   - Best model saved to `models/best_pipeline.joblib`

2. `make tune`: Fine-tunes GradientBoosting 
   - Saves tuning results to `models/gbr_random_results.csv`
   - Best tuned model saves to `models/best_pipeline.joblib`

3. `make predict`: Generates predictions
   - Uses best available model
   - Creates `submission.csv`