"""Compare causal timestamp repair on an isolated, expendable native estimator."""
from copy import copy
import hashlib
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
        self.publish_preview(message, stamp)

    def publish_preview(self, message, stamp):
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
        self.publish_preview(message, stamp)

    def publish_preview(self, message, stamp):
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


class ReadOnlyClockPreview(ClockIngressPreview):
    """Hold the original map until the confirmed clock window and its suffix finish."""

    def __init__(self, out, imu):
        super().__init__(out, imu)
        self.readonly_start = None
        self.healthy_suffix = 0

    def map_evidence(self, label):
        response = self.send("preview_map", label)
        if "valid=1" not in response:
            raise RuntimeError(response)
        return hashlib.sha256((self.ctl / f"preview_{label}.xyz32").read_bytes()).hexdigest()

    def publish_preview(self, message, stamp):
        if self.sensor_step is not None and self.readonly_start is None:
            self.wait_status(self.latest_scan)
            hold = self.send("hold")
            if "valid=1" not in hold or "map_writes=held" not in hold:
                raise RuntimeError(hold)
            self.readonly_start = self.map_evidence("begin")
        elif self.readonly_start is not None and self.sensor_step is None:
            if self.healthy_suffix == 2:
                self.wait_status(self.latest_scan)
                stopped_map = self.map_evidence("end")
                unchanged = stopped_map == self.readonly_start
                self.event_file.write(json.dumps({
                    "action": "preview_readonly_map_verified", "unchanged": unchanged,
                    "before_sha256": self.readonly_start, "after_sha256": stopped_map,
                }) + "\n")
                if not unchanged:
                    self.stop_preview(stamp, "held_map_changed")
                    return
                if "map_writes=released" not in self.send("resume"):
                    raise RuntimeError("native host refused to release the clock preview")
                self.readonly_start = None
                self.healthy_suffix = 0
            else:
                self.healthy_suffix += 1
        super().publish_preview(message, stamp)


class ClockWithNativeFallback(ReadOnlyClockPreview):
    """Route a later nonclock fault through the original lifecycle in the same host."""

    def __init__(self, out, imu):
        super().__init__(out, imu)
        self.native_fallback = False

    def forward_preview(self, message, origin, receiver_ns):
        if self.native_fallback:
            return frozen.AutoZ.handle(self, message, origin, receiver_ns)
        if self.mode == "ARMED" and self.sensor_step is None and self.readonly_start is None:
            reasons, _, _ = self.diagnose(message, origin, receiver_ns)
            if self.beam_alarm(message) or any(reason != CHANNEL for reason in reasons):
                self.native_fallback = True
                self.event_file.write(json.dumps({
                    "action": "preview_native_fallback", "scan_ns": message.header.stamp.to_nsec(),
                }) + "\n")
        if self.native_fallback:
            return frozen.AutoZ.handle(self, message, origin, receiver_ns)
        return super().forward_preview(message, origin, receiver_ns)

    def publish_preview(self, message, stamp):
        super().publish_preview(message, stamp)
        if self.latest_scan == stamp:
            self.previous = message


if __name__ == "__main__":
    from run_return import main

    arm = sys.argv[3]
    controller = {"native": Native, "preview": ClockIngressPreview,
                  "readonly": ReadOnlyClockPreview, "fallback": ClockWithNativeFallback}[arm]
    cv2.setNumThreads(1)
    main(Path(sys.argv[1]), sys.argv[2], controller=controller, arm=arm)
