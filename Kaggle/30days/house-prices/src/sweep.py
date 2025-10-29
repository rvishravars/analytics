# src/sweep.py
import os, joblib, numpy as np, pandas as pd
from pathlib import Path
from typing import List, Tuple, Dict, Any

from sklearn.compose import ColumnTransformer, make_column_selector as selector
from sklearn.impute import SimpleImputer
from sklearn.preprocessing import OneHotEncoder, StandardScaler
from sklearn.pipeline import Pipeline
from sklearn.model_selection import KFold, cross_val_score
from sklearn.metrics import make_scorer, mean_squared_error
from sklearn.linear_model import RidgeCV, LassoCV
from sklearn.ensemble import GradientBoostingRegressor, RandomForestRegressor, HistGradientBoostingRegressor
from sklearn.compose import TransformedTargetRegressor

from features import DomainFeatures  # custom transformer

DATA_DIR = Path(__file__).resolve().parents[1] / "data"
MODEL_DIR = Path(__file__).resolve().parents[1] / "models"
MODEL_DIR.mkdir(parents=True, exist_ok=True)
RESULTS_CSV = MODEL_DIR / "sweep_results.csv"
BEST_MODEL = MODEL_DIR / "best_pipeline.joblib"

SEED = 42

def rmse(y_true, y_pred) -> float:
    return np.sqrt(mean_squared_error(y_true, y_pred))

def neg_log_rmse(yt, yp):
    # scorer must be "higher is better"; we return negative log-RMSE
    return -rmse(np.log1p(yt), np.log1p(yp))

def make_preprocessor():
    numeric_pipe = Pipeline(steps=[
        ("imputer", SimpleImputer(strategy="median")),
        ("scaler", StandardScaler()),
    ])
    categorical_pipe = Pipeline(steps=[
        ("imputer", SimpleImputer(strategy="most_frequent")),
        ("onehot", OneHotEncoder(handle_unknown="ignore", min_frequency=0.01, sparse_output=True)),
    ])
    return ColumnTransformer(transformers=[
        ("num", numeric_pipe, selector(dtype_include=np.number)),
        ("cat", categorical_pipe, selector(dtype_include=["object", "string", "category"])),
    ])

def make_pipeline(base_estimator):
    pre = make_preprocessor()
    pipe = Pipeline(steps=[
        ("domain", DomainFeatures()),
        ("pre", pre),
        ("reg", TransformedTargetRegressor(
            regressor=base_estimator,
            func=np.log1p, inverse_func=np.expm1
        ))
    ])
    return pipe

def candidates() -> Dict[str, Any]:
    return {
        "ridge": RidgeCV(alphas=np.logspace(-3, 3, 13)),
        "lasso": LassoCV(alphas=np.logspace(-3, 1, 10), random_state=SEED, max_iter=20000),
        "gbr": GradientBoostingRegressor(
            n_estimators=700, learning_rate=0.05, max_depth=3, random_state=SEED
        ),
        "rf": RandomForestRegressor(
            n_estimators=800, max_depth=None, min_samples_leaf=1,
            n_jobs=-1, random_state=SEED
        ),
        "hgbr": HistGradientBoostingRegressor(
            learning_rate=0.06, max_iter=700, max_depth=None,
            early_stopping=True, random_state=SEED
        ),
    }

def main():
    train = pd.read_csv(DATA_DIR / "train.csv")
    X = train.drop(columns=["SalePrice", "Id"], errors="ignore").copy()
    y = train["SalePrice"].values

    cv = KFold(n_splits=5, shuffle=True, random_state=SEED)
    scorer = make_scorer(neg_log_rmse)

    rows = []
    best_name, best_score, best_pipe = None, float("inf"), None

    for name, est in candidates().items():
        pipe = make_pipeline(est)
        scores = cross_val_score(pipe, X, y, cv=cv, scoring=scorer, n_jobs=None)
        # convert back to positive log-RMSE
        mean_log_rmse = -scores.mean()
        std_log_rmse = scores.std()

        rows.append({
            "model": name,
            "cv_log_rmse_mean": mean_log_rmse,
            "cv_log_rmse_std": std_log_rmse
        })
        print(f"{name:>5s} | CV log-RMSE: {mean_log_rmse:.5f} ± {std_log_rmse:.5f}")

        if mean_log_rmse < best_score:
            best_score, best_name = mean_log_rmse, name
            # fit on all data
            best_pipe = make_pipeline(est)
            best_pipe.fit(X, y)

    # Save results & best model
    df = pd.DataFrame(rows).sort_values("cv_log_rmse_mean").reset_index(drop=True)
    df.to_csv(RESULTS_CSV, index=False)
    joblib.dump({"pipeline": best_pipe, "best_model_name": best_name, "cv_log_rmse": best_score}, BEST_MODEL)

    print("\n=== Summary ===")
    print(df)
    print(f"\nBest: {best_name} (CV log-RMSE={best_score:.5f})")
    print(f"Wrote: {RESULTS_CSV}")
    print(f"Saved best pipeline to: {BEST_MODEL}")

if __name__ == "__main__":
    main()
