# ML/DL Implementation Plan: Impact Intelligence (Layer 2)

Based on the latest architectural changes (Option C), the Computer Vision (CV) pipeline for CME detection has been replaced by a deterministic threshold detector and the DONKI API. Therefore, your focus for the ML/DL part of HelioOps is entirely on **Layer 2: Impact Intelligence**.

This layer uses machine learning to translate abstract space weather physics into concrete, real-world impact numbers with confidence intervals.

---

## 1. Connectivity with the CV Model (Inputs)

The ML model is the immediate downstream consumer of the **Heliospheric Detection (Layer 1)**. 

### How Input is Taken
The CV pipeline outputs a `StormEvent` JSON object. Your ML pipeline will consume this JSON to build the feature vector ($X$).

### Why CV Input is Crucial & Its Impact on the ML Model
The CV/Detection layer provides kinematics directly from the sun:
*   `cme_speed_km_s`
*   `cme_width_deg`
*   `flare.class` & `r_scale`

**Why we need this:** Reactive metrics like `kp_index` or L1 `wind_speed_km_s` only trigger when the storm is already hitting Earth (or is 30 minutes away). The CV parameters (`cme_speed` and `cme_width`) are our **predictive drivers**. 
**Impact on the Model:** Faster, wider CMEs compress the Earth's magnetosphere more violently. The inclusion of `cme_speed_km_s` allows the ML model to predict non-linear spikes in GPS error and HF blackout probabilities *days before* the storm hits. Without this CV connectivity, the model would only act as a reactive look-up table. The optimum connectivity is achieved by parsing the `StormEvent` contract directly into the Pandas DataFrame used for model inference.

---

## 2. Data Acquisition, Structure, and EDA

### Data Finding & Structure
Use the NOAA 2000–2024 storm events archive (`data/training/noaa_archive/`). 
The core data structure is a **Pandas DataFrame** containing 9 feature columns:
1. `g_scale` (0-5)
2. `kp_index` (0.0 - 9.0)
3. `bz_nt` (Interplanetary Magnetic Field Z-component)
4. `wind_speed_km_s` (L1 Solar wind speed)
5. `cme_speed_km_s` (From CV)
6. `cme_width_deg` (From CV)
7. `r_scale` (0-5)
8. `geomag_lat_bin` (0=equatorial, 1=mid-lat, 2=high-lat >60°)
9. `local_time_bin` (0=night, 1=day)

**Generating Target Variables (Since real logs are sparse):**
Use the validated proxy formulas to synthesize training labels:
*   **GPS Error Target:** `0.162 * ((kp_index - 3) ** 1.8) * lat_modifier + bz_modifier + noise`
*   **HF Blackout Target:** `(r_scale * 0.15) + (kp_index * 0.05) + daylight_modifier + noise`

### Exploratory Data Analysis (EDA)
**Do not jump straight to modeling.** Perform EDA to understand the feature space:
1.  **Feature Distributions:** Plot histograms of `bz_nt`, `wind_speed`, etc., to identify heavy tails or outliers.
2.  **Correlation Matrix:** Check for multicollinearity (e.g., highly correlated `g_scale` and `kp_index`).
3.  **Scatter Plots:** Map `cme_speed_km_s` vs. the synthesized GPS error to visualize the non-linear relationship.
4.  **Temporal Analysis:** Plot storm frequency over the solar cycle to ensure your train/test split has a representative sample of Solar Maximums and Minimums.

---

## 3. Data Splitting & Leakage Prevention

**CRITICAL: Data Leakage Prevention**
Solar storms are temporal events. Consecutive 15-minute frames of the same storm are highly correlated. If you use a standard `train_test_split()`, frames from the exact same storm will end up in both the training and testing sets, causing massive data leakage and artificially high performance.

**Solution:** Use **Group-based Splitting** grouped by `storm_id`.
*   Ensure that all data points from a specific storm (e.g., `2003-Halloween-Storm`) remain entirely within either the training set or the validation set.

