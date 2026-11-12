import re, json, sys
log, times_path = sys.argv[1], "/tmp/orb_hall01/times.txt"
times = [int(x)/1e9 for x in open(times_path) if x.strip()]
t0 = times[0]
ids = []
for line in open(log, errors='replace'):
    m = re.match(r"mnFirstFrameId = (\d+)", line.strip())
    if m: ids.append(int(m.group(1)))
def t_of(fi):
    return round(times[fi-1]-t0, 2) if 1 <= fi <= len(times) else None
inits = [{"frame": f, "t_s": t_of(f)} for f in ids]
wins = {"pre_E1": (0,190), "E1": (190,220), "mid": (220,300), "E2": (300,330), "tail": (330,400)}
counts = {k: 0 for k in wins}
for e in inits:
    if e["t_s"] is None: continue
    for k,(a,b) in wins.items():
        if a <= e["t_s"] < b: counts[k]+=1
print(json.dumps({
 "n_map_initialisations": len(inits),
 "first_frame": ids[0] if ids else None,
 "last_frame": ids[-1] if ids else None,
 "last_t_s": t_of(ids[-1]) if ids else None,
 "seq_duration_s": round(times[-1]-t0,2),
 "init_counts_by_window": counts,
 "first_10": inits[:10], "last_5": inits[-5:],
}, indent=1))
