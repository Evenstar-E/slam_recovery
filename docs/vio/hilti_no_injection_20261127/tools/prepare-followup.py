import fcntl
import csv
from collections import Counter
import hashlib
import json
from pathlib import Path
import re
import sys

import cv2
import numpy as np
import rosbag
import yaml


root = Path.home() / "vio-multiseq-20261127"
config = root / "config"
cv2.setNumThreads(2)
left, right = ("/alphasense/cam1/image_raw", "/alphasense/cam0/image_raw")
imu = "/alphasense/imu"


def rectification():
    calibration = yaml.safe_load((config / "hilti-source.yaml").read_text())
    cameras = [calibration[f"cam{i}"] for i in (1, 0)]
    size = tuple(cameras[0]["resolution"])
    intrinsics, distortions, body = [], [], []
    for camera in cameras:
        assert tuple(camera["resolution"]) == size and camera["distortion_model"] == "equidistant"
        fx, fy, cx, cy = camera["intrinsics"]
        intrinsics.append(np.array([[fx, 0, cx], [0, fy, cy], [0, 0, 1.]]))
        distortions.append(np.array(camera["distortion_coeffs"]))
        body.append(np.linalg.inv(camera["T_cam_imu"]))
    relative = np.linalg.inv(body[1]) @ body[0]
    rl, rr, pl, pr, _ = cv2.fisheye.stereoRectify(
        intrinsics[0], distortions[0], intrinsics[1], distortions[1], size,
        relative[:3, :3], relative[:3, 3], cv2.CALIB_ZERO_DISPARITY, balance=0)
    maps, valid, transforms = [], [], []
    for k, d, r, p, b in zip(intrinsics, distortions, (rl, rr), (pl, pr), body):
        xy = cv2.fisheye.initUndistortRectifyMap(k, d, r, p[:3, :3], size, cv2.CV_16SC2)
        maps.append(xy)
        coverage = cv2.remap(np.ones(size[::-1], dtype=np.uint8), *xy, cv2.INTER_NEAREST)
        valid.append(float(coverage.mean()))
        transform = np.eye(4)
        transform[:3, :3] = r.T
        transforms.append(b @ transform)
    relation = np.linalg.inv(transforms[0]) @ transforms[1]
    assert np.allclose(relation[:3, :3], np.eye(3), atol=1e-7)
    assert np.allclose(relation[1:3, 3], 0, atol=1e-7) and relation[0, 3] > 0
    assert np.allclose(pl[:3, :3], pr[:3, :3]) and min(valid) > .95
    shift_ns = round(cameras[0]["timeshift_cam_imu"] * 1e9)
    return maps, transforms, relation, (pl, pr), size, valid, shift_ns


def matrix(label, transform, dtype="f"):
    data = json.dumps(transform.ravel().tolist())
    return f"{label}: !!opencv-matrix\n  rows: 4\n  cols: 4\n  dt: {dtype}\n  data: {data}\n"


def settings(transforms, relation, projections, size, valid, shift_ns):
    def parameters(projection):
        return dict(fx=float(projection[0, 0]), fy=float(projection[1, 1]),
                    cx=float(projection[0, 2]), cy=float(projection[1, 2]))

    cameras = list(map(parameters, projections))
    original = (config / "orb-template.yaml").read_text()
    keep = original[original.index("Camera.width:"):]
    orb = '%YAML:1.0\nFile.version: "1.0"\nCamera.type: "PinHole"\n'
    for i, camera in enumerate(cameras, 1):
        calib = dict(camera, k1=0., k2=0., p1=0., p2=0.)
        orb += "".join(f"Camera{i}.{key}: {value}\n" for key, value in calib.items())
    orb += f"Stereo.b: {relation[0, 3]}\n"
    orb += matrix("Stereo.T_c1_c2", relation) + matrix("IMU.T_b_c1", transforms[0]) + keep
    (config / "orb-rectified.yaml").write_text(orb)
    for i, camera in enumerate(cameras):
        cam = dict(model_type="PINHOLE", camera_name=f"cam{i}", image_width=size[0],
                   image_height=size[1], distortion_parameters=dict(k1=0., k2=0., p1=0., p2=0.),
                   projection_parameters=camera)
        (config / f"cam{i}.yaml").write_text("%YAML:1.0\n---\n" + yaml.safe_dump(cam))
    vins = (config / "vins-template.yaml").read_text()
    for i, transform in enumerate(transforms):
        vins, count = re.subn(rf"^body_T_cam{i}: !!opencv-matrix\n(?: +[^\n]*\n){{4}}",
                              matrix(f"body_T_cam{i}", transform, "d"), vins, flags=re.M)
        assert count == 1
    for key, val in (("multiple_thread", 0), ("td", 0.0), ("save_image", 0)):
        vins = re.sub(rf"^{key}:.*$", f"{key}: {val}", vins, flags=re.M)
    (config / "vins-rectified.yaml").write_text(vins)
    okvis = (config / "okvis-template.yaml").read_text()
    block = ""
    for camera, transform in zip(cameras, transforms):
        block += ("  - {T_SC: " + json.dumps(transform.ravel().tolist())
                  + ", image_dimension: " + json.dumps(size)
                  + ", distortion_coefficients: [0.0, 0.0, 0.0, 0.0], distortion_type: radialtangential, "
                  + "focal_length: " + json.dumps([camera["fx"], camera["fy"]])
                  + ", principal_point: " + json.dumps([camera["cx"], camera["cy"]])
                  + ", camera_type: gray, slam_use: okvis}\n")
    okvis = "%YAML:1.0\ncameras:\n" + block + okvis[okvis.index("\ncamera_parameters:"):]
    okvis = re.sub(r"^    image_delay:.*$", "    image_delay: 0.0", okvis, flags=re.M)
    (config / "okvis-rectified.yaml").write_text(okvis)
    receipt = dict(size=list(size), rectified_valid_fraction=valid, projection=cameras,
                   stereo_right_to_left=relation.tolist(), body_from_camera=[t.tolist() for t in transforms],
                   camera_to_imu_shift_ns=shift_ns, calibration_sha256=hashlib.sha256(
                       (config / "hilti-source.yaml").read_bytes()).hexdigest())
    (config / "calibration.json").write_text(json.dumps(receipt, indent=2))


def extract(source, sequence, maps, size, shift_ns):
    dest = root / "inputs" / sequence / "mav0"
    for cam in ("cam0", "cam1"):
        (dest / cam / "data").mkdir(parents=True)
    (dest / "imu0").mkdir()
    counts, buffers, pairs, imu_rows = Counter(), [{}, {}], [], []
    dropped = [0, 0]
    with rosbag.Bag(str(source), "r") as bag:
        for topic, msg, _ in bag.read_messages(topics=(left, right, imu)):
            counts[topic] += 1
            stamp = msg.header.stamp.to_nsec()
            if topic == imu:
                g, a = msg.angular_velocity, msg.linear_acceleration
                imu_rows.append((stamp, g.x, g.y, g.z, a.x, a.y, a.z))
                continue
            idx = int(topic == right)
            buffers[idx][stamp] = msg
            if stamp in buffers[1 - idx]:
                if pairs and stamp <= pairs[-1]:
                    raise ValueError(f"non-increasing paired camera stamp {stamp}")
                for i in range(2):
                    img = buffers[i].pop(stamp)
                    assert (img.width, img.height) == size and img.encoding == "mono8"
                    old = np.frombuffer(img.data, dtype=np.uint8).reshape(img.height, img.step)[:, :img.width]
                    new = cv2.remap(old, *maps[i], cv2.INTER_LINEAR)
                    out = dest / f"cam{i}" / "data" / f"{stamp + shift_ns}.png"
                    if not cv2.imwrite(str(out), new, [cv2.IMWRITE_PNG_COMPRESSION, 1]):
                        raise OSError(f"could not write {out}")
                pairs.append(stamp)
                if len(pairs) % 1000 == 0:
                    print(sequence, len(pairs), flush=True)
            for i, buffer in enumerate(buffers):
                for earlier in list(buffer):
                    if earlier < stamp - 1_000_000_000:
                        del buffer[earlier]
                        dropped[i] += 1

    assert pairs and imu_rows and all(a[0] < b[0] for a, b in zip(imu_rows, imu_rows[1:]))
    sensor_min, sensor_max = imu_rows[0][0], imu_rows[-1][0]
    kept = [t + shift_ns for t in pairs if sensor_min <= t + shift_ns <= sensor_max]
    with (dest / "imu0" / "data.csv").open("w") as stream:
        stream.write("#timestamp [ns],w_x,w_y,w_z,a_x,a_y,a_z\n")
        csv.writer(stream).writerows(imu_rows)
    for i in range(2):
        with (dest / f"cam{i}" / "data.csv").open("w") as stream:
            stream.write("#timestamp [ns],filename\n")
            csv.writer(stream).writerows((t, f"{t}.png") for t in kept)
    gaps = [b[0] - a[0] for a, b in zip(imu_rows, imu_rows[1:])
            if b[0] > kept[0] and a[0] < kept[-1]]
    receipt = dict(sequence=sequence, bag=str(source), bag_bytes=source.stat().st_size,
                   topic_counts=counts, exact_pairs=len(pairs), pairs_in_imu_support=len(kept),
                   imu_gap_max_ns=max(gaps, default=0), imu_gaps_over_15ms=sum(g > 15000000 for g in gaps),
                   unpaired=[dropped[i] + len(buffers[i]) for i in range(2)],
                   first_stamp_ns=kept[0], last_stamp_ns=kept[-1],
                   duration_s=(kept[-1] - kept[0]) / 1e9, same_input_both_modes=True)
    (root / "receipts" / f"{sequence}-input.json").write_text(json.dumps(receipt, indent=2))
    print(json.dumps(receipt), flush=True)


if __name__ == "__main__":
    maps, *calibration = rectification()
    if not (config / "calibration.json").exists():
        settings(*calibration)
    if len(sys.argv) > 1:
        seq = sys.argv[1]
        with (root / "receipts" / f"{seq}-prepare.lock").open("a") as lock:
            fcntl.flock(lock, fcntl.LOCK_EX)
            if not (root / "receipts" / f"{seq}-input.json").is_file():
                extract(Path(sys.argv[2]), seq, maps, calibration[3], calibration[-1])
