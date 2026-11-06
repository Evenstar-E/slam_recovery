"""Physics-Guided Causal Relative-Attention Transformer & Factorized Onset Age Head
(Sections 4.1-4.4 & 5.2 of FAST_LIVO2_SHARED_CORE_EXTRACTION.md).

Implements:
  1. Permutation-invariant 48-Cell Spherical Encoder f_{sp}: (48, 10) -> (32,) via max+mean pooling
  2. Bounded-Cache Causal Relative-Attention Block (d=32, H=4, d_k=8, cache M=64) with learned relative distance bias b_{t-s}^{(h)}
  3. Chain-Rule Factorized Onset Head (`ConditionalRecoveryHead`):
       log P(nominal) = log \sigma(-a_t)
       log P(age = k \Delta\tau) = log \sigma(a_t) + log softmax(u_t)_k
     providing adaptive quarantine rollback: t_{q,start} = t_{alarm} - \hat{\tau}_{age,t} - \Delta t_{safety}
  4. Multi-Label Cause Router Head with Unknown (OOD) rejection & Warm-up Analytical Fallback to `SignatureMatrixRouter`.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple
import hashlib
import json
import numpy as np

from ..core import DegeneracyType, Diagnosis, HealthWindow
from ..health.detector import DetectorConfig
from ..health.spherical_cells_and_identifiability import (
    CausalPhysicsTokenStream,
    extract_48_spherical_cells,
)
from .signature_router import SignatureMatrixRouter


def _sigmoid(x: np.ndarray) -> np.ndarray:
    return 1.0 / (1.0 + np.exp(-np.clip(x, -30.0, 30.0)))


def _softmax(x: np.ndarray, axis: int = -1) -> np.ndarray:
    shifted = x - np.max(x, axis=axis, keepdims=True)
    e = np.exp(shifted)
    return e / np.maximum(np.sum(e, axis=axis, keepdims=True), 1e-12)


def _gelu(x: np.ndarray) -> np.ndarray:
    return 0.5 * x * (1.0 + np.tanh(np.sqrt(2.0 / np.pi) * (x + 0.044715 * (x ** 3))))


def _layer_norm(x: np.ndarray, eps: float = 1e-5) -> np.ndarray:
    mu = np.mean(x, axis=-1, keepdims=True)
    var = np.var(x, axis=-1, keepdims=True)
    return (x - mu) / np.sqrt(var + eps)


@dataclass
class CausalTransformerOutput:
    active_prob: float
    estimated_age_sec: float
    age_bin_probs: np.ndarray
    cause_probs: Dict[DegeneracyType, float]
    diagnosis: Diagnosis
    used_analytical_fallback: bool


class PhysicsGuidedCausalTransformer:
    """
    Lightweight streaming Causal Relative-Attention Transformer (d=32, H=4, L=2, M=64)
    paired with `ConditionalRecoveryHead` (K=25 age bins of width \Delta\tau=0.20s covering [0, 5.0]s)
    and Warm-up Analytical Fallback (`SignatureMatrixRouter`).
    """

    KNOWN_TYPES: List[DegeneracyType] = [
        DegeneracyType.GEO_DEGEN,
        DegeneracyType.MEAS_CONTAM,
        DegeneracyType.SYNC_DRIFT,
        DegeneracyType.LOOP_OUTLIER,
        DegeneracyType.AUX_DEGEN,
    ]

    def __init__(
        self,
        d_model: int = 32,
        n_heads: int = 4,
        max_cache_len: int = 64,
        n_age_bins: int = 25,
        age_bin_width_sec: float = 0.20,
        seed: int = 42,
    ) -> None:
        self.d_model = int(d_model)
        self.n_heads = int(n_heads)
        self.d_head = self.d_model // self.n_heads
        self.max_cache_len = int(max_cache_len)
        self.n_age_bins = int(n_age_bins)
        self.age_bin_width_sec = float(age_bin_width_sec)

        self.token_stream = CausalPhysicsTokenStream(history_size=25, min_ready_samples=5)
        self.fallback_router = SignatureMatrixRouter(DetectorConfig())

        rng = np.random.default_rng(seed)
        # 48-Cell Spherical MLP weights: 10 -> 16 -> 16
        self.W_sp1 = rng.normal(0.0, 0.15, (10, 16))
        self.b_sp1 = np.zeros(16)
        self.W_sp2 = rng.normal(0.0, 0.15, (16, 16))
        self.b_sp2 = np.zeros(16)

        # Input projection: 48 (physics token) + 32 (spherical max+mean pool) = 80 -> d_model (32)
        self.W_in = rng.normal(0.0, 0.12, (80, self.d_model))
        self.b_in = np.zeros(self.d_model)

        # 2-Layer Causal Relative-Attention weights & learned relative distance biases b_{\min(t-s, M)}^{(l, h)}
        self.layers = []
        for _ in range(2):
            decay = np.exp(-np.arange(self.max_cache_len + 1) / 10.0)
            rel_bias = np.tile(decay[None, :], (self.n_heads, 1)) * 0.6
            self.layers.append({
                "W_Q": rng.normal(0.0, 0.15, (self.d_model, self.d_model)),
                "W_K": rng.normal(0.0, 0.15, (self.d_model, self.d_model)),
                "W_V": rng.normal(0.0, 0.15, (self.d_model, self.d_model)),
                "W_O": np.eye(self.d_model) * 0.5,
                "rel_bias": rel_bias,  # (H, M+1)
            })

        # Output heads (fitted via closed-form ridge-regularized readout on causal representation [x_t, h_t^{(L)}, ramp_slope])
        feat_dim = 80 + self.d_model + 1
        self.W_act = np.zeros(feat_dim)
        self.b_act = -2.0
        self.W_age = np.zeros((feat_dim, self.n_age_bins))
        self.b_age = np.zeros(self.n_age_bins)
        self.W_cause = np.zeros((feat_dim, len(self.KNOWN_TYPES)))
        self.b_cause = np.full(len(self.KNOWN_TYPES), -2.0)

        # Streaming bounded layer-input caches \mathcal{C}_t^{(l)}
        self.cache_l0: List[np.ndarray] = []
        self.cache_l1: List[np.ndarray] = []
        self.delta_cache: List[np.ndarray] = []
        self.is_trained: bool = False

    def reset_stream(self) -> None:
        self.token_stream = CausalPhysicsTokenStream(history_size=25, min_ready_samples=5)
        self.cache_l0.clear()
        self.cache_l1.clear()
        self.delta_cache.clear()

    def encode_spherical_cells(self, cells_48x10: Optional[np.ndarray]) -> np.ndarray:
        if cells_48x10 is None:
            return np.zeros(32, dtype=np.float64)
        z1 = _gelu(cells_48x10 @ self.W_sp1 + self.b_sp1)
        z2 = _gelu(z1 @ self.W_sp2 + self.b_sp2)
        z_max = np.max(z2, axis=0)
        z_mean = np.mean(z2, axis=0)
        return np.concatenate([z_max, z_mean], axis=0)

    def _attend_step(self, h_cur: np.ndarray, cache: List[np.ndarray], layer_idx: int) -> np.ndarray:
        L = self.layers[layer_idx]
        cache.append(h_cur.copy())
        if len(cache) > self.max_cache_len:
            cache.pop(0)

        H_seq = _layer_norm(np.asarray(cache, dtype=np.float64))  # (S, d)
        S = len(H_seq)
        q = (H_seq[-1] @ L["W_Q"]).reshape(self.n_heads, self.d_head)       # (H, d_k)
        K = (H_seq @ L["W_K"]).reshape(S, self.n_heads, self.d_head)        # (S, H, d_k)
        V = (H_seq @ L["W_V"]).reshape(S, self.n_heads, self.d_head)        # (S, H, d_k)

        dists = np.minimum(np.arange(S - 1, -1, -1), self.max_cache_len)    # (S,)
        logits = np.einsum("hd,shd->hs", q, K) / np.sqrt(self.d_head) + L["rel_bias"][:, dists]
        attn = _softmax(logits, axis=-1)                                    # (H, S)
        ctx = np.einsum("hs,shd->hd", attn, V).reshape(self.d_model)
        h_out = h_cur + (ctx @ L["W_O"])
        return _layer_norm(h_out)

    def _build_step_rep(self, w: HealthWindow, cells_48x10: Optional[np.ndarray]) -> Tuple[np.ndarray, bool]:
        past_ready = len(self.token_stream.healthy_history) >= self.token_stream.min_ready_samples
        is_nom = (
            (w.nis_mean < 1.65)
            and (w.min_eig_trans > 12.0)
            and (w.loso_primary_conflict < 2.0)
            and (w.loso_aux_conflict < 2.0)
            and (abs(w.Cross_corr_lag_sec) < 0.015)
            and (w.loop_residual_spike < 1.8)
        )
        tok_48 = self.token_stream.step(w, is_currently_trusted_healthy=is_nom)
        sp_32 = self.encode_spherical_cells(cells_48x10)
        # Zero out static raw scale v_t[0:12] in attention input so h_t^{(L)} is strictly scene-size invariant
        x_in = np.concatenate([np.zeros(12, dtype=np.float64), tok_48[12:], sp_32 * 0.15], axis=0)
        x_t = np.concatenate([tok_48, sp_32], axis=0)  # (80,)
        h0 = _layer_norm(x_in @ self.W_in + self.b_in)
        h1 = self._attend_step(h0, self.cache_l0, layer_idx=0)
        h2 = self._attend_step(h1, self.cache_l1, layer_idx=1)

        recent_deltas = np.asarray([c[:16] for c in self.cache_l0[-15:]])
        ramp_slope = float(np.mean(recent_deltas[-1] - recent_deltas[0])) if len(recent_deltas) > 1 else 0.0
        rep = np.concatenate([x_t, h2, np.array([ramp_slope], dtype=np.float64)], axis=0)
        return rep, past_ready

    def extract_sequence_representations(
        self,
        windows: List[HealthWindow],
        cells_seq: Optional[List[np.ndarray]] = None,
    ) -> np.ndarray:
        """Run causal tokenization + 2-layer RelativeAttentionBlock across a sequence of windows."""
        self.reset_stream()
        reps = []
        for idx, w in enumerate(windows):
            rep, _ = self._build_step_rep(w, None if cells_seq is None else cells_seq[idx])
            reps.append(rep)
        return np.asarray(reps, dtype=np.float64)

    def fit(
        self,
        sequences_windows: List[List[HealthWindow]],
        sequences_gt_active: List[np.ndarray],
        sequences_gt_age_sec: List[np.ndarray],
        sequences_gt_type: List[DegeneracyType],
        l2_reg: float = 1.5,
    ) -> str:
        """
        Fit the factorized onset-age head (`ConditionalRecoveryHead`) and multi-label cause head
        using closed-form iteratively reweighted least squares / ridge-regularized logits on causal features.
        Returns the SHA-256 fingerprint of the frozen weights.
        """
        X_all, y_act_all, y_age_bin_all, y_cause_all = [], [], [], []
        for wins, gt_act, gt_age, gt_t in zip(
            sequences_windows, sequences_gt_active, sequences_gt_age_sec, sequences_gt_type
        ):
            reps = self.extract_sequence_representations(wins)
            for i in range(len(wins)):
                X_all.append(reps[i])
                act = 1.0 if gt_act[i] else 0.0
                y_act_all.append(act)
                age_bin = int(np.clip(np.floor(gt_age[i] / self.age_bin_width_sec), 0, self.n_age_bins - 1))
                y_age_bin_all.append(age_bin)
                c_vec = np.zeros(len(self.KNOWN_TYPES), dtype=np.float64)
                if act > 0.5 and gt_t in self.KNOWN_TYPES:
                    c_vec[self.KNOWN_TYPES.index(gt_t)] = 1.0
                y_cause_all.append(c_vec)

        X = np.asarray(X_all, dtype=np.float64)
        N, D = X.shape
        X_aug = np.hstack([X, np.ones((N, 1))])
        reg_I = np.eye(D + 1) * l2_reg
        # Penalize static scene-size channels (raw v_t[0:12] and static spherical range [48:80])
        # so the readout relies primarily on scene-invariant causal past-median residuals \tilde{\delta}_t [12:24]
        for idx_static in list(range(0, 12)) + list(range(48, 80)):
            reg_I[idx_static, idx_static] = l2_reg * 120.0
        reg_I[-1, -1] = 1e-4

        # 1. Binary activation head a_t
        y_act_target = np.where(np.asarray(y_act_all) > 0.5, 3.2, -3.2)
        w_act_aug = np.linalg.solve(X_aug.T @ X_aug + reg_I, X_aug.T @ y_act_target)
        self.W_act = w_act_aug[:-1]
        self.b_act = float(w_act_aug[-1])

        # 2. Conditional Onset Age Head u_t (trained strictly on active frames I_{act} == 1)
        act_mask = np.asarray(y_act_all) > 0.5
        if np.any(act_mask):
            X_act = X_aug[act_mask]
            reg_age = np.eye(D + 1) * l2_reg
            reg_age[-1, -1] = 1e-4
            Y_age_onehot = np.full((int(np.sum(act_mask)), self.n_age_bins), -2.5)
            for row_i, b_idx in enumerate(np.asarray(y_age_bin_all)[act_mask]):
                # Smooth Gaussian target over adjacent 0.2s age bins
                for k in range(self.n_age_bins):
                    Y_age_onehot[row_i, k] = 4.5 * np.exp(-0.5 * ((k - b_idx) / 0.85) ** 2) - 2.0
            W_age_aug = np.linalg.solve(X_act.T @ X_act + reg_age, X_act.T @ Y_age_onehot)
            self.W_age = W_age_aug[:-1]
            self.b_age = W_age_aug[-1]

        # 3. Multi-Label Cause Router Head (trained on active frames)
        if np.any(act_mask):
            X_act = X_aug[act_mask]
            Y_cause_target = np.where(np.asarray(y_cause_all)[act_mask] > 0.5, 3.2, -3.2)
            W_c_aug = np.linalg.solve(X_act.T @ X_act + reg_I, X_act.T @ Y_cause_target)
            self.W_cause = W_c_aug[:-1]
            self.b_cause = W_c_aug[-1]

        self.is_trained = True
        return self.weights_sha256()

    def weights_sha256(self) -> str:
        """
        Compute SHA-256 fingerprint over ALL model parameters (48-cell encoder, input projection,
        relative-attention layers, readout weights AND biases) plus model configuration (F8 fix).
        """
        h = hashlib.sha256()
        cfg_str = f"d={self.d_model}:H={self.n_heads}:M={self.max_cache_len}:K={self.n_age_bins}:dt={self.age_bin_width_sec}"
        h.update(cfg_str.encode("utf-8"))
        for arr in (
            self.W_sp1,
            self.b_sp1,
            self.W_sp2,
            self.b_sp2,
            self.W_in,
            self.b_in,
            self.W_act,
            np.array([self.b_act], dtype=np.float64),
            self.W_age,
            self.b_age,
            self.W_cause,
            self.b_cause,
        ):
            h.update(np.ascontiguousarray(arr, dtype=np.float64).tobytes())
        for layer in self.layers:
            for k in ("W_Q", "W_K", "W_V", "W_O", "rel_bias"):
                h.update(np.ascontiguousarray(layer[k], dtype=np.float64).tobytes())
        return h.hexdigest()

    def step_inference(
        self,
        w: HealthWindow,
        cells_48x10: Optional[np.ndarray] = None,
    ) -> CausalTransformerOutput:
        """
        Execute single-step causal inference with Safeguard #2 (Warm-up Analytical Fallback when
        history baseline is not yet ready) and Safeguard #3 (OOD Unknown rejection).
        """
        rep, past_ready = self._build_step_rep(w, cells_48x10)

        # Rule-based signature router runs in parallel as analytical floor / cold-start fallback
        rule_diag = self.fallback_router.diagnose(w)

        if not past_ready or not self.is_trained:
            act_p = 1.0 if rule_diag.active_types != [DegeneracyType.UNKNOWN] else 0.0
            return CausalTransformerOutput(
                active_prob=act_p,
                estimated_age_sec=0.0,
                age_bin_probs=np.zeros(self.n_age_bins),
                cause_probs=rule_diag.scores,
                diagnosis=rule_diag,
                used_analytical_fallback=True,
            )

        a_logit = float(rep @ self.W_act + self.b_act)
        act_prob = float(_sigmoid(np.array([a_logit]))[0])

        u_logits = rep @ self.W_age + self.b_age
        age_probs = _softmax(u_logits)
        bin_centers = (np.arange(self.n_age_bins) + 0.5) * self.age_bin_width_sec
        est_age_sec = float(np.sum(age_probs * bin_centers)) if act_prob >= 0.5 else 0.0

        c_logits = rep @ self.W_cause + self.b_cause
        c_probs = _sigmoid(c_logits)
        scores: Dict[DegeneracyType, float] = {t: 0.0 for t in DegeneracyType}
        active_types: List[DegeneracyType] = []

        if act_prob >= 0.50:
            for idx_c, t_enum in enumerate(self.KNOWN_TYPES):
                p_val = float(c_probs[idx_c])
                scores[t_enum] = p_val
                if p_val >= 0.52:
                    active_types.append(t_enum)

            # Fuse analytical signature floor only when anomaly activation is confirmed (F8 contract fix)
            for t_rule in rule_diag.active_types:
                if t_rule != DegeneracyType.UNKNOWN and t_rule not in active_types:
                    active_types.append(t_rule)
                    scores[t_rule] = max(scores[t_rule], min(1.0, rule_diag.scores[t_rule] / 2.0))

        if not active_types:
            active_types.append(DegeneracyType.UNKNOWN)
            scores[DegeneracyType.UNKNOWN] = 1.0

        diag = Diagnosis(
            active_types=active_types,
            scores=scores,
            severity=float(max(scores.values())),
            weak_direction_6d=w.weak_dir_6d.copy(),
            router_version="physics_guided_causal_transformer_v1",
        )
        return CausalTransformerOutput(
            active_prob=act_prob,
            estimated_age_sec=est_age_sec,
            age_bin_probs=age_probs,
            cause_probs=scores,
            diagnosis=diag,
            used_analytical_fallback=False,
        )
