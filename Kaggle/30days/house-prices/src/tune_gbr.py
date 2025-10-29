# src/tune_gbr.py
import numpy as np, pandas as pd, joblib
from pathlib import Path
from joblib import Memory

from sklearn.compose import ColumnTransformer, make_column_selector as selector
from sklearn.impute import SimpleImputer
from sklearn.preprocessing import OneHotEncoder, StandardScaler
from sklearn.pipeline import Pipeline
from sklearn.metrics import make_scorer, mean_squared_error
from sklearn.model_selection import KFold, RandomizedSearchCV
from sklearn.ensemble import GradientBoostingRegressor
from sklearn.compose import TransformedTargetRegressor
from scipy.stats import randint, uniform, loguniform  # pip install scipy if missing

from features import DomainFeatures

DATA_DIR = Path(__file__).resolve().parents[1] / "data"
MODEL_DIR = Path(__file__).resolve().parents[1] / "models"
MODEL_DIR.mkdir(parents=True, exist_ok=True)
CACHE_DIR = MODEL_DIR / ".cache"
CACHE_DIR.mkdir(parents=True, exist_ok=True)

SEED = 42
RND = np.random.RandomState(SEED)

def rmse_log_space(y_true, y_pred):
    return np.sqrt(mean_squared_error(np.log1p(y_true), np.log1p(y_pred)))

def make_preprocessor():
    num = Pipeline([
        ("imputer", SimpleImputer(strategy="median")),
        ("scaler", StandardScaler()),
    ])
    cat = Pipeline([
        ("imputer", SimpleImputer(strategy="most_frequent")),
        ("ohe", OneHotEncoder(handle_unknown="ignore", min_frequency=0.01, sparse_output=True)),
    ])
    return ColumnTransformer([
        ("num", num, selector(dtype_include=np.number)),
        ("cat", cat, selector(dtype_include=["object", "string", "category"])),
    ])

def make_pipe(base, memory):
    # memory caches fit/transform steps for speed across CV folds
    return Pipeline([
        ("domain", DomainFeatures()),
        ("pre", make_preprocessor()),
        ("reg", TransformedTargetRegressor(regressor=base, func=np.log1p, inverse_func=np.expm1)),
    ], memory=memory)

def main():
    # Data
    train = pd.read_csv(DATA_DIR / "train.csv")
    X = train.drop(columns=["SalePrice", "Id"], errors="ignore")
    y = train["SalePrice"].values

    # Base estimator
    base = GradientBoostingRegressor(random_state=SEED)

    # Cache for pipeline steps
    memory = Memory(location=str(CACHE_DIR), verbose=0)

    pipe = make_pipe(base, memory)

    # Fast, effective param distributions
    param_dist = {
        "reg__regressor__n_estimators": randint(400, 1100),
        "reg__regressor__learning_rate": loguniform(0.02, 0.12),
        "reg__regressor__max_depth": randint(2, 5),
        "reg__regressor__min_samples_leaf": randint(1, 6),
        "reg__regressor__subsample": uniform(0.75, 0.25),  # 0.75–1.0
        "reg__regressor__max_features": [None, "sqrt", "log2"],     # small regularization
    }

    cv = KFold(n_splits=5, shuffle=True, random_state=SEED)
    scorer = make_scorer(lambda yt, yp: -rmse_log_space(yt, yp))  # maximize negative loss

    search = RandomizedSearchCV(
        estimator=pipe,
        param_distributions=param_dist,
        n_iter=48,              # ~48 configs is plenty here
        scoring=scorer,
        cv=cv,
        random_state=SEED,
        n_jobs=-1,              # parallelize across configs/folds
        refit=True,
        verbose=2
    )

    search.fit(X, y)

    best = search.best_estimator_
    best_score = -search.best_score_  # back to positive log-RMSE

    print("\nBest params:")
    for k, v in search.best_params_.items():
        print(f"  {k} = {v}")
    print(f"\nBest CV log-RMSE: {best_score:.5f}")

    # Save artifacts
    joblib.dump(
        {"pipeline": best, "cv_log_rmse": best_score, "best_params": search.best_params_},
        MODEL_DIR / "best_pipeline.joblib"
    )
    pd.DataFrame(search.cv_results_).to_csv(MODEL_DIR / "gbr_random_results.csv", index=False)
    print("Saved best pipeline and random search results.")

if __name__ == "__main__":
    main()
