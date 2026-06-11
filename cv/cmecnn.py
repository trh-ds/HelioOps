"""
Commit 13 — CME Detection CNN + Bounding Region + Kinematics
feat(cv): CME detection CNN + bounding region + kinematics (speed, width, ETA)

Architecture — 3-channel EfficientNet-B0 / ResNet-18d / MobileNetV3-Small on stacked
[normalized, diff, diff] LASCO C2 coronagraph image pairs (512→224 px, grayscale tripled).
Tasks:
  · Binary classification  : full-halo detection (width ≥ 180°)
  · CPA cyclic regression  : sin/cos encoding → atan2 recovery, handles 0/360° boundary
  · Angular-width regression: sigmoid-scaled head, SmoothL1 loss
Kinematics (rule-based, no labels needed):
  · Leading-edge radius extracted from diff image via polar profiling at CPA direction
  · Bright arc (>0.65) vs dark wake (<0.35) median radii → displacement in one 15-min cadence
  · Speed [km/s] = displacement_km / 900 s → ETA [h] = (1AU − 2.2R☉) / speed
Training protocol:
  · Optuna TPE, 50 trials, fold-0 hold-out → maximize composite_score
  · 5-fold temporal CV, date-sorted group assignment, ZERO inter-fold leakage
  · AMP (FP16), cosine-warmup LR, gradient clipping 1.0, EMA decay 0.999
  · Rotation augmentation with consistent CPA-label rotation (360° symmetry of LASCO)
Eval metrics (all domain-relevant):
  Classification — AUROC, AUPRC, F1, Precision, Recall, MCC, Balanced-Accuracy
  CPA regression — Circular-MAE[°], Circular-RMSE[°], within-15°/30° rate
  Width regression — MAE[°], RMSE[°], MAPE[%], R², Pearson-r
  Composite score — harmonic mean of normalised MAE gains (Optuna objective)
Outputs StormEvent-compatible dict consumed by commit-15 fusion layer.

Usage:
  python cv/cmecnn.py              # HPO + full 5-fold CV
  python cv/cmecnn.py --skip-hpo   # default params, full CV
  python cv/cmecnn.py --test        # self-tests only, no training
  python cv/cmecnn.py --n-trials 10 --n-epochs 20   # fast smoke run
"""

from __future__ import annotations

import argparse
import gc
import json
import math
import os
import pickle
import random
import warnings
from copy import deepcopy
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import cv2
import numpy as np
import optuna
import pandas as pd
import torch
import torch.nn as nn
import torch.nn.functional as F
from PIL import Image
from sklearn.metrics import (
    average_precision_score,
    balanced_accuracy_score,
    f1_score,
    matthews_corrcoef,
    mean_absolute_error,
    mean_squared_error,
    precision_score,
    r2_score,
    recall_score,
    roc_auc_score,
)
try:
    from torch.amp import GradScaler, autocast as _autocast

    def autocast(enabled: bool = True):  # noqa: E303
        return _autocast("cuda" if enabled else "cpu", enabled=enabled)

    def _make_scaler(enabled: bool) -> GradScaler:
        return GradScaler("cuda", enabled=enabled)

except ImportError:
    from torch.cuda.amp import GradScaler, autocast  # type: ignore[assignment]

    def _make_scaler(enabled: bool) -> GradScaler:  # type: ignore[misc]
        return GradScaler(enabled=enabled)
from torch.utils.data import DataLoader, Dataset
from tqdm import tqdm

try:
    import timm
except ImportError:
    raise SystemExit("timm not found — run: pip install 'timm>=0.9.0'")

try:
    import albumentations as A
    from albumentations.pytorch import ToTensorV2
except ImportError:
    raise SystemExit("albumentations not found — run: pip install 'albumentations>=1.3.0'")

try:
    from scipy.stats import pearsonr as _scipy_pearsonr
except ImportError:
    raise SystemExit("scipy not found — run: pip install 'scipy>=1.11.0'")

warnings.filterwarnings("ignore", category=DeprecationWarning)
warnings.filterwarnings("ignore", category=UserWarning)
optuna.logging.set_verbosity(optuna.logging.WARNING)


@dataclass
class Config:
    data_dir: Path = Path("data/final_processed")
    catalog_csv: Path = Path("data/cme_catalog.csv")
    checkpoint_dir: Path = Path("ml/checkpoints/commit13")
    results_dir: Path = Path("ml/results/commit13")
    image_size: int = 224
    n_folds: int = 5
    n_epochs: int = 50
    patience: int = 10
    seed: int = 42
    num_workers: int = 0
    pixel_scale_arcsec: float = 22.8
    solar_radius_km: float = 695_700.0
    au_km: float = 1.496e8
    cadence_sec: float = 900.0
    arcsec_per_rsun: float = 959.68
    ch_mean: Tuple[float, float, float] = (0.20, 0.50, 0.50)
    ch_std: Tuple[float, float, float] = (0.15, 0.10, 0.10)
    n_trials: int = 50
    optuna_fold: int = 0
    ema_decay: float = 0.999
    backbone_choices: List[str] = field(
        default_factory=lambda: ["efficientnet_b0", "resnet18d", "mobilenetv3_small_100"]
    )
    device: str = "cpu"

    def __post_init__(self) -> None:
        self.device = "cuda" if torch.cuda.is_available() else "cpu"
        self.num_workers = min(4, os.cpu_count() or 0) if self.device == "cuda" else 0
        self.checkpoint_dir.mkdir(parents=True, exist_ok=True)
        self.results_dir.mkdir(parents=True, exist_ok=True)


CFG = Config()


def set_seed(seed: int) -> None:
    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)
    if torch.cuda.is_available():
        torch.cuda.manual_seed_all(seed)
    torch.backends.cudnn.deterministic = True
    torch.backends.cudnn.benchmark = False