### 5-Fold Cross Validation
Use `GroupKFold(n_splits=5)` grouped by `storm_id`. This validates that your model generalizes well to *unseen future storms*, rather than just memorizing frames of storms it has already seen.

---

## 4. Model Selection & Hyperparameter Tuning

### Model Selection (Don't Stick to Just One)
While **LightGBM** is the baseline due to its speed and native quantile regression, it relies on greedy tree-building. You must test and compare multiple architectures to find the best fit:
1.  **LightGBM:** Fast, handles NaNs, native quantile objective.
2.  **CatBoost:** Excellent if we introduce more categorical variables (like sensor IDs or specific orbital paths). Often more robust against overfitting than LightGBM.
3.  **XGBoost:** The industry standard for tabular data. Try it to see if exact greedy algorithms outperform LightGBM's histogram-based approach.
4.  **PyTorch / Neural Networks:** Using a simple MLP with a custom **Pinball Loss** function. NNs can jointly predict the 0.025, 0.50, and 0.975 quantiles simultaneously, which explicitly prevents "quantile crossing" (where the lower bound accidentally predicts a higher value than the median).

### Optuna for Hyperparameter Tuning
To save time and systematically find the best model, use **Optuna**.
Set up an Optuna study that loops through your 5-Fold CV:
```python
import optuna

def objective(trial):
    params = {
        'learning_rate': trial.suggest_float('learning_rate', 1e-3, 0.1, log=True),
        'max_depth': trial.suggest_int('max_depth', 3, 10),
        'num_leaves': trial.suggest_int('num_leaves', 20, 100)
    }
    # Run 5-fold GroupKFold CV and return the average Pinball Loss
    return average_cv_loss

study = optuna.create_study(direction='minimize')
study.optimize(objective, n_trials=50)
```

---

## 5. Evaluation Metrics & Verification

Standard metrics like RMSE or MAE are insufficient for quantile regression. You must use specific metrics to verify if "we are doing everything perfect".

### Required Evaluation Metrics:
1.  **Pinball Loss (Quantile Loss):** The primary metric to minimize. It penalizes over-predictions and under-predictions asymmetrically based on the target quantile (e.g., `alpha=0.975` heavily penalizes under-predicting the worst-case scenario).
2.  **Prediction Interval Coverage Probability (PICP):** Check if your 95% Confidence Interval *actually* contains 95% of the validation ground truths. If PICP is 80%, your model is overconfident.
3.  **Prediction Interval Normalized Average Width (PINAW):** If the interval is [0, 1000m] for GPS error, it's useless. PINAW measures how tight and useful the intervals are.

### Final Anchor Verification
Pass the documented **May 2024 G5 storm** feature vector into your final tuned models.
*   `gps_med.predict(X)` **must** be > 15m.
*   `hf_med.predict(X)` **must** be > 0.80.
If it fails this anchor test, the model is scientifically invalid for our operational use case, regardless of its CV loss.

---

## 6. Output Generation & Model Optimization

The final deliverable is the trained model files for Layer 2.

### Optimization & Lightweight Constraints
The backend needs to load these models into memory quickly and run them in milliseconds. 
*   **Limit Tree Size:** Limit `max_depth` and `n_estimators` via Optuna to prevent bloated models.
*   **Compression:** When exporting, use `joblib` with high compression or convert the model to **ONNX** format for the absolute lowest latency and smallest file size.

### Required Files
Save the finalized models (one for each quantile) in the exact expected paths:
*   `ml/checkpoints/impact-v0.3-frozen/gps_q025.pkl`
*   `ml/checkpoints/impact-v0.3-frozen/gps_q500.pkl`
*   `ml/checkpoints/impact-v0.3-frozen/gps_q975.pkl`
*(And similarly for HF Blackout models).*

By following this expanded plan, you ensure no data leakage, highly optimized hyperparameters, robust model comparison, and scientifically verified outputs suitable for mission-critical operations.
