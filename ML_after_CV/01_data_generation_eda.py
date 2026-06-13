import pandas as pd
import numpy as np
import os
import matplotlib.pyplot as plt
import seaborn as sns

def generate_synthetic_data(num_storms=100, frames_per_storm=50):
    """
    Generates synthetic space weather data with grouped storm_ids to prevent data leakage.
    Each storm has a base profile, and individual frames have slight variations.
    """
    np.random.seed(42)
    data = []
    
    for storm_idx in range(num_storms):
        storm_id = f"storm_{storm_idx:03d}"
        
        # Base storm characteristics
        # Kp can be anywhere from 1.0 to 9.0, heavily weighted towards lower numbers
        base_kp = np.clip(np.random.gamma(shape=2.0, scale=1.5), 1.0, 9.0)
        base_g_scale = int(max(0, base_kp - 4))
        
        # Wind speed correlates somewhat with Kp
        base_wind = 300 + (base_kp * 70) + np.random.normal(0, 50)
        base_wind = np.clip(base_wind, 250, 2500)
        
        # CME speed and width correlate with severity
        cme_detected = np.random.rand() > 0.3
        if cme_detected:
            base_cme_speed = base_wind * np.random.uniform(1.2, 2.5)
            base_cme_width = np.clip(np.random.normal(120, 60), 10, 360)
        else:
            base_cme_speed = 0
            base_cme_width = 0
            
        base_bz = -np.random.lognormal(mean=1.5, sigma=0.8) if np.random.rand() > 0.5 else np.random.lognormal(mean=1.0, sigma=0.5)
        base_r_scale = np.random.choice([0, 1, 2, 3, 4, 5], p=[0.5, 0.2, 0.15, 0.1, 0.04, 0.01])
        
        # Geographic and temporal features
        geomag_lat_bin = np.random.choice([0, 1, 2])
        local_time_bin = np.random.choice([0, 1])
        
        for frame in range(frames_per_storm):
            # Frame-level variations
            kp = np.clip(base_kp + np.random.normal(0, 0.5), 1.0, 9.0)
            g_scale = int(max(0, kp - 4))
            wind = np.clip(base_wind + np.random.normal(0, 20), 250, 2500)
            bz = base_bz + np.random.normal(0, 2)
            
            # Synthesize targets
            # GPS L1 Error Target
            if kp > 3:
                base_gps_error = 0.30 * ((kp - 3) ** 1.8)
            else:
                base_gps_error = 0.0
                
            lat_modifier = 1.5 if geomag_lat_bin == 2 else (1.2 if geomag_lat_bin == 1 else 1.0)
            bz_modifier = abs(bz) * 0.1 if bz < 0 else 0
            
            # Non-linear kick for high CME speeds
            cme_modifier = (base_cme_speed / 1000) ** 1.5 if base_cme_speed > 1000 else 1.0
            
            target_gps_error = base_gps_error * lat_modifier * cme_modifier + bz_modifier
            target_gps_error += np.random.normal(0, target_gps_error * 0.1)
            target_gps_error = max(0, target_gps_error)
            
            # HF Blackout Target
            target_hf_prob = (base_r_scale * 0.15) + (kp * 0.05)
            if local_time_bin == 1:
                target_hf_prob += 0.2
            
            target_hf_prob = np.clip(target_hf_prob + np.random.normal(0, 0.05), 0.0, 1.0)
            
            data.append({
                "storm_id": storm_id,
                "g_scale": g_scale,
                "kp_index": round(kp, 1),
                "bz_nt": round(bz, 1),
                "wind_speed_km_s": round(wind, 1),
                "cme_speed_km_s": round(base_cme_speed, 1),
                "cme_width_deg": round(base_cme_width, 1),
                "r_scale": base_r_scale,
                "geomag_lat_bin": geomag_lat_bin,
                "local_time_bin": local_time_bin,
                "target_gps_error": round(target_gps_error, 2),
                "target_hf_prob": round(target_hf_prob, 3)
            })
            
    df = pd.DataFrame(data)
    return df

def run_eda(df, output_dir="eda_plots"):
    os.makedirs(output_dir, exist_ok=True)
    
    print(f"Running EDA on dataset with shape: {df.shape}")
    
    # 1. Target Distributions
    plt.figure(figsize=(12, 5))
    plt.subplot(1, 2, 1)
    sns.histplot(df['target_gps_error'], bins=50, kde=True)
    plt.title("Distribution of GPS L1 Error (m)")
    
    plt.subplot(1, 2, 2)
    sns.histplot(df['target_hf_prob'], bins=50, kde=True)
    plt.title("Distribution of HF Blackout Probability")
    
    plt.tight_layout()
    plt.savefig(os.path.join(output_dir, "01_target_distributions.png"))
    plt.close()
    
    # 2. Correlation Matrix
    plt.figure(figsize=(10, 8))
    numeric_df = df.drop(columns=['storm_id'])
    corr = numeric_df.corr()
    sns.heatmap(corr, annot=True, cmap='coolwarm', fmt=".2f", linewidths=0.5)
    plt.title("Feature Correlation Matrix")
    plt.tight_layout()
    plt.savefig(os.path.join(output_dir, "02_correlation_matrix.png"))
    plt.close()
    
    # 3. Kp vs GPS Error Scatter
    plt.figure(figsize=(8, 6))
    sns.scatterplot(x='kp_index', y='target_gps_error', hue='geomag_lat_bin', data=df, alpha=0.6)
    plt.title("Kp Index vs GPS Error by Latitude Bin")
    plt.tight_layout()
    plt.savefig(os.path.join(output_dir, "03_kp_vs_gps.png"))
    plt.close()
    
    # 4. CME Speed vs GPS Error
    plt.figure(figsize=(8, 6))
    sns.scatterplot(x='cme_speed_km_s', y='target_gps_error', data=df, alpha=0.5)
    plt.title("CME Speed vs GPS Error")
    plt.tight_layout()
    plt.savefig(os.path.join(output_dir, "04_cme_speed_vs_gps.png"))
    plt.close()
    
    print(f"EDA complete. Plots saved to {output_dir}/")

if __name__ == "__main__":
    os.makedirs("data", exist_ok=True)
    df = generate_synthetic_data(num_storms=120, frames_per_storm=40)
    df.to_csv("data/synthetic_storms.csv", index=False)
    print("Synthetic data generated and saved to data/synthetic_storms.csv")
    
    run_eda(df, output_dir="eda_plots")