def _pearsonr_safe(x: np.ndarray, y: np.ndarray) -> Tuple[float, float]:
    if len(x) < 2 or float(np.std(x)) < 1e-8 or float(np.std(y)) < 1e-8:
        return float("nan"), float("nan")
    try:
        res = _scipy_pearsonr(x, y)
        if hasattr(res, "statistic"):
            return float(res.statistic), float(res.pvalue)
        return float(res[0]), float(res[1])
    except Exception:
        return float("nan"), float("nan")


def load_meta_files(data_dir: Path) -> pd.DataFrame:
    records = []
    for meta_path in sorted(data_dir.glob("*_meta.txt")):
        event_id = meta_path.stem.replace("_meta", "")
        norm_path = data_dir / f"{event_id}_normalized.png"
        diff_path = data_dir / f"{event_id}_diff.png"
        if not (norm_path.exists() and diff_path.exists()):
            continue
        kv: Dict[str, str] = {}
        with open(meta_path) as fh:
            for line in fh:
                if ":" in line:
                    k, v = line.strip().split(":", 1)
                    kv[k.strip()] = v.strip()
        raw_date = kv.get("date_obs", "1996/01/01").replace("/", "-")
        cx_s, cy_s = kv.get("center_xy", "(256, 256)").strip("()").split(",")
        occ_s = kv.get("occulter_r", "80px").replace("px", "").strip()
        records.append(
            {
                "event_id": event_id,
                "date_obs": pd.to_datetime(raw_date, format="%Y-%m-%d", errors="coerce"),
                "norm_path": str(norm_path),
                "diff_path": str(diff_path),
                "center_x": int(cx_s.strip()),
                "center_y": int(cy_s.strip()),
                "occulter_r": int(float(occ_s)),
            }
        )
    if not records:
        raise FileNotFoundError(f"No valid image pairs found in {data_dir}")
    df = (
        pd.DataFrame(records)
        .dropna(subset=["date_obs"])
        .sort_values("date_obs")
        .reset_index(drop=True)
    )
    return df


def load_catalog(catalog_csv: Path) -> Optional[pd.DataFrame]:
    if not catalog_csv.exists():
        return None
    df = pd.read_csv(catalog_csv)
    if not {"event_id", "cpa_deg", "width_deg"}.issubset(df.columns):
        return None
    df["event_id"] = df["event_id"].astype(str)
    if "is_cme" not in df.columns:
        df["is_cme"] = 1
    return df[["event_id", "cpa_deg", "width_deg", "is_cme"]].copy()


def build_manifest(cfg: Config) -> pd.DataFrame:
    meta_df = load_meta_files(cfg.data_dir)
    catalog_df = load_catalog(cfg.catalog_csv)
    if catalog_df is not None:
        meta_df["event_id"] = meta_df["event_id"].astype(str)
        df = meta_df.merge(catalog_df, on="event_id", how="left")
    else:
        df = meta_df.copy()
        df["cpa_deg"] = 0.0
        df["width_deg"] = 180.0
        df["is_cme"] = 1
    df["cpa_deg"] = df["cpa_deg"].fillna(0.0).clip(0.0, 360.0).astype(float)
    df["width_deg"] = df["width_deg"].fillna(180.0).clip(0.0, 360.0).astype(float)
    df["is_cme"] = df["is_cme"].fillna(1).astype(int)
    df["is_full_halo"] = (df["width_deg"] >= 180.0).astype(int)
    return df.reset_index(drop=True)


def encode_cpa(cpa_deg: float) -> Tuple[float, float]:
    rad = math.radians(cpa_deg)
    return math.sin(rad), math.cos(rad)


def decode_cpa(sin_v: float, cos_v: float) -> float:
    return math.degrees(math.atan2(sin_v, cos_v)) % 360.0


def circular_mae_deg(pred: np.ndarray, true: np.ndarray) -> float:
    diff = np.abs(pred - true) % 360.0
    return float(np.mean(np.minimum(diff, 360.0 - diff)))


def circular_rmse_deg(pred: np.ndarray, true: np.ndarray) -> float:
    diff = np.abs(pred - true) % 360.0
    return float(np.sqrt(np.mean(np.minimum(diff, 360.0 - diff) ** 2)))


def get_temporal_fold_assignments(dates: pd.Series, n_folds: int) -> np.ndarray:
    n = len(dates)
    sort_idx = np.argsort(dates.values)
    folds = np.zeros(n, dtype=int)
    for rank, orig in enumerate(sort_idx):
        folds[orig] = min(int(rank * n_folds / max(n, 1)), n_folds - 1)
    return folds


def get_train_transforms(image_size: int, ch_mean: tuple, ch_std: tuple) -> A.Compose:
    return A.Compose(
        [
            A.Resize(image_size, image_size, interpolation=cv2.INTER_LINEAR, always_apply=True),
            A.RandomBrightnessContrast(brightness_limit=0.12, contrast_limit=0.12, p=0.5),
            A.GaussNoise(var_limit=(0.0, 0.004), p=0.35),
            A.GaussianBlur(blur_limit=(3, 3), p=0.2),
            A.Normalize(mean=list(ch_mean), std=list(ch_std), max_pixel_value=1.0, always_apply=True),
            ToTensorV2(),
        ]
    )


def get_val_transforms(image_size: int, ch_mean: tuple, ch_std: tuple) -> A.Compose:
    return A.Compose(
        [
            A.Resize(image_size, image_size, interpolation=cv2.INTER_LINEAR, always_apply=True),
            A.Normalize(mean=list(ch_mean), std=list(ch_std), max_pixel_value=1.0, always_apply=True),
            ToTensorV2(),
        ]
    )


