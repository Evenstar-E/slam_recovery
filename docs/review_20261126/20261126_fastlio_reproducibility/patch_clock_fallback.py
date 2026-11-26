"""Restrict experimental odometry publication to an explicitly latched clock hold."""
from pathlib import Path
import sys


path = Path(sys.argv[1])
source = path.read_text()


def replace(old, new):
    global source
    assert source.count(old) == 1, old
    source = source.replace(old, new)


replace("static bool lab_clock_readonly_preview = false;",
        "static bool lab_clock_readonly_preview = false;\nstatic bool lab_clock_preview_latched = false;")
replace('            nr_write_ack(std::string("OK preview_map valid=") + (ok ? "1" : "0"));',
        '''            if (ok) lab_clock_preview_latched = payload == "begin";
            nr_write_ack(std::string("OK preview_map valid=") + (ok ? "1" : "0"));''')
replace("if (!(lab_clock_readonly_preview && g_nr_hold.load())) lasermap_fov_segment();",
        "if (!(lab_clock_preview_latched && g_nr_hold.load())) lasermap_fov_segment();")
replace("const bool preview_pose = lab_clock_readonly_preview && g_nr_hold.load() &&",
        "const bool preview_pose = lab_clock_preview_latched && g_nr_hold.load() &&")
path.write_text(source)
