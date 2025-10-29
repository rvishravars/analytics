# src/infer.py
import joblib, pandas as pd
from pathlib import Path
from features import DomainFeatures  # ensure resolvable when unpickling

DATA_DIR = Path(__file__).resolve().parents[1] / "data"
MODEL_DIR = Path(__file__).resolve().parents[1] / "models"

def main():
    test = pd.read_csv(DATA_DIR / "test.csv")
    ids = test["Id"]
    X_test = test.drop(columns=["Id"], errors="ignore").copy()
    if "MSSubClass" in X_test.columns:
        X_test["MSSubClass"] = X_test["MSSubClass"].astype("string")

    # Prefer best model if present; fall back to previous filename
    model_path = (MODEL_DIR / "best_pipeline.joblib")
    if not model_path.exists():
        model_path = (MODEL_DIR / "house_prices_pipeline.joblib")

    bundle = joblib.load(model_path)
    model = bundle["pipeline"]
    preds = model.predict(X_test)

    out = Path(__file__).resolve().parents[1] / "submission.csv"
    pd.DataFrame({"Id": ids, "SalePrice": preds}).to_csv(out, index=False)
    print(f"Wrote {out}")

if __name__ == "__main__":
    main()