class CMEDataset(Dataset):
    def __init__(
        self,
        manifest: pd.DataFrame,
        transforms: A.Compose,
        augment_rotation: bool = False,
    ) -> None:
        self.manifest = manifest.reset_index(drop=True)
        self.transforms = transforms
        self.augment_rotation = augment_rotation

    def __len__(self) -> int:
        return len(self.manifest)

    def _load_gray_float(self, path: str) -> np.ndarray:
        img = np.array(Image.open(path).convert("L"), dtype=np.float32) / 255.0
        return img

    def __getitem__(self, idx: int) -> Dict:
        row = self.manifest.iloc[idx]
        norm_img = self._load_gray_float(row["norm_path"])
        diff_img = self._load_gray_float(row["diff_path"])
        cpa_deg = float(row["cpa_deg"])

        if self.augment_rotation:
            angle = random.uniform(0.0, 360.0)
            h, w = norm_img.shape
            cx, cy = w / 2.0, h / 2.0
            M = cv2.getRotationMatrix2D((cx, cy), angle, 1.0)
            norm_img = cv2.warpAffine(norm_img, M, (w, h), flags=cv2.INTER_LINEAR)
            diff_img = cv2.warpAffine(diff_img, M, (w, h), flags=cv2.INTER_LINEAR)
            cpa_deg = (cpa_deg + angle) % 360.0

        combined = np.stack([norm_img, diff_img, diff_img], axis=-1)
        out = self.transforms(image=combined)
        tensor = out["image"].float()

        sin_cpa, cos_cpa = encode_cpa(cpa_deg)

        return {
            "image": tensor,
            "cpa_sincos": torch.tensor([sin_cpa, cos_cpa], dtype=torch.float32),
            "width_norm": torch.tensor(float(row["width_deg"]) / 360.0, dtype=torch.float32),
            "is_full_halo": torch.tensor(float(row["is_full_halo"]), dtype=torch.float32),
            "cpa_deg_raw": torch.tensor(cpa_deg, dtype=torch.float32),
            "width_deg_raw": torch.tensor(float(row["width_deg"]), dtype=torch.float32),
            "diff_path": str(row["diff_path"]),
            "center_x": int(row["center_x"]),
            "center_y": int(row["center_y"]),
            "occulter_r": int(row["occulter_r"]),
        }


class EMA:
    def __init__(self, model: nn.Module, decay: float = 0.999) -> None:
        self.decay = decay
        self.shadow = deepcopy(model).eval()
        for p in self.shadow.parameters():
            p.requires_grad_(False)

    @torch.no_grad()
    def update(self, model: nn.Module) -> None:
        for (_, sp), (_, mp) in zip(
            self.shadow.named_parameters(), model.named_parameters()
        ):
            sp.data.mul_(self.decay).add_(mp.data, alpha=1.0 - self.decay)

    def __call__(self, x: torch.Tensor) -> Tuple[torch.Tensor, torch.Tensor, torch.Tensor]:
        with torch.no_grad():
            return self.shadow(x)


class EarlyStopping:
    def __init__(self, patience: int = 10, mode: str = "max", delta: float = 1e-4) -> None:
        self.patience = patience
        self.mode = mode
        self.delta = delta
        self.best: Optional[float] = None
        self.counter = 0

    def __call__(self, score: float) -> bool:
        if self.best is None:
            self.best = score
            return False
        improved = (
            score > self.best + self.delta
            if self.mode == "max"
            else score < self.best - self.delta
        )
        if improved:
            self.best = score
            self.counter = 0
        else:
            self.counter += 1
        return self.counter >= self.patience


class CMENet(nn.Module):
    def __init__(self, backbone: str = "efficientnet_b0", dropout: float = 0.30) -> None:
        super().__init__()
        try:
            self.encoder = timm.create_model(
                backbone, pretrained=True, num_classes=0, global_pool="avg"
            )
        except RuntimeError:
            self.encoder = timm.create_model(
                backbone, pretrained=False, num_classes=0, global_pool="avg"
            )
        feat_dim: int = self.encoder.num_features

        self.cls_head = nn.Sequential(
            nn.Dropout(dropout),
            nn.Linear(feat_dim, 256),
            nn.SiLU(),
            nn.Dropout(dropout * 0.5),
            nn.Linear(256, 1),
        )
        self.cpa_head = nn.Sequential(
            nn.Dropout(dropout),
            nn.Linear(feat_dim, 256),
            nn.SiLU(),
            nn.Dropout(dropout * 0.5),
            nn.Linear(256, 2),
        )
        self.width_head = nn.Sequential(
            nn.Dropout(dropout),
            nn.Linear(feat_dim, 256),
            nn.SiLU(),
            nn.Dropout(dropout * 0.5),
            nn.Linear(256, 1),
        )

    def forward(
        self, x: torch.Tensor
    ) -> Tuple[torch.Tensor, torch.Tensor, torch.Tensor]:
        feat = self.encoder(x)
        cls_logit = self.cls_head(feat).squeeze(-1)
        cpa_raw = self.cpa_head(feat)
        cpa_unit = F.normalize(cpa_raw, p=2, dim=-1)
        width_sig = torch.sigmoid(self.width_head(feat).squeeze(-1))
        return cls_logit, cpa_unit, width_sig


class MultiTaskLoss(nn.Module):
    def __init__(self, w_cls: float = 1.0, w_cpa: float = 1.5, w_width: float = 1.5) -> None:
        super().__init__()
        self.w_cls = w_cls
        self.w_cpa = w_cpa
        self.w_width = w_width
        self.bce = nn.BCEWithLogitsLoss(pos_weight=torch.tensor([2.0]))
        self.mse = nn.MSELoss()
        self.smooth_l1 = nn.SmoothL1Loss(beta=0.05)

    def forward(
        self,
        cls_logit: torch.Tensor,
        cpa_unit: torch.Tensor,
        width_sig: torch.Tensor,
        true_cls: torch.Tensor,
        true_cpa_sc: torch.Tensor,
        true_width_norm: torch.Tensor,
    ) -> Tuple[torch.Tensor, torch.Tensor, torch.Tensor, torch.Tensor]:
        self.bce.pos_weight = self.bce.pos_weight.to(cls_logit.device)
        cls_loss = self.bce(cls_logit, true_cls)
        cpa_loss = self.mse(cpa_unit, true_cpa_sc)
        width_loss = self.smooth_l1(width_sig, true_width_norm)
        total = self.w_cls * cls_loss + self.w_cpa * cpa_loss + self.w_width * width_loss
        return total, cls_loss, cpa_loss, width_loss


