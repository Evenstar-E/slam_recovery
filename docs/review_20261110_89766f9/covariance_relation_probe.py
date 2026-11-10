"""Review arithmetic only: projected information is not inverse directional variance."""
import json
import numpy as np

information = np.eye(6) * 4.0
information[0, 1] = information[1, 0] = 3.9
v = np.eye(6)[0]
covariance = np.linalg.inv(information + .001 * np.eye(6))
q = float(v @ information @ v)
variance = float(v @ covariance @ v)
norm = float(np.linalg.norm(covariance, 2))
assert q >= 2.0 and variance > .5 and norm > .5
print(json.dumps({
    "scope": "SPD arithmetic control; no SLAM experiment or threshold changes",
    "direction_information": q,
    "reciprocal_direction_information": 1.0 / q,
    "actual_direction_variance": variance,
    "covariance_spectral_norm": norm,
    "floor_2_pass": q >= 2.0,
    "existing_covariance_0_5_pass": norm <= .5,
}, indent=2))
