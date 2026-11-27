import json
from pathlib import Path

root=Path.home()/"vio_matrix_evidence_20261127"
hosts=("orb","vins","okvis")
data={}
counts={"pairs":0,"decreased_verified":0,"increased_verified":0,"increased_public":0,
        "increased_1sec_verified":0,"decreased_1sec_verified":0,
        "early_plugin_stop":[], "rmse_improves":0,"rmse_measurable_pairs":0,
        "isolate_total":0,"promotions":0}
for seq in ("exp01","exp04","exp05","exp16","exp18"):
    source=root/seq/"receipts"/f"{seq}-score.json"
    if not source.is_file():
        continue
    sets=json.loads(source.read_text())
    if seq=="exp18":
        fair=root/"exp18-nodrain/receipts/exp18-nodrain-score.json"
        if fair.is_file():
            sets["orb"]=json.loads(fair.read_text())["orb"]
    seq_data={}
    for kind in hosts:
        pair=sets[kind]
        a,b=(pair["arms"][mode] for mode in ("native","recover"))
        sa,sb=(x["status"] for x in (a,b))
        counts["pairs"]+=1
        va,vb=sa["verified_pairs"],sb["verified_pairs"]
        counts["decreased_verified"]+=vb<va
        counts["increased_verified"]+=vb>va
        counts["increased_public"]+=sb["public_pairs"]>sa["public_pairs"]
        counts["increased_1sec_verified"]+=b["timely_verified_1sec"]>a["timely_verified_1sec"]
        counts["decreased_1sec_verified"]+=b["timely_verified_1sec"]<a["timely_verified_1sec"]
        counts["isolate_total"]+=b["lifecycle"]["isolate"]
        counts["promotions"]+=b["lifecycle"]["promote"]
        if not sb["scheduled_full"] or sb["controller_exit"]:
            counts["early_plugin_stop"].append({"sequence":seq,"host":kind,"exit":sb["controller_exit"],
                  "clocked":sb["clocked_pairs"],"expected":sb["requested_pairs"]})
        an,bn=(pair["common_accuracy"][mode] for mode in ("native","recover"))
        if "rmse_m" in an and "rmse_m" in bn:
            counts["rmse_measurable_pairs"]+=1
            counts["rmse_improves"]+=bn["rmse_m"]<an["rmse_m"]
        stage={"orb":"primary_tracking","vins":"host_ns","okvis":"submission_ns"}[kind]
        seq_data[kind]={"origin":[va,vb],"expected":sa["requested_pairs"],
                         "public":[sa["public_pairs"],sb["public_pairs"]],
                         "within_1sec_original":[a["timely_verified_1sec"],b["timely_verified_1sec"]],
                         "p95_external_ms":[x["latency_ms"].get("p95") for x in (a,b)],
                         "same_frame_primary_p50_effect_ms":pair["same_frame_delta_ms"].get(stage,{}).get("p50"),
                         "common_rmse_m":[an.get("rmse_m"),bn.get("rmse_m")],"common_count":an["matched"],
                         "exit":[sa["controller_exit"],sb["controller_exit"]],
                         "t_last_public_gap_s":[x["no_output"]["tail_sensor_s"] for x in (a,b)],
                         "cpu_s":[x["sampled_process_tree_cpu_s"] for x in (a,b)],
                         "rss_mib":[x["peak_sum_rss_mib"] for x in (a,b)]}
    data[seq]=seq_data
output={"counts":counts,"cases":data}
(root/"SUMMARY.json").write_text(json.dumps(output,indent=2))
print(json.dumps(counts))
for seq,group in data.items():
    print(seq,group["orb"]["expected"],[(kind,g["origin"],g["same_frame_primary_p50_effect_ms"],
                                         g["common_rmse_m"]) for kind,g in group.items()])