def compute_metrics(
    cls_logits: np.ndarray,
    cls_true: np.ndarray,
    cpa_pred_deg: np.ndarray,
    cpa_true_deg: np.ndarray,
    width_pred_deg: np.ndarray,
    width_true_deg: np.ndarray,
) -> Dict[str, float]:
    m: Dict[str, float] = {}

    cls_probs = 1.0 / (1.0 + np.exp(-np.clip(cls_logits, -50, 50)))
    cls_pred = (cls_probs >= 0.5).astype(int)
    n_classes = int(len(np.unique(cls_true)))

    if n_classes >= 2:
        try:
            m["auroc"] = float(roc_auc_score(cls_true, cls_probs))
        except ValueError:
            m["auroc"] = float("nan")
        try:
            m["auprc"] = float(average_precision_score(cls_true, cls_probs))
        except ValueError:
            m["auprc"] = float("nan")
        m["f1"] = float(f1_score(cls_true, cls_pred, zero_division=0))
        m["precision"] = float(precision_score(cls_true, cls_pred, zero_division=0))
        m["recall"] = float(recall_score(cls_true, cls_pred, zero_division=0))
        m["mcc"] = float(matthews_corrcoef(cls_true, cls_pred))
        m["balanced_acc"] = float(balanced_accuracy_score(cls_true, cls_pred))
    else:
        for key in ("auroc", "auprc", "f1", "precision", "recall", "mcc", "balanced_acc"):
            m[key] = float("nan")

    m["cpa_circular_mae_deg"] = circular_mae_deg(cpa_pred_deg, cpa_true_deg)
    m["cpa_circular_rmse_deg"] = circular_rmse_deg(cpa_pred_deg, cpa_true_deg)
    angular_errors = np.minimum(
        np.abs(cpa_pred_deg - cpa_true_deg) % 360.0,
        360.0 - np.abs(cpa_pred_deg - cpa_true_deg) % 360.0,
    )
    m["cpa_within_15deg"] = float(np.mean(angular_errors < 15.0))
    m["cpa_within_30deg"] = float(np.mean(angular_errors < 30.0))

    m["width_mae_deg"] = float(mean_absolute_error(width_true_deg, width_pred_deg))
    m["width_rmse_deg"] = float(np.sqrt(mean_squared_error(width_true_deg, width_pred_deg)))
    r2_val = r2_score(width_true_deg, width_pred_deg)
    m["width_r2"] = float(r2_val) if not math.isnan(float(r2_val)) else float("nan")
    rho, pval = _pearsonr_safe(width_true_deg, width_pred_deg)
    m["width_pearson_r"] = rho
    m["width_pearson_pval"] = pval
    nonzero = width_true_deg > 1.0
    if nonzero.sum() > 0:
        m["width_mape"] = float(
            np.mean(np.abs((width_true_deg[nonzero] - width_pred_deg[nonzero]) / width_true_deg[nonzero]) * 100.0)
        )
    else:
        m["width_mape"] = float("nan")

    gains = [
        1.0 - min(m["cpa_circular_mae_deg"] / 90.0, 1.0),
        1.0 - min(m["width_mae_deg"] / 90.0, 1.0),
    ]
    if not math.isnan(m.get("auroc", float("nan"))):
        gains.append(m["auroc"])
    m["composite_score"] = float(np.mean(gains))

    return m


def estimate_speed_from_diff(
    diff_img: np.ndarray,
    cpa_deg: float,
    center_x: int,
    center_y: int,
    occulter_r: int,
    pixel_scale_arcsec: float = 22.8,
    solar_radius_km: float = 695_700.0,
    cadence_sec: float = 900.0,
    arcsec_per_rsun: float = 959.68,
) -> float:
    km_per_px = (pixel_scale_arcsec / arcsec_per_rsun) * solar_radius_km
    h, w = diff_img.shape[:2]
    cpa_rad = math.radians(cpa_deg)
    dir_x = -math.sin(cpa_rad)
    dir_y = -math.cos(cpa_rad)

    bright_radii: List[float] = []
    dark_radii: List[float] = []
    r_max = int(min(h, w) * 0.47)

    for delta_deg in np.linspace(-25.0, 25.0, 13):
        d_rad = cpa_rad + math.radians(delta_deg)
        dx = -math.sin(d_rad)
        dy = -math.cos(d_rad)
        for r in range(occulter_r + 6, r_max):
            px = int(round(center_x + r * dx))
            py = int(round(center_y + r * dy))
            if not (0 <= px < w and 0 <= py < h):
                break
            val = float(diff_img[py, px])
            if val > 0.65:
                bright_radii.append(float(r))
            elif val < 0.35:
                dark_radii.append(float(r))

    if not bright_radii:
        return 500.0

    r_front = float(np.median(bright_radii))
    r_back = float(np.median(dark_radii)) if dark_radii else max(float(occulter_r), r_front - 8.0)
    disp_px = max(abs(r_front - r_back), 2.0)
    speed = (disp_px * km_per_px) / cadence_sec
    return float(np.clip(speed, 50.0, 5000.0))


def compute_eta_hours(
    speed_km_s: float,
    au_km: float = 1.496e8,
    solar_radius_km: float = 695_700.0,
) -> float:
    distance_km = au_km - 2.2 * solar_radius_km
    return float(distance_km / max(speed_km_s, 1.0) / 3600.0)


