import pandas as pd
import joblib
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score
import numpy as np

def main():
    df = pd.read_csv("data/synthetic_storms.csv")
    features = ["g_scale", "kp_index", "bz_nt", "wind_speed_km_s", "cme_speed_km_s", "cme_width_deg", "r_scale", "geomag_lat_bin", "local_time_bin"]
    X = df[features]
    
    # Evaluate GPS Error Model
    y_gps = df["target_gps_error"]
    gps_med = joblib.load("checkpoints/gps_q500.pkl")
    preds_gps = gps_med.predict(X)
    
    print("--- Traditional Metrics for GPS L1 Error (Median) ---")
    print(f"R^2 Score: {r2_score(y_gps, preds_gps):.4f}")
    print(f"MAE: {mean_absolute_error(y_gps, preds_gps):.4f}")
    print(f"RMSE: {np.sqrt(mean_squared_error(y_gps, preds_gps)):.4f}")
    print()
    
    # Evaluate HF Blackout Probability Model
    y_hf = df["target_hf_prob"]
    hf_med = joblib.load("checkpoints/hf_q500.pkl")
    preds_hf = hf_med.predict(X)
    
    print("--- Traditional Metrics for HF Radio Blackout (Median) ---")
    print(f"R^2 Score: {r2_score(y_hf, preds_hf):.4f}")
    print(f"MAE: {mean_absolute_error(y_hf, preds_hf):.4f}")
    print(f"RMSE: {np.sqrt(mean_squared_error(y_hf, preds_hf)):.4f}")

if __name__ == "__main__":
    main()
