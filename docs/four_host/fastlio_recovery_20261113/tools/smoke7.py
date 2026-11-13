#!/usr/bin/env python3
"""Seven-step interface smoke for the FAST-LIO native recovery host, verbatim acks.

  1 status            2 capabilities (+ semantics block present)
  3 hold              4 snapshot        5 restore
  6 relay + reprocess                    7 resume
Each ack is appended to <ctl>/../smoke7.jsonl exactly as the host wrote it. Run it against a
host-only session: interleaving it with the driver's own command stream would make one `ack`
file serve two writers and the receipts could be misattributed.
"""
import json, os, sys, time

def cmd(ctl, name, payload=""):
    ack = os.path.join(ctl, "ack")
    for p in (ack, os.path.join(ctl, "cmd.done")):
        try: os.remove(p)
        except OSError: pass
    tmp = os.path.join(ctl, "cmd.tmp")
    with open(tmp, "w") as f:
        f.write(name + "\n" + payload + "\n")
    os.rename(tmp, os.path.join(ctl, "cmd"))
    t0 = time.time()
    while time.time() - t0 < 30.0:
        if os.path.exists(ack):
            time.sleep(0.05)
            return open(ack).read().strip()
        time.sleep(0.02)
    return "TIMEOUT"

def main():
    ctl = sys.argv[1]
    log_path = sys.argv[2] if len(sys.argv) > 2 else os.path.join(os.path.dirname(ctl.rstrip("/")), "smoke7.jsonl")
    steps = [("status", ""), ("capabilities", ""), ("hold", ""), ("snapshot", "")]
    out = []
    for name, payload in steps:
        a = cmd(ctl, name, payload)
        out.append({"step": name, "ack": a})
        print(f"[{name}] {a}")
    # relay + reprocess: the repair cloud is published by the caller (a feeder on the topic).
    a = cmd(ctl, "restore", "")
    out.append({"step": "restore", "ack": a}); print("[restore]", a)
    a = cmd(ctl, "reprocess", "")
    out.append({"step": "reprocess", "ack": a}); print("[reprocess]", a)
    a = cmd(ctl, "resume", "")
    out.append({"step": "resume", "ack": a}); print("[resume]", a)
    with open(log_path, "w") as f:
        for row in out:
            f.write(json.dumps(row) + "\n")
    caps = os.path.join(ctl, "capabilities.json")
    ok = False
    if os.path.exists(caps):
        try:
            ok = "semantics" in json.load(open(caps))
        except Exception:
            ok = False
    print("semantics_present:", ok)

if __name__ == "__main__":
    main()
