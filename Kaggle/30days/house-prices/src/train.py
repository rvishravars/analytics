# Main training pipeline: evaluates multiple models and selects best
import os, joblib, numpy as np, pandas as pd
from pathlib import Path

from sklearn.compose import ColumnTransformer, make_column_selector as selector
from sklearn.impute import SimpleImputer
from sklearn.preprocessing import OneHotEncoder, StandardScaler
from sklearn.pipeline import Pipeline
from sklearn.model_selection import KFold, cross_val_score
from sklearn.metrics import make_scorer, mean_squared_error
from sklearn.ensemble import HistGradientBoostingRegressor
from sklearn.compose import TransformedTargetRegressor

from features import DomainFeatures

# ----------------------------- Paths ---------------------------------
DATA_DIR = Path(__file__).resolve().parents[1] / "data"
MODEL_DIR = Path(__file__).resolve().parents[1] / "models"
MODEL_DIR.mkdir(parents=True, exist_ok=True)

def rmse(y_true, y_pred) -> float:
    return np.sqrt(mean_squared_error(y_true, y_pred))

def main():
    train = pd.read_csv(DATA_DIR / "train.csv")
    X = train.drop(columns=["SalePrice", "Id"], errors="ignore").copy()
    y = train["SalePrice"].values

    # Build pipeline
    model = Pipeline(steps=[
        ("domain", DomainFeatures()),
        ("pre", ColumnTransformer([
            ("num", Pipeline([
                ("imputer", SimpleImputer(strategy="median")),
                ("scaler", StandardScaler()),
            ]), selector(dtype_include=np.number)),
            ("cat", Pipeline([
                ("imputer", SimpleImputer(strategy="most_frequent")),
                ("onehot", OneHotEncoder(handle_unknown="ignore", min_frequency=0.01, sparse_output=True)),
            ]), selector(dtype_include=["object", "string", "category"])),
        ])),
        ("reg", TransformedTargetRegressor(
            regressor=HistGradientBoostingRegressor(
                learning_rate=0.06, max_iter=600,
                max_depth=None, l2_regularization=0.0,
                early_stopping=True, random_state=42
            ),
            func=np.log1p, inverse_func=np.expm1
        )),
    ])

    # Score in log-space
    def neg_log_rmse(yt, yp): return -rmse(np.log1p(yt), np.log1p(yp))
    
    scores = cross_val_score(
        model, X, y, 
        cv=KFold(n_splits=5, shuffle=True, random_state=42),
        scoring=make_scorer(neg_log_rmse),
        n_jobs=None
    )
    print(f"CV RMSE(log-space): {-scores.mean():.5f} ± {scores.std():.5f}")

    # Fit & save
    model.fit(X, y)
    joblib.dump({"pipeline": model}, MODEL_DIR / "house_prices_pipeline.joblib")
    print("Saved model to models/house_prices_pipeline.joblib")

if __name__ == "__main__":
    main()
