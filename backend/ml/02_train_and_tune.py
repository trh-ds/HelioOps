"""
Trains the 6 LightGBM quantile checkpoints that backend/ml/inference.py serves.

    PYTHONPATH=. python backend/ml/02_train_and_tune.py

GroupKFold on storm_id, not a row split: 40 frames share one storm profile, so
a random split leaks the answer across the fold boundary and the CV loss comes
out meaninglessly good.
"""

import warnings

import joblib
import lightgbm as lgb
import numpy as np
import optuna
import pandas as pd
from sklearn.model_selection import GroupKFold

from backend.paths import CHECKPOINT_DIR, SYNTHETIC_CSV

warnings.filterwarnings("ignore")

def pinball_loss(y_true, y_pred, alpha):
    """Calculates the Pinball Loss (Quantile Loss)"""
    err = y_true - y_pred
    return np.mean(np.maximum(alpha * err, (alpha - 1) * err))

def train_and_tune_model(df, target_col, alphas, n_trials=20):
    """
    Tunes and trains LightGBM models for multiple quantiles using Optuna.
    Returns a dictionary of trained models.
    """
    print(f"\n--- Tuning and Training for {target_col} ---")
    
    # Features
    features = [
        "g_scale", "kp_index", "bz_nt", "wind_speed_km_s", 
        "cme_speed_km_s", "cme_width_deg", "r_scale", 
        "geomag_lat_bin", "local_time_bin"
    ]
    
    X = df[features]
    y = df[target_col]
    groups = df["storm_id"]
    
    trained_models = {}
    
    for alpha in alphas:
        print(f"Tuning for alpha={alpha}...")
        
        def objective(trial):
            params = {
                'objective': 'quantile',
                'alpha': alpha,
                'metric': 'quantile',
                'learning_rate': trial.suggest_float('learning_rate', 1e-3, 0.1, log=True),
                'max_depth': trial.suggest_int('max_depth', 3, 8),
                'num_leaves': trial.suggest_int('num_leaves', 10, 50),
                'n_estimators': trial.suggest_int('n_estimators', 50, 200), # Keeping it lightweight
                'verbose': -1
            }
            
            gkf = GroupKFold(n_splits=5)
            cv_scores = []
            
            for train_idx, val_idx in gkf.split(X, y, groups=groups):
                X_train, X_val = X.iloc[train_idx], X.iloc[val_idx]
                y_train, y_val = y.iloc[train_idx], y.iloc[val_idx]
                
                model = lgb.LGBMRegressor(**params)
                model.fit(
                    X_train, y_train,
                    eval_set=[(X_val, y_val)],
                    callbacks=[lgb.early_stopping(stopping_rounds=10, verbose=False)]
                )
                
                y_pred = model.predict(X_val)
                score = pinball_loss(y_val, y_pred, alpha)
                cv_scores.append(score)
                
            return np.mean(cv_scores)

        # Suppress optuna logging output
        optuna.logging.set_verbosity(optuna.logging.WARNING)
        study = optuna.create_study(direction='minimize')
        study.optimize(objective, n_trials=n_trials)
        
        print(f"  Best params for alpha={alpha}: {study.best_params}")
        print(f"  Best CV Pinball Loss: {study.best_value:.4f}")
        
        # Train final model on entire dataset using best params
        best_params = study.best_params
        best_params['objective'] = 'quantile'
        best_params['alpha'] = alpha
        best_params['metric'] = 'quantile'
        best_params['verbose'] = -1
        
        final_model = lgb.LGBMRegressor(**best_params)
        final_model.fit(X, y)
        trained_models[alpha] = final_model
        
    return trained_models

def calculate_metrics(y_true, y_pred_low, y_pred_high):
    """Calculates PICP and PINAW"""
    # Prediction Interval Coverage Probability
    picp = np.mean((y_true >= y_pred_low) & (y_true <= y_pred_high))
    
    # Prediction Interval Normalized Average Width
    y_range = np.max(y_true) - np.min(y_true)
    if y_range == 0:
        y_range = 1e-8
    pinaw = np.mean(y_pred_high - y_pred_low) / y_range
    
    return picp, pinaw

def main():
    if not SYNTHETIC_CSV.exists():
        raise SystemExit(
            f"{SYNTHETIC_CSV} not found. Run:\n"
            "  PYTHONPATH=. python backend/ml/01_data_generation_eda.py"
        )

    df = pd.read_csv(SYNTHETIC_CSV)
    print(f"Training on {len(df)} rows / {df.storm_id.nunique()} storms from {SYNTHETIC_CSV.name}")
    
    alphas = [0.025, 0.500, 0.975]
    
    # 1. Train GPS models
    gps_models = train_and_tune_model(df, "target_gps_error", alphas, n_trials=15)
    
    # Evaluate GPS on training set for a quick sanity check
    # Normally we'd evaluate on a holdout set, but the Optuna loop already cross-validated the loss.
    X = df[["g_scale", "kp_index", "bz_nt", "wind_speed_km_s", "cme_speed_km_s", "cme_width_deg", "r_scale", "geomag_lat_bin", "local_time_bin"]]
    y_gps = df["target_gps_error"]
    gps_low = gps_models[0.025].predict(X)
    gps_high = gps_models[0.975].predict(X)
    picp_gps, pinaw_gps = calculate_metrics(y_gps, gps_low, gps_high)
    print(f"\nGPS Training Set Sanity Check -> PICP (Coverage): {picp_gps:.2%}, PINAW (Width): {pinaw_gps:.4f}")
    
    # 2. Train HF models
    hf_models = train_and_tune_model(df, "target_hf_prob", alphas, n_trials=15)
    y_hf = df["target_hf_prob"]
    hf_low = hf_models[0.025].predict(X)
    hf_high = hf_models[0.975].predict(X)
    picp_hf, pinaw_hf = calculate_metrics(y_hf, hf_low, hf_high)
    print(f"\nHF Training Set Sanity Check -> PICP (Coverage): {picp_hf:.2%}, PINAW (Width): {pinaw_hf:.4f}")
    
    # 3. Export Models
    print("\nExporting lightweight models...")
    ckpt_dir = CHECKPOINT_DIR
    ckpt_dir.mkdir(parents=True, exist_ok=True)
    
    # Using compress=3 to balance compression ratio and loading speed
    joblib.dump(gps_models[0.025], ckpt_dir / "gps_q025.pkl", compress=3)
    joblib.dump(gps_models[0.500], ckpt_dir / "gps_q500.pkl", compress=3)
    joblib.dump(gps_models[0.975], ckpt_dir / "gps_q975.pkl", compress=3)
    
    joblib.dump(hf_models[0.025], ckpt_dir / "hf_q025.pkl", compress=3)
    joblib.dump(hf_models[0.500], ckpt_dir / "hf_q500.pkl", compress=3)
    joblib.dump(hf_models[0.975], ckpt_dir / "hf_q975.pkl", compress=3)
    
    print(f"Successfully saved 6 models to {ckpt_dir}")

if __name__ == "__main__":
    main()
