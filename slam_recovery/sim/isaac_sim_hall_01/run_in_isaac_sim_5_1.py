"""Standalone loader for NVIDIA Isaac Sim 5.1.

    ./python.sh run_in_isaac_sim_5_1.py
or open `hall_01_isaac_scene.usda` directly from the Isaac Sim GUI (File -> Open).
Then press Play (Spacebar) to replay the 350 s timeline.
"""
from pathlib import Path

from isaacsim import SimulationApp

simulation_app = SimulationApp({"headless": False, "width": 1920, "height": 1080})

import omni.timeline
import omni.usd

stage_path = (Path(__file__).resolve().parent / "hall_01_isaac_scene.usda").as_posix()
print(f"[Isaac Sim 5.1] opening {stage_path}")
omni.usd.get_context().open_stage(stage_path)

timeline = omni.timeline.get_timeline_interface()
timeline.set_start_time(0.0)
timeline.set_end_time(350.0 / 20.0)
timeline.play()

while simulation_app.is_running():
    simulation_app.update()

simulation_app.close()