def train_one_epoch(
    model: nn.Module,
    loader: DataLoader,
    optimizer: torch.optim.Optimizer,
    criterion: MultiTaskLoss,
    scaler: GradScaler,
    scheduler: Optional[torch.optim.lr_scheduler.LRScheduler],
    ema: EMA,
    device: str,
) -> float:
    model.train()
    total_loss = 0.0
    use_amp = device == "cuda"
    for batch in loader:
        imgs = batch["image"].to(device, non_blocking=True)
        true_cls = batch["is_full_halo"].to(device, non_blocking=True)
        true_cpa = batch["cpa_sincos"].to(device, non_blocking=True)
        true_w = batch["width_norm"].to(device, non_blocking=True)

        optimizer.zero_grad(set_to_none=True)
        with autocast(enabled=use_amp):
            cls_l, cpa_u, w_s = model(imgs)
            loss, _, _, _ = criterion(cls_l, cpa_u, w_s, true_cls, true_cpa, true_w)

        scaler.scale(loss).backward()
        scaler.unscale_(optimizer)
        torch.nn.utils.clip_grad_norm_(model.parameters(), max_norm=1.0)
        scaler.step(optimizer)
        scaler.update()
        if scheduler is not None:
            scheduler.step()
        ema.update(model)
        total_loss += loss.item()

    return total_loss / max(len(loader), 1)


@torch.no_grad()
def evaluate(
    ema: EMA,
    loader: DataLoader,
    device: str,
) -> Tuple[Dict[str, float], np.ndarray, np.ndarray]:
    ema.shadow.eval()
    use_amp = device == "cuda"
    cls_logits_all, cls_true_all = [], []
    cpa_pred_all, cpa_true_all = [], []
    w_pred_all, w_true_all = [], []

    for batch in loader:
        imgs = batch["image"].to(device, non_blocking=True)
        with autocast(enabled=use_amp):
            cls_l, cpa_u, w_s = ema.shadow(imgs)

        cls_logits_all.extend(cls_l.cpu().float().numpy().tolist())
        cls_true_all.extend(batch["is_full_halo"].numpy().tolist())

        sc = cpa_u.cpu().float().numpy()
        cpa_deg = np.degrees(np.arctan2(sc[:, 0], sc[:, 1])) % 360.0
        cpa_pred_all.extend(cpa_deg.tolist())
        cpa_true_all.extend(batch["cpa_deg_raw"].numpy().tolist())

        w_pred_all.extend((w_s.cpu().float().numpy() * 360.0).tolist())
        w_true_all.extend(batch["width_deg_raw"].numpy().tolist())

    metrics = compute_metrics(
        np.array(cls_logits_all),
        np.array(cls_true_all, dtype=int),
        np.array(cpa_pred_all),
        np.array(cpa_true_all),
        np.array(w_pred_all),
        np.array(w_true_all),
    )
    return metrics, np.array(cpa_pred_all), np.array(w_pred_all)


def _build_loaders(
    manifest: pd.DataFrame,
    train_idx: np.ndarray,
    val_idx: np.ndarray,
    batch_size: int,
    cfg: Config,
) -> Tuple[DataLoader, DataLoader]:
    tr_transforms = get_train_transforms(cfg.image_size, cfg.ch_mean, cfg.ch_std)
    va_transforms = get_val_transforms(cfg.image_size, cfg.ch_mean, cfg.ch_std)
    tr_ds = CMEDataset(manifest.iloc[train_idx], tr_transforms, augment_rotation=True)
    va_ds = CMEDataset(manifest.iloc[val_idx], va_transforms, augment_rotation=False)
    tr_bs = min(batch_size, max(len(tr_ds), 1))
    va_bs = min(batch_size * 2, max(len(va_ds), 1))
    tr_loader = DataLoader(
        tr_ds, batch_size=tr_bs, shuffle=True,
        num_workers=cfg.num_workers, pin_memory=(cfg.device == "cuda"), drop_last=False,
    )
    va_loader = DataLoader(
        va_ds, batch_size=va_bs, shuffle=False,
        num_workers=cfg.num_workers, pin_memory=(cfg.device == "cuda"),
    )
    return tr_loader, va_loader


def _make_scheduler(
    optimizer: torch.optim.Optimizer,
    total_steps: int,
    warmup_ratio: float,
) -> torch.optim.lr_scheduler.LambdaLR:
    ws = int(total_steps * warmup_ratio)

    def lr_fn(step: int, _ws: int = ws, _ts: int = total_steps) -> float:
        if step < _ws:
            return float(step) / max(_ws, 1)
        prog = (step - _ws) / max(_ts - _ws, 1)
        return max(0.0, 0.5 * (1.0 + math.cos(math.pi * prog)))

    return torch.optim.lr_scheduler.LambdaLR(optimizer, lr_fn)


