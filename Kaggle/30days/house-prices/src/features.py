# src/features.py
import numpy as np
import pandas as pd
from typing import Optional
from sklearn.base import BaseEstimator, TransformerMixin

class DomainFeatures(BaseEstimator, TransformerMixin):
    """
    - Applies competition-specific fill rules (None/0) for structural missingness
    - Encodes ordered quality columns as integers
    - Adds simple, high-signal features
    - Group-median impute for LotFrontage by Neighborhood (if present)
    - Ensures MSSubClass is treated as categorical (string)
    """
    def __init__(self):
        self._lotfrontage_by_nbhd_: Optional[pd.Series] = None

        self.fill_none_cols = [
            "PoolQC", "Alley", "Fence", "FireplaceQu",
            "GarageType", "GarageFinish", "GarageQual", "GarageCond",
            "BsmtExposure", "BsmtFinType1", "BsmtFinType2", "BsmtQual", "BsmtCond",
            "MasVnrType",
        ]
        self.fill_zero_cols = ["MasVnrArea", "GarageYrBlt"]

        self.qual_map = {"Ex": 5, "Gd": 4, "TA": 3, "Fa": 2, "Po": 1}
        self.ordinal_cols = ["ExterQual", "BsmtQual", "KitchenQual", "HeatingQC"]

    def fit(self, X: pd.DataFrame, y=None):
        Xc = X.copy()
        if "Neighborhood" in Xc.columns and "LotFrontage" in Xc.columns:
            self._lotfrontage_by_nbhd_ = Xc.groupby("Neighborhood")["LotFrontage"].median()
        else:
            self._lotfrontage_by_nbhd_ = None
        return self

    def transform(self, X: pd.DataFrame):
        Xc = X.copy()

        if "MSSubClass" in Xc.columns:
            Xc["MSSubClass"] = Xc["MSSubClass"].astype("string")

        for c in self.fill_none_cols:
            if c in Xc.columns:
                Xc[c] = Xc[c].fillna("None")
        for c in self.fill_zero_cols:
            if c in Xc.columns:
                Xc[c] = Xc[c].fillna(0)

        if "LotFrontage" in Xc.columns:
            if self._lotfrontage_by_nbhd_ is not None and "Neighborhood" in Xc.columns:
                global_med = Xc["LotFrontage"].median()
                mapped = Xc["Neighborhood"].map(self._lotfrontage_by_nbhd_)
                Xc["LotFrontage"] = Xc["LotFrontage"].fillna(mapped).fillna(global_med)
            else:
                Xc["LotFrontage"] = Xc["LotFrontage"].fillna(Xc["LotFrontage"].median())

        for c in self.ordinal_cols:
            if c in Xc.columns:
                Xc[c] = Xc[c].map(self.qual_map).fillna(0).astype(int)

        def has(cols): return all(col in Xc.columns for col in cols)
        if has(["TotalBsmtSF", "1stFlrSF", "2ndFlrSF"]):
            Xc["TotalSF"] = Xc["TotalBsmtSF"] + Xc["1stFlrSF"] + Xc["2ndFlrSF"]
        if has(["YrSold", "YearBuilt"]):
            Xc["Age"] = Xc["YrSold"] - Xc["YearBuilt"]
        if has(["FullBath", "HalfBath"]):
            Xc["TotalBath"] = Xc["FullBath"] + 0.5 * Xc["HalfBath"]

        return Xc
