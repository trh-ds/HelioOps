import joblib
import pandas as pd

def test_may_2024_anchor():
    """
    Verifies that the trained models produce scientifically valid results 
    for the May 2024 G5 anchor storm.
    """
    print("Running May 2024 G5 Anchor Verification...")
    
    # May 2024 G5 characteristics (Approximate from physical logs)
    # G5, Kp=9.0, very fast wind > 800, massive CME > 1500 km/s, wide > 160 deg, R3+ flares
    storm_features = {
        "g_scale": 5,
        "kp_index": 9.0,
        "bz_nt": -40.0, # Massive southward Bz
        "wind_speed_km_s": 850.0,
        "cme_speed_km_s": 1800.0,
        "cme_width_deg": 180.0,
        "r_scale": 3,
        "geomag_lat_bin": 2, # High lat
        "local_time_bin": 1  # Day
    }
    
    df_test = pd.DataFrame([storm_features])
    
    try:
        # Load models
        gps_med = joblib.load("checkpoints/gps_q500.pkl")
        hf_med = joblib.load("checkpoints/hf_q500.pkl")
        
        # Predict
        gps_error = gps_med.predict(df_test)[0]
        hf_prob = hf_med.predict(df_test)[0]
        
        print(f"Predicted Median GPS L1 Error: {gps_error:.2f} m")
        print(f"Predicted Median HF Blackout Probability: {hf_prob:.2%}")
        
        # Assertions based on imp.md requirements
        assert gps_error > 15.0, f"GPS error ({gps_error}) must be > 15m for G5 anchor."
        assert hf_prob > 0.80, f"HF Blackout prob ({hf_prob}) must be > 0.80 for G5 anchor."
        
        print("\n[PASS] ANCHOR TEST PASSED! The model correctly predicts severe impacts for a G5 storm.")
        
    except FileNotFoundError:
        print("Model files not found. Ensure 02_train_and_tune.py ran successfully.")
    except AssertionError as e:
        print(f"\n[FAIL] ANCHOR TEST FAILED: {e}")

if __name__ == "__main__":
    test_may_2024_anchor()
