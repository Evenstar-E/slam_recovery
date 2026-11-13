#!/usr/bin/env python3
"""Write one native-recovery command and wait for the host's ack."""
import os, sys, time
d = sys.argv[1]; cmd = sys.argv[2]; payload = sys.argv[3] if len(sys.argv) > 3 else ""
ack = os.path.join(d, "ack")
for p in (ack, os.path.join(d, "cmd.done")):
    try: os.remove(p)
    except OSError: pass
tmp = os.path.join(d, "cmd.tmp")
with open(tmp, "w") as f:
    f.write(cmd + "\n" + payload + "\n")
os.rename(tmp, os.path.join(d, "cmd"))
t0 = time.time()
while time.time() - t0 < 20.0:
    if os.path.exists(ack):
        time.sleep(0.05)
        print(open(ack).read().strip()); sys.exit(0)
    time.sleep(0.02)
print("TIMEOUT waiting for ack of", cmd); sys.exit(1)