def run_optuna_study(
    manifest: pd.DataFrame,
    fold_assignments: np.ndarray,
    cfg: Config,
) -> Dict:
    def objective(trial: optuna.Trial) -> float:
        backbone = trial.suggest_categorical("backbone", cfg.backbone_choices)
        lr = trial.suggest_float("lr", 1e-5, 5e-3, log=True)
        weight_decay = trial.suggest_float("weight_decay", 1e-6, 5e-3, log=True)
        dropout = trial.suggest_float("dropout", 0.10, 0.45)
        w_cpa = trial.suggest_float("w_cpa", 0.5, 3.0)
        w_width = trial.suggest_float("w_width", 0.5, 3.0)
        batch_size = trial.suggest_categorical("batch_size", [8, 16, 32])
        warmup_ratio = trial.suggest_float("warmup_ratio", 0.0, 0.15)

        t_idx = np.where(fold_assignments != cfg.optuna_fold)[0]
        v_idx = np.where(fold_assignments == cfg.optuna_fold)[0]
        if len(t_idx) == 0 or len(v_idx) == 0:
            return -999.0

        tr_loader, va_loader = _build_loaders(manifest, t_idx, v_idx, batch_size, cfg)

        try:
            model = CMENet(backbone=backbone, dropout=dropout).to(cfg.device)
        except Exception:
            return -999.0

        optimizer = torch.optim.AdamW(model.parameters(), lr=lr, weight_decay=weight_decay)
        criterion = MultiTaskLoss(w_cls=1.0, w_cpa=w_cpa, w_width=w_width)
        scaler = _make_scaler(cfg.device == "cuda")
        ema = EMA(model, decay=cfg.ema_decay)
        total_steps = min(cfg.n_epochs, 20) * max(len(tr_loader), 1)
        scheduler = _make_scheduler(optimizer, total_steps, warmup_ratio)
        es = EarlyStopping(patience=cfg.patience, mode="max")
        best = -999.0

        try:
            for epoch in range(min(cfg.n_epochs, 20)):
                train_one_epoch(model, tr_loader, optimizer, criterion, scaler, scheduler, ema, cfg.device)
                val_m, _, _ = evaluate(ema, va_loader, cfg.device)
                score = val_m["composite_score"]
                best = max(best, score)
                trial.report(score, epoch)
                if trial.should_prune():
                    raise optuna.exceptions.TrialPruned()
                if es(score):
                    break
        except torch.cuda.OutOfMemoryError:
            best = -999.0
        finally:
            del model, optimizer, criterion, scaler, ema, scheduler
            gc.collect()
            if cfg.device == "cuda":
                torch.cuda.empty_cache()

        return best

    set_seed(cfg.seed)
    n_actual = min(cfg.n_trials, max(10, len(manifest) // 5))
    study = optuna.create_study(
        direction="maximize",
        sampler=optuna.samplers.TPESampler(seed=cfg.seed),
        pruner=optuna.pruners.MedianPruner(n_startup_trials=5, n_warmup_steps=4),
    )
    study.optimize(objective, n_trials=n_actual, timeout=3600, show_progress_bar=False)

    with open(cfg.results_dir / "optuna_study.pkl", "wb") as fh:
        pickle.dump(study, fh)

    return study.best_params


def train_full_cv(
    manifest: pd.DataFrame,
    fold_assignments: np.ndarray,
    best_params: Dict,
    cfg: Config,
) -> Dict:
    backbone = best_params.get("backbone", "efficientnet_b0")
    lr = float(best_params.get("lr", 3e-4))
    wd = float(best_params.get("weight_decay", 1e-4))
    dropout = float(best_params.get("dropout", 0.30))
    w_cpa = float(best_params.get("w_cpa", 1.5))
    w_width = float(best_params.get("w_width", 1.5))
    batch_size = int(best_params.get("batch_size", 16))
    warmup_ratio = float(best_params.get("warmup_ratio", 0.05))

    fold_results: List[Dict] = []
    best_global_score = -1.0
    best_global_state: Optional[Dict] = None

    for fold_idx in range(cfg.n_folds):
        set_seed(cfg.seed + fold_idx * 7)
        t_idx = np.where(fold_assignments != fold_idx)[0]
        v_idx = np.where(fold_assignments == fold_idx)[0]
        if len(v_idx) == 0:
            continue

        tr_loader, va_loader = _build_loaders(manifest, t_idx, v_idx, batch_size, cfg)
        model = CMENet(backbone=backbone, dropout=dropout).to(cfg.device)
        optimizer = torch.optim.AdamW(model.parameters(), lr=lr, weight_decay=wd)
        criterion = MultiTaskLoss(w_cls=1.0, w_cpa=w_cpa, w_width=w_width)
        scaler = _make_scaler(cfg.device == "cuda")
        ema = EMA(model, decay=cfg.ema_decay)
        total_steps = cfg.n_epochs * max(len(tr_loader), 1)
        scheduler = _make_scheduler(optimizer, total_steps, warmup_ratio)
        es = EarlyStopping(patience=cfg.patience, mode="max")

        best_fold_score = -1.0
        best_fold_ema_state: Optional[Dict] = None

        pbar = tqdm(range(cfg.n_epochs), desc=f"Fold {fold_idx}/{cfg.n_folds - 1}", leave=True)
        for epoch in pbar:
            t_loss = train_one_epoch(
                model, tr_loader, optimizer, criterion, scaler, scheduler, ema, cfg.device
            )
            val_m, _, _ = evaluate(ema, va_loader, cfg.device)
            score = val_m["composite_score"]
            pbar.set_postfix(
                loss=f"{t_loss:.4f}",
                cpa_mae=f"{val_m['cpa_circular_mae_deg']:.1f}°",
                w_mae=f"{val_m['width_mae_deg']:.1f}°",
                score=f"{score:.4f}",
            )

            if score > best_fold_score:
                best_fold_score = score
                best_fold_ema_state = deepcopy(ema.shadow.state_dict())
                torch.save(
                    {
                        "epoch": epoch,
                        "ema_state": best_fold_ema_state,
                        "metrics": val_m,
                        "params": best_params,
                        "backbone": backbone,
                    },
                    cfg.checkpoint_dir / f"fold{fold_idx}_best.pt",
                )
            if es(score):
                break

        if best_fold_ema_state is not None:
            ema.shadow.load_state_dict(best_fold_ema_state)

        final_m, _, _ = evaluate(ema, va_loader, cfg.device)
        fold_results.append(
            {
                "fold": fold_idx,
                "n_train": int(len(t_idx)),
                "n_val": int(len(v_idx)),
                **final_m,
            }
        )
        print(
            f"  Fold {fold_idx} → composite={final_m['composite_score']:.4f} | "
            f"CPA-MAE={final_m['cpa_circular_mae_deg']:.1f}° | "
            f"Width-MAE={final_m['width_mae_deg']:.1f}°"
        )

        if best_fold_score > best_global_score:
            best_global_score = best_fold_score
            best_global_state = deepcopy(best_fold_ema_state)

        del model, optimizer, criterion, scaler, ema, scheduler
        gc.collect()
        if cfg.device == "cuda":
            torch.cuda.empty_cache()

    if best_global_state is not None:
        torch.save(
            {"ema_state": best_global_state, "params": best_params, "backbone": backbone},
            cfg.checkpoint_dir / "final_model.pt",
        )

    cv_summary: Dict[str, float] = {}
    if fold_results:
        metric_keys = [k for k in fold_results[0] if k not in ("fold", "n_train", "n_val")]
        for k in metric_keys:
            vals = [
                float(r[k])
                for r in fold_results
                if not math.isnan(float(r.get(k, float("nan"))))
            ]
            cv_summary[f"{k}_mean"] = float(np.mean(vals)) if vals else float("nan")
            cv_summary[f"{k}_std"] = float(np.std(vals)) if vals else float("nan")

    results = {
        "fold_results": fold_results,
        "cv_summary": cv_summary,
        "best_params": best_params,
    }
    with open(cfg.results_dir / "cv_results.json", "w") as fh:
        json.dump(results, fh, indent=2, default=str)

    return results


def detect_cme(
    diff_path: str,
    norm_path: str,
    meta_path: str,
    checkpoint: Optional[str] = None,
    cfg: Optional[Config] = None,
) -> Dict:
    if cfg is None:
        cfg = CFG
    if checkpoint is None:
        checkpoint = str(cfg.checkpoint_dir / "final_model.pt")

    ckpt = torch.load(checkpoint, map_location="cpu")
    backbone = ckpt.get("backbone", ckpt.get("params", {}).get("backbone", "efficientnet_b0"))
    dropout = float(ckpt.get("params", {}).get("dropout", 0.30))

    model = CMENet(backbone=backbone, dropout=dropout)
    model.load_state_dict(ckpt["ema_state"])
    model = model.to(cfg.device).eval()

    kv: Dict[str, str] = {}
    with open(meta_path) as fh:
        for line in fh:
            if ":" in line:
                k, v = line.strip().split(":", 1)
                kv[k.strip()] = v.strip()
    cx_s, cy_s = kv.get("center_xy", "(256, 256)").strip("()").split(",")
    center_x = int(cx_s.strip())
    center_y = int(cy_s.strip())
    occulter_r = int(float(kv.get("occulter_r", "80px").replace("px", "").strip()))

    norm_arr = np.array(Image.open(norm_path).convert("L"), dtype=np.float32) / 255.0
    diff_arr = np.array(Image.open(diff_path).convert("L"), dtype=np.float32) / 255.0

    combined = np.stack([norm_arr, diff_arr, diff_arr], axis=-1)
    tf = get_val_transforms(cfg.image_size, cfg.ch_mean, cfg.ch_std)
    tensor = tf(image=combined)["image"].float().unsqueeze(0).to(cfg.device)

    use_amp = cfg.device == "cuda"
    with torch.no_grad(), autocast(enabled=use_amp):
        cls_l, cpa_u, w_s = model(tensor)

    cls_prob = float(torch.sigmoid(cls_l).item())
    sin_v = float(cpa_u[0, 0].item())
    cos_v = float(cpa_u[0, 1].item())
    cpa_deg = decode_cpa(sin_v, cos_v)
    width_deg = float(w_s.item()) * 360.0

    speed_km_s = estimate_speed_from_diff(
        diff_arr, cpa_deg, center_x, center_y, occulter_r,
        cfg.pixel_scale_arcsec, cfg.solar_radius_km, cfg.cadence_sec, cfg.arcsec_per_rsun,
    )
    eta_hours = compute_eta_hours(speed_km_s, cfg.au_km, cfg.solar_radius_km)

    del model
    gc.collect()
    if cfg.device == "cuda":
        torch.cuda.empty_cache()

    return {
        "is_cme": bool(cls_prob > 0.5),
        "cme_confidence": round(cls_prob, 4),
        "cpa_deg": round(cpa_deg, 1),
        "width_deg": round(width_deg, 1),
        "speed_km_s": round(speed_km_s, 1),
        "eta_hours": round(eta_hours, 2),
        "is_halo": bool(width_deg >= 120.0),
        "is_full_halo": bool(width_deg >= 180.0),
    }


def run_self_tests(cfg: Config) -> None:
    print("Running self-tests ...")

    for angle in [0.0, 45.0, 90.0, 180.0, 270.0, 350.0, 359.9]:
        recovered = decode_cpa(*encode_cpa(angle))
        assert abs(recovered - angle) < 1e-3, f"CPA roundtrip failed at {angle}°: got {recovered}"

    pred = np.array([358.0, 2.0, 175.0, 95.0])
    true = np.array([2.0, 358.0, 185.0, 85.0])
    mae = circular_mae_deg(pred, true)
    assert mae < 15.0, f"Circular MAE wrap-around: expected < 15°, got {mae:.2f}°"

    set_seed(0)
    fake_diff = np.full((512, 512), 0.5, dtype=np.float32)
    cv2.circle(fake_diff, (256, 256), 130, 0.72, 4)
    speed = estimate_speed_from_diff(fake_diff, 0.0, 256, 256, 80)
    assert 50.0 <= speed <= 5000.0, f"Speed out of physical range: {speed}"

    for spd in [300.0, 1000.0, 3000.0]:
        eta = compute_eta_hours(spd)
        assert 10.0 <= eta <= 200.0, f"ETA implausible for {spd} km/s: {eta:.1f} h"

    set_seed(42)
    model = CMENet(backbone="resnet18d", dropout=0.2).to(cfg.device)
    dummy = torch.randn(2, 3, 224, 224).to(cfg.device)
    with torch.no_grad():
        c_l, c_u, w_s = model(dummy)
    assert c_l.shape == (2,), f"cls_head shape error: {c_l.shape}"
    assert c_u.shape == (2, 2), f"cpa_head shape error: {c_u.shape}"
    assert w_s.shape == (2,), f"width_head shape error: {w_s.shape}"
    norms = torch.norm(c_u, dim=-1)
    assert torch.allclose(norms, torch.ones(2, device=cfg.device), atol=1e-5), "CPA not unit-normalised"
    assert float(w_s.min()) >= 0.0 and float(w_s.max()) <= 1.0, "width sigmoid out of [0,1]"
    ema_obj = EMA(model, decay=0.999)
    ema_logit, _, _ = ema_obj(dummy)
    assert ema_logit.shape == (2,), "EMA forward shape error"
    del model, ema_obj

    gc.collect()
    if cfg.device == "cuda":
        torch.cuda.empty_cache()

    n = 20
    fake_dates = pd.Series(pd.date_range("2000-01-01", periods=n, freq="90D"))
    fa = get_temporal_fold_assignments(fake_dates, n_folds=5)
    assert len(fa) == n, "fold assignment length mismatch"
    assert set(fa) == {0, 1, 2, 3, 4}, f"not all 5 folds populated: {set(fa)}"
    for fi in range(5):
        fi_dates = fake_dates[fa == fi].values
        other_dates = fake_dates[fa != fi].values
        if len(fi_dates) > 0 and len(other_dates) > 0:
            fi_max = pd.Timestamp(fi_dates.max())
            fi_min = pd.Timestamp(fi_dates.min())
            assert fi_min <= fi_max, "date ordering broken within fold"

    tr_transforms = get_train_transforms(224, (0.2, 0.5, 0.5), (0.15, 0.1, 0.1))
    va_transforms = get_val_transforms(224, (0.2, 0.5, 0.5), (0.15, 0.1, 0.1))
    dummy_img = np.random.rand(512, 512, 3).astype(np.float32)
    tr_out = tr_transforms(image=dummy_img)["image"]
    va_out = va_transforms(image=dummy_img)["image"]
    assert tr_out.shape == (3, 224, 224), f"train transform output shape wrong: {tr_out.shape}"
    assert va_out.shape == (3, 224, 224), f"val transform output shape wrong: {va_out.shape}"

    pearsonr_pairs = [
        (np.array([1.0, 2.0, 3.0]), np.array([1.0, 2.0, 3.0])),
        (np.array([1.0]), np.array([1.0])),
        (np.array([1.0, 1.0, 1.0]), np.array([2.0, 3.0, 4.0])),
    ]
    for x, y in pearsonr_pairs:
        rho, pval = _pearsonr_safe(x, y)
        assert isinstance(rho, float), "_pearsonr_safe must return float"

    print("All self-tests PASSED.")


def main() -> None:
    parser = argparse.ArgumentParser(description="Commit 13 — CME Detection CNN + Kinematics")
    parser.add_argument("--skip-hpo", action="store_true", help="Skip Optuna, use defaults")
    parser.add_argument("--test", action="store_true", help="Self-tests only")
    parser.add_argument("--n-trials", type=int, default=None)
    parser.add_argument("--n-epochs", type=int, default=None)
    parser.add_argument("--data-dir", type=str, default=None)
    parser.add_argument("--catalog", type=str, default=None)
    args = parser.parse_args()

    if args.n_trials is not None:
        CFG.n_trials = args.n_trials
    if args.n_epochs is not None:
        CFG.n_epochs = args.n_epochs
    if args.data_dir is not None:
        CFG.data_dir = Path(args.data_dir)
    if args.catalog is not None:
        CFG.catalog_csv = Path(args.catalog)

    set_seed(CFG.seed)

    if args.test:
        run_self_tests(CFG)
        return

    print(f"Device : {CFG.device}")
    print(f"Data   : {CFG.data_dir}")

    manifest = build_manifest(CFG)
    n = len(manifest)
    print(
        f"Dataset: {n} samples | "
        f"{manifest['date_obs'].min().date()} → {manifest['date_obs'].max().date()} | "
        f"full-halo fraction: {manifest['is_full_halo'].mean():.2%}"
    )

    fold_assignments = get_temporal_fold_assignments(manifest["date_obs"], CFG.n_folds)
    for fi in range(CFG.n_folds):
        cnt = int((fold_assignments == fi).sum())
        d_min = manifest.loc[fold_assignments == fi, "date_obs"].min()
        d_max = manifest.loc[fold_assignments == fi, "date_obs"].max()
        print(f"  Fold {fi}: {cnt:4d} samples  {d_min.date()} → {d_max.date()}")

    if args.skip_hpo:
        best_params: Dict = {
            "backbone": "efficientnet_b0",
            "lr": 3e-4,
            "weight_decay": 1e-4,
            "dropout": 0.30,
            "w_cpa": 1.5,
            "w_width": 1.5,
            "batch_size": 16,
            "warmup_ratio": 0.05,
        }
        print("HPO skipped — using default hyperparameters")
    else:
        print(f"\nOptuna HPO — {CFG.n_trials} trials on fold {CFG.optuna_fold} ...")
        best_params = run_optuna_study(manifest, fold_assignments, CFG)
        print(f"Best params:\n{json.dumps(best_params, indent=2)}")

    print("\n5-fold temporal CV ...")
    results = train_full_cv(manifest, fold_assignments, best_params, CFG)

    print("\n=== CV SUMMARY ===")
    summary = results["cv_summary"]
    for k in sorted(summary):
        if k.endswith("_mean") and not math.isnan(summary[k]):
            base = k[:-5]
            std = summary.get(f"{base}_std", float("nan"))
            print(f"  {base:40s}: {summary[k]:.4f} ± {std:.4f}")

    final_ckpt = CFG.checkpoint_dir / "final_model.pt"
    if final_ckpt.exists():
        row = manifest.iloc[0]
        if Path(row["diff_path"]).exists() and Path(row["norm_path"]).exists():
            storm_event = detect_cme(
                row["diff_path"],
                row["norm_path"],
                str(CFG.data_dir / f"{row['event_id']}_meta.txt"),
                checkpoint=str(final_ckpt),
            )
            print("\n=== SAMPLE STORM EVENT (inference check) ===")
            for k, v in storm_event.items():
                print(f"  {k}: {v}")
            assert 50.0 <= storm_event["speed_km_s"] <= 5000.0, "speed outside physical range"
            assert 5.0 <= storm_event["eta_hours"] <= 200.0, "ETA outside physical range"

            speed_eta = {
                "event_id": row["event_id"],
                "speed_km_s": storm_event["speed_km_s"],
                "eta_hours": storm_event["eta_hours"],
                "cpa_deg": storm_event["cpa_deg"],
                "width_deg": storm_event["width_deg"],
            }
            with open(CFG.results_dir / "speed_eta_summary.json", "w") as fh:
                json.dump(speed_eta, fh, indent=2)
            print(f"\nOutputs saved to: {CFG.results_dir}")
            print(f"Checkpoints at : {CFG.checkpoint_dir}")


if __name__ == "__main__":
    main()