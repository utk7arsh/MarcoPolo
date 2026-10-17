"""Emulated iPhone Pro on a chest lanyard: ARKit frames with LiDAR depth, and an object detector.

What it outputs mirrors ARFrame:
  camera.transform  4x4 camera-to-world (ARKit axes: camera looks down -z), *as ARKit estimates it*
                    (true pose composed with visual-inertial drift)
  camera.intrinsics 3x3 for the 1920x1440 capturedImage (sensor landscape orientation)
  sceneDepth        256x192 float32 z-depth in metres + confidence (0 low, 1 medium, 2 high)
Numbers come from research/arkit_lidar_facts.md (measured on real ARKitScenes LiDAR vs laser-scan GT).
"""
from dataclasses import dataclass, field

import numpy as np

from scene import intersect

IMG_W, IMG_H = 1920, 1440
DEP_W, DEP_H = 256, 192
FX = FY = 1600.0
CX, CY = 937.0, 710.0
K = np.array([[FX, 0, CX], [0, FY, CY], [0, 0, 1.0]])
SX, SY = DEP_W / IMG_W, DEP_H / IMG_H
UP = np.array([0.0, 1.0, 0.0])


def yaw_vectors(yaw_deg):
    a = np.radians(yaw_deg)
    fwd = np.array([np.sin(a), 0.0, -np.cos(a)])
    right = np.array([np.cos(a), 0.0, np.sin(a)])
    return fwd, right


def chest_camera_pose(torso_xz, torso_yaw, t, tilt_deg=0.0, walking=False, chest_h=1.30, rng=None):
    """Camera-to-world 4x4 for a portrait phone hanging on the chest, camera facing forward.

    Portrait mounting: the sensor's long (1920 px, u) axis points down, so the horizontal
    field of view is the narrow one (~48 deg) and the vertical one is ~62 deg.
    """
    fwd, right = yaw_vectors(torso_yaw)
    bob = sway = swing = 0.0
    if walking:
        ph = 2 * np.pi * 1.8 * t
        bob, sway, swing = 0.02 * np.sin(2 * ph), 0.015 * np.sin(ph), 3.0 * np.sin(ph + 0.5)
    th = np.radians(tilt_deg + swing)
    f_t = np.cos(th) * fwd - np.sin(th) * UP          # optical axis, tilted down by th
    u_t = np.sin(th) * fwd + np.cos(th) * UP          # "up" in the image plane
    x_c, y_c, z_c = -u_t, right, -f_t
    T = np.eye(4)
    T[:3, 0], T[:3, 1], T[:3, 2] = x_c, y_c, z_c
    T[:3, 3] = np.array([torso_xz[0], chest_h + bob, torso_xz[1]]) + 0.12 * fwd + sway * right
    return T


def pixel_rays(T, w=DEP_W, h=DEP_H, fx=FX * SX, fy=FY * SY, cx=CX * SX, cy=CY * SY):
    """World-space ray origins and directions for every depth pixel (direction has camera z = -1)."""
    u, v = np.meshgrid(np.arange(w) + 0.5, np.arange(h) + 0.5)
    dc = np.stack([(u - cx) / fx, -(v - cy) / fy, -np.ones_like(u)], -1).reshape(-1, 3)
    d = dc @ T[:3, :3].T
    o = np.broadcast_to(T[:3, 3], d.shape)
    return o, d


def project(T, pts):
    """World points (N,3) -> pixel (u,v) in the 1920x1440 image and z-depth (positive in front)."""
    R, p = T[:3, :3], T[:3, 3]
    pc = (pts - p) @ R
    z = -pc[:, 2]
    with np.errstate(divide="ignore", invalid="ignore"):
        u = CX + FX * pc[:, 0] / z
        v = CY - FY * pc[:, 1] / z
    return np.stack([u, v], -1), z


def unproject(T, u, v, z):
    """Pixel in the 1920x1440 image + z-depth -> world point."""
    pc = np.array([(u - CX) / FX * z, -(v - CY) / FY * z, -z])
    return T[:3, :3] @ pc + T[:3, 3]


@dataclass
class LidarModel:
    """Noise model fitted to ARKitScenes iPad Pro LiDAR vs Faro laser GT (high confidence)."""
    scale_bias: float = -0.012     # reads ~1.2 % short
    sd_a: float = 0.012            # sd = a + b * z  (m)
    sd_b: float = 0.011
    frame_offset_sd: float = 0.01
    iphone_factor: float = 1.5     # ScanNet++ iPhone 13 Pro RMSE is ~1.5-2x the iPad table
    lowconf_sd: float = 0.15
    max_range: float = 5.0

    def p_high(self, z):
        return np.interp(z, [0, 1, 2, 3, 4, 5, 8], [0.98, 0.98, 0.95, 0.89, 0.88, 0.77, 0.3])


