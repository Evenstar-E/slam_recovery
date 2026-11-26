"""Apply the experimental read-only clock lane to the pinned native host."""
from pathlib import Path
import sys


path = Path(sys.argv[1])
source = path.read_text()


def replace(old, new):
    global source
    assert source.count(old) == 1, old
    source = source.replace(old, new)


replace("static bool lab_dual = false;",
        "static bool lab_dual = false;\nstatic bool lab_clock_readonly_preview = false;")
replace('        else if (cmd == "restore")',
        '''        else if (cmd == "preview_map" && lab_clock_readonly_preview)
        {
            if (!g_nr_hold.load() || g_nr_replay_remaining ||
                (payload != "begin" && payload != "end") || !ikdtree.Root_Node)
            {
                nr_write_ack("OK preview_map valid=0");
                return;
            }
            PointVector points;
            ikdtree.flatten(ikdtree.Root_Node, points, NOT_RECORD);
            const bool ok = lab_dump_points(g_nr_dir + "/preview_" + payload + ".xyz32", points);
            nr_write_ack(std::string("OK preview_map valid=") + (ok ? "1" : "0"));
        }
        else if (cmd == "restore")''')
replace('        if (std::getenv("LIO_TWO_EVENT_DIAGNOSTIC"))',
        '''        lab_clock_readonly_preview = std::getenv("LIO_CLOCK_READONLY_PREVIEW") != nullptr;
        if (std::getenv("LIO_TWO_EVENT_DIAGNOSTIC"))''')
replace("            lasermap_fov_segment();",
        "            if (!(lab_clock_readonly_preview && g_nr_hold.load())) lasermap_fov_segment();")
replace("                if (visible) publish_odometry(pubOdomAftMapped);",
        '''                const bool preview_pose = lab_clock_readonly_preview && g_nr_hold.load() &&
                    !g_nr_cur_is_replay && isPublish;
                if (visible || preview_pose) publish_odometry(pubOdomAftMapped);''')
path.write_text(source)
