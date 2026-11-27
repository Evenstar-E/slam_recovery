"""Validate the stored paired calibration used in each successful staged experiment."""
import hashlib
import json
from pathlib import Path
import re

root = Path.home() / "vio_matrix_evidence_20261127"
output = {}
for seq in ("exp01","exp04","exp05","exp16","exp18"):
    if not (root/seq/"cleanup.json").is_file():
        continue
    for host in ("orb","okvis","vins"):
        dataset = "exp18-nodrain" if host=="orb" and seq=="exp18" else seq
        suffix = "-startup-fixed" if seq=="exp18" and host=="vins" else ""
        configs = [root/dataset/"results"/f"{dataset}-{host}-{mode}{suffix}"/"config"
                   for mode in ("native","recover")]
        use = ("orb-rectified.yaml",)
        if host=="okvis":
            use += ("okvis.yaml",)
        elif host=="vins":
            use += ("cam0.yaml","cam1.yaml","primary.yaml")
        sources = {}
        ignored = []
        for name in use:
            first, second = (p.joinpath(name).read_bytes() for p in configs)
            if name=="primary.yaml":
                first, second = (re.sub(rb"^(output_path|pose_graph_save_path):[^\n]*",rb"\1: DIR",text,flags=re.M)
                                 for text in (first,second))
            if name=="orb-rectified.yaml" and host!="orb" and first!=second:
                # HeldOutStereo loads only numeric calibration fields and the two matrices.
                ignored.append("unused Camera.type label")
                first, second = (re.sub(rb"^Camera.type:[^\n]*", b"Camera.type: UNUSED", text, flags=re.M)
                                 for text in (first,second))
            assert first==second, (seq,host,name)
            sources[name]=hashlib.sha256(first).hexdigest()
        output[f"{seq}-{host}"]={"hashes":sources, "ignored_in_gate_calibration":ignored}
(root/"PAIR_CONFIG_CHECK.json").write_text(json.dumps(output, indent=2))
print("matched configurations", len(output))