@dataclass
class VIODrift:
    """ARKit world-tracking error: grows with distance walked (~0.3 %) plus slow yaw drift."""
    pos_rate: float = 0.003         # m of drift per m travelled (direction wanders slowly)
    yaw_rw_deg_per_sqrt_min: float = 0.5
    rng: np.random.Generator = field(default_factory=lambda: np.random.default_rng(0))

    def __post_init__(self):
        self.offset = np.zeros(3)
        self.yaw = 0.0
        self.dirn = self.rng.normal(size=3); self.dirn[1] *= 0.3
        self.dirn /= np.linalg.norm(self.dirn)
        self.last = None

    def update(self, true_pos, dt):
        if self.last is not None:
            step = np.linalg.norm(true_pos - self.last)
            self.dirn += self.rng.normal(0, 0.3 * np.sqrt(dt), 3); self.dirn[1] *= 0.9
            self.dirn /= np.linalg.norm(self.dirn)
            self.offset += self.pos_rate * step * self.dirn
            self.yaw += self.rng.normal(0, self.yaw_rw_deg_per_sqrt_min * np.sqrt(dt / 60))
        self.last = true_pos.copy()

    def apply(self, T):
        """Compose drift: ARKit's estimate of the pose (rotation about world up + translation)."""
        a = np.radians(self.yaw)
        Ry = np.array([[np.cos(a), 0, np.sin(a)], [0, 1, 0], [-np.sin(a), 0, np.cos(a)]])
        out = np.eye(4)
        out[:3, :3] = Ry @ T[:3, :3]
        out[:3, 3] = Ry @ T[:3, 3] + self.offset
        return out


class Phone:
    def __init__(self, room, rng, lidar=None, drift=None):
        self.room, self.rng = room, rng
        self.lidar = lidar or LidarModel()
        self.drift = drift or VIODrift(rng=np.random.default_rng(rng.integers(1 << 30)))

    def frame(self, T_true, t, dt=1 / 60):
        """One ARFrame: estimated pose, depth, confidence, and ground truth for the detector."""
        self.drift.update(T_true[:3, 3], dt)
        o, d = pixel_rays(T_true)
        z, idx = self.room.cast(o, d)
        z = z.reshape(DEP_H, DEP_W)
        idx = idx.reshape(DEP_H, DEP_W)
        prims = self.room.prims()
        z_behind = None
        if any(getattr(p, "material", "") == "transparent" for p in prims):
            opaque = [p for p in prims if getattr(p, "material", "") != "transparent"]
            zb, _ = self.room.cast(o, d, only=opaque)
            z_behind = zb.reshape(DEP_H, DEP_W)
        depth, conf = self._noisy(z, idx, prims, z_behind)
        return dict(t=t, T_arkit=self.drift.apply(T_true), T_true=T_true, depth=depth.astype(np.float32),
                    conf=conf, gt_depth=z, gt_idx=idx, prims=prims)

    def _noisy(self, z, idx, prims, z_behind=None):
        L, r = self.lidar, self.rng
        mat = np.array(["shell"] + [getattr(p, "material", "matte") for p in prims])[idx + 1]
        zt = z.copy()
        # Transparent items: ToF sees what is behind them.
        tr = mat == "transparent"
        if tr.any() and z_behind is not None:
            zt[tr] = z_behind[tr]
        # Edges: depth jump or id change -> flying pixels mixing foreground and background.
        zz = np.pad(zt, 1, mode="edge")
        nb_max = np.max([zz[1 + dy:DEP_H + 1 + dy, 1 + dx:DEP_W + 1 + dx] for dy in (-1, 0, 1) for dx in (-1, 0, 1)], axis=0)
        nb_min = np.min([zz[1 + dy:DEP_H + 1 + dy, 1 + dx:DEP_W + 1 + dx] for dy in (-1, 0, 1) for dx in (-1, 0, 1)], axis=0)
        edge = (nb_max - nb_min) > 0.1 * zt
        w = r.uniform(0, 1, zt.shape)
        mix = edge & (r.uniform(size=zt.shape) < 0.5)
        zt = np.where(mix, w * nb_min + (1 - w) * nb_max, zt)
        # Small protrusions (<~6 depth px across) are pulled toward the background.
        for k, p in enumerate(prims):
            m = idx == k
            n = int(m.sum())
            if 0 < n <= 30 and getattr(p, "is_item", False):
                bg = np.median(nb_max[m])
                frac = r.uniform(0.3, 1.0) if n <= 6 else r.uniform(0.0, 0.6)
                zt[m] = zt[m] + frac * (bg - zt[m])
        p_hi = L.p_high(zt)
        p_hi = np.where(edge, 0.62, p_hi)
        p_hi = np.where(np.isin(mat, ["dark", "specular", "transparent"]), 0.35, p_hi)
        u = r.uniform(size=zt.shape)
        conf = np.where(u < p_hi, 2, np.where(u < p_hi + (1 - p_hi) * 0.7, 1, 0)).astype(np.uint8)
        sd = L.iphone_factor * (L.sd_a + L.sd_b * zt)
        sd = np.where(conf == 2, sd, L.lowconf_sd)
        out = zt * (1 + L.scale_bias) + r.normal(0, L.frame_offset_sd) + r.normal(0, 1, zt.shape) * sd
        out = np.where(zt > L.max_range, r.uniform(3, 5, zt.shape), out)
        conf = np.where(zt > L.max_range, 0, conf).astype(np.uint8)
        return np.clip(out, 0.05, 10), conf


@dataclass
class DetectorModel:
    """Object detector + personal-item recogniser behaviour, as a function of image evidence.

    h50_px: object size (longest bbox side in the 1920x1440 image) detected 50 % of the time.
    COCO-style small-object recall motivates ~24 px for easy classes; keys are harder (~40 px).
    """
    h50_px: dict = field(default_factory=lambda: {"keys": 40.0, "default": 26.0})
    slope: float = 0.35          # in log2(px) units
    min_visible: float = 0.35
    exposure_s: float = 1 / 60
    bbox_jitter: float = 0.04
    fp_rate: float = 0.01        # spurious detections per detector run

    def p_detect(self, name, h_px, vis, blur_px):
        h50 = self.h50_px.get(name, self.h50_px["default"])
        ps = 1 / (1 + np.exp(-(np.log2(max(h_px, 1)) - np.log2(h50)) / self.slope))
        pv = np.clip((vis - self.min_visible) / 0.4, 0, 1)
        pb = np.exp(-blur_px / max(0.6 * h_px, 1))
        return ps * pv * pb


def detect(frame, room, det: DetectorModel, rng, ang_speed_deg_s=0.0):
    """Run the emulated detector on a frame. Returns list of dicts with bbox (1920x1440 px)."""
    T = frame["T_true"]
    prims = frame["prims"]
    out = []
    px_per_deg = FX * np.pi / 180
    blur = ang_speed_deg_s * det.exposure_s * px_per_deg
    for k, p in enumerate(prims):
        if not getattr(p, "is_item", False):
            continue
        uv, z = project(T, p.corners())
        if np.any(z <= 0.05):
            continue
        u0, v0 = uv.min(0)
        u1, v1 = uv.max(0)
        if u1 < 0 or v1 < 0 or u0 > IMG_W or v0 > IMG_H:
            continue
        cu0, cv0, cu1, cv1 = max(u0, 0), max(v0, 0), min(u1, IMG_W), min(v1, IMG_H)
        in_frame = (cu1 - cu0) * (cv1 - cv0) / max((u1 - u0) * (v1 - v0), 1e-9)
        # Occlusion: fraction of the object's own pixels that are its own in the full render.
        o, d = pixel_rays(T)
        alone = np.isfinite(intersect(p, o, d))
        n_alone = int(alone.sum())
        if n_alone == 0:
            c = p.center[None]
            (cu, cv), zc = project(T, c)[0][0], project(T, c)[1][0]
            iu, iv = int(cu * SX), int(cv * SY)
            if not (0 <= iu < DEP_W and 0 <= iv < DEP_H):
                continue
            vis = 1.0 if frame["gt_depth"][iv, iu] >= zc - 0.05 else 0.0
        else:
            vis = float((frame["gt_idx"].ravel()[alone] == k).sum()) / n_alone
        vis *= in_frame
        h = max(cu1 - cu0, cv1 - cv0)
        if rng.uniform() < det.p_detect(p.name, h, vis, blur):
            s = det.bbox_jitter
            w_, h_ = cu1 - cu0, cv1 - cv0
            j = rng.normal(0, s, 4) * np.array([w_, h_, w_, h_])
            out.append(dict(label=p.name, bbox=np.array([cu0, cv0, cu1, cv1]) + j, true_index=k, size_px=h, visible=vis))
    if rng.uniform() < det.fp_rate:
        u, v = rng.uniform(100, IMG_W - 100), rng.uniform(100, IMG_H - 100)
        sz = rng.uniform(30, 120)
        names = [p.name for p in prims if getattr(p, "is_item", False)]
        out.append(dict(label=str(rng.choice(names)), bbox=np.array([u, v, u + sz, v + sz]), true_index=-1, size_px=sz, visible=1.0))
    return out
