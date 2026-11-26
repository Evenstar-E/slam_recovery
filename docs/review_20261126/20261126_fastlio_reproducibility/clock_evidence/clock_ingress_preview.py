"""Compare causal timestamp repair on an isolated, expendable native estimator."""
from copy import copy
import json
from pathlib import Path
import sys

import cv2

from clock_confirmation import CHANNEL
from run_return import ReturnController, frozen
from run_confirmation import ObservedController


class Native(ObservedController):
    def receive(self, message, origin, receiver_ns, arrived_wall_ns):
        stamp = message.header.stamp.to_nsec()
        self.imu_through(stamp)
        self.native_pub.publish(message)
        self.latest_scan = stamp

    def flush_clock(self, origin):
        pass


class ClockIngressPreview(ReturnController):
    """Output is from a disposable map. It has no authority to update the trusted host."""

    def __init__(self, out, imu):
        super().__init__(out, imu)
        self.event_file.write(json.dumps({"action": "preview_started"}) + "\n")

    def _forward(self, message, origin, receiver_ns, diagnosis=None):
        self.precomputed_diagnosis = diagnosis
        try:
            self.forward_preview(message, origin, receiver_ns)
        finally:
            self.precomputed_diagnosis = None
        self.last_forwarded_input_ns = message.header.stamp.to_nsec()

    def forward_preview(self, message, origin, receiver_ns):
        if self.mode == "PREVIEW_STOPPED":
            return
        source_stamp = message.header.stamp.to_nsec()
        elapsed = (source_stamp - origin) / frozen.NS
        if self.mode == "CALIBRATING":
            if 28 <= elapsed < 29:
                r, z, ring, usable = frozen.measures(message)
                self.training.append((r[usable], z[usable], ring[usable]))
            elif 29 <= elapsed < 31:
                self.calibration.append(message)
        else:
            reasons, _, _ = self.diagnose(message, origin, receiver_ns)
            if self.beam_alarm(message) or (reasons and reasons != [CHANNEL]):
                self.stop_preview(source_stamp, "additional_geometry_or_unverified_clock")
                return
            if reasons == [CHANNEL]:
                if self.sensor_step is None or self.sensor_step.saw_reverse_edge:
                    self.stop_preview(source_stamp, "no_active_verified_clock_epoch")
                    return
                corrected_stamp = source_stamp - self.sensor_step.offset_ns
                message = copy(message)
                message.header = copy(message.header)
                message.header.stamp = frozen.time_to_ros(corrected_stamp)
                self.event_file.write(json.dumps({
                    "action": "preview_retime",
                    "scan_ns": source_stamp,
                    "corrected_ns": corrected_stamp,
                    "offset_ns": self.sensor_step.offset_ns,
                }) + "\n")
            elif self.sensor_step is not None and self.sensor_step.saw_reverse_edge:
                self.sensor_step = None
        stamp = message.header.stamp.to_nsec()
        if self.latest_scan is not None and stamp <= self.latest_scan:
            self.stop_preview(source_stamp, "nonmonotonic_corrected_stamp")
            return
        self.imu_through(stamp)
        self.native_pub.publish(message)
        self.latest_scan = stamp

    def receive(self, message, origin, receiver_ns, arrived_wall_ns):
        if self.mode == "PREVIEW_STOPPED":
            return
        if self.sensor_step is None:
            return super().receive(message, origin, receiver_ns, arrived_wall_ns)
        # Confirmation has already selected the shifted epoch. Keep passing
        # each subsequent header through the return-edge state machine.
        self.previous_input_ns = message.header.stamp.to_nsec()
        return self._forward(message, origin, receiver_ns)

    def stop_preview(self, scan_ns, reason):
        self.mode = "PREVIEW_STOPPED"
        self.event_file.write(json.dumps({
            "action": "preview_stopped", "scan_ns": scan_ns, "reason": reason,
        }) + "\n")


if __name__ == "__main__":
    from run_return import main

    arm = sys.argv[3]
    controller = {"native": Native, "preview": ClockIngressPreview}[arm]
    cv2.setNumThreads(1)
    main(Path(sys.argv[1]), sys.argv[2], controller=controller, arm=arm)
