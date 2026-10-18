"""Geometry shared by the whole server (INTERFACES.md §2, POC 23).

- Matrices arrive column-major (simd layout); images and depth arrive in the SENSOR orientation.
- Camera space is ARKit's: x right and y up in the sensor image, the camera looks down -z.
- The upright rotation for detection comes from gravity in each frame, so any vest mounting works.
- A 2D box becomes a 3D world position with the pose and depth of the frame the box came from, never the
  current pose (0.3 s of server latency with the current pose put items 50 cm off in POC 23).
"""
import math

import numpy as np

UP = np.array([0.0, 1.0, 0.0])


# ---------------------------------------------------------------- matrices
def mat4(flat):
    a = np.asarray(flat, dtype=float)
    if a.size != 16:
        raise ValueError(f"expected 16 numbers for a 4x4 matrix, got {a.size}")
    return a.reshape(4, 4).T                      # column-major in, row-major numpy out


def mat3(flat):
    a = np.asarray(flat, dtype=float)
    if a.size != 9:
        raise ValueError(f"expected 9 numbers for a 3x3 matrix, got {a.size}")
    return a.reshape(3, 3).T


def flat_colmajor(M):
    return np.asarray(M, dtype=float).T.reshape(-1).tolist()


def check_pose(T):
    """Raise if T is not a rigid camera-to-world transform."""
    R = T[:3, :3]
    if not np.allclose(R.T @ R, np.eye(3), atol=1e-3) or abs(np.linalg.det(R) - 1) > 1e-3:
        raise ValueError("camera_transform rotation is not orthonormal (wrong matrix order?)")
    if not np.allclose(T[3], [0, 0, 0, 1], atol=1e-6):
        raise ValueError("camera_transform last row must be 0 0 0 1 (is it row-major instead of column-major?)")


# ---------------------------------------------------------------- image orientation
def upright_turns(T):
    """Quarter turns CLOCKWISE that make the sensor image upright (0..3), from gravity in the camera frame.
    Portrait vest mount (the sensor's long axis points down): 1."""
    up_cam = T[:3, :3].T @ UP                    # world up, in camera coordinates
    ux, uy = up_cam[0], up_cam[1]                # image 'up' is (+u if ux > 0) / (top if uy > 0)
    if abs(uy) >= abs(ux):
        return 0 if uy > 0 else 2
    return 1 if ux < 0 else 3


def rotate_point(x, y, k, w, h):
    """Point in an image of size (w, h) -> the same point after k clockwise quarter turns (continuous px)."""
    k %= 4
    if k == 0:
        return x, y
    if k == 1:
        return h - y, x
    if k == 2:
        return w - x, h - y
    return y, w - x


def unrotate_point(x, y, k, w, h):
    """Inverse of rotate_point: (w, h) is the size of the ORIGINAL (unrotated) image."""
    k %= 4
    if k == 0:
        return x, y
    if k == 1:
        return y, h - x
    if k == 2:
        return w - x, h - y
    return w - y, x


def rotate_box(b, k, w, h):
    (x0, y0), (x1, y1) = rotate_point(b[0], b[1], k, w, h), rotate_point(b[2], b[3], k, w, h)
    return [min(x0, x1), min(y0, y1), max(x0, x1), max(y0, y1)]


def unrotate_box(b, k, w, h):
    (x0, y0), (x1, y1) = unrotate_point(b[0], b[1], k, w, h), unrotate_point(b[2], b[3], k, w, h)
    return [min(x0, x1), min(y0, y1), max(x0, x1), max(y0, y1)]


def detector_box_to_sensor(box, k, jpeg_w, jpeg_h, jpeg_scale):
    """Box from the detector on the upright image -> box in full-resolution sensor pixels (intrinsics space)."""
    b = unrotate_box(box, k, jpeg_w, jpeg_h)
    return [v / jpeg_scale for v in b]


# ---------------------------------------------------------------- camera model
class Frame:
    """What one ARFrame gives us: pose, intrinsics at image_resolution, depth + confidence (sensor orientation)."""

    def __init__(self, T, K, image_resolution, depth, conf):
        self.T, self.K = np.asarray(T, float), np.asarray(K, float)
        self.W, self.H = image_resolution
        self.depth, self.conf = depth, conf
        self.dh, self.dw = depth.shape
        self.sx, self.sy = self.dw / self.W, self.dh / self.H

    def ray(self, u, v):
        fx, fy, cx, cy = self.K[0, 0], self.K[1, 1], self.K[0, 2], self.K[1, 2]
        d = self.T[:3, :3] @ np.array([(u - cx) / fx, -(v - cy) / fy, -1.0])
        return self.T[:3, 3], d / np.linalg.norm(d)

    def unproject(self, u, v, z):
        fx, fy, cx, cy = self.K[0, 0], self.K[1, 1], self.K[0, 2], self.K[1, 2]
        pc = np.array([(u - cx) / fx * z, -(v - cy) / fy * z, -z])
        return self.T[:3, :3] @ pc + self.T[:3, 3]

    def project(self, pts):
        """World points (N,3) -> sensor pixels (N,2) and z-depth (N,)."""
        fx, fy, cx, cy = self.K[0, 0], self.K[1, 1], self.K[0, 2], self.K[1, 2]
        pc = (np.atleast_2d(pts) - self.T[:3, 3]) @ self.T[:3, :3]
        z = -pc[:, 2]
        with np.errstate(divide="ignore", invalid="ignore"):
            return np.stack([cx + fx * pc[:, 0] / z, cy - fy * pc[:, 1] / z], -1), z

    def depth_at(self, u, v, r=1, min_conf=2):
        iu, iv = int(u * self.sx), int(v * self.sy)
        if not (0 <= iu < self.dw and 0 <= iv < self.dh):
            return None
        win = self.depth[max(iv - r, 0): iv + r + 1, max(iu - r, 0): iu + r + 1]
        cw = self.conf[max(iv - r, 0): iv + r + 1, max(iu - r, 0): iu + r + 1]
        good = win[(cw >= min_conf) & np.isfinite(win)]
        return float(np.median(good)) if good.size else None

    def point_cloud(self, step=4, min_conf=2):
        """World points of every `step`-th depth pixel with enough confidence, plus their sensor pixels."""
        vs, us = np.mgrid[0:self.dh:step, 0:self.dw:step]
        z = self.depth[vs, us]
        ok = (self.conf[vs, us] >= min_conf) & np.isfinite(z) & (z > 0.1) & (z < 5.0)
        u = (us[ok] + 0.5) / self.sx
        v = (vs[ok] + 0.5) / self.sy
        z = z[ok]
        fx, fy, cx, cy = self.K[0, 0], self.K[1, 1], self.K[0, 2], self.K[1, 2]
        pc = np.stack([(u - cx) / fx * z, -(v - cy) / fy * z, -z], -1)
        return pc @ self.T[:3, :3].T + self.T[:3, 3], np.stack([u, v], -1)


def locate_median(box, fr: Frame):
    """Median of high-confidence depth over the inner half of the box (sensor pixels)."""
    u0, v0, u1, v1 = box
    cu, cv, hw, hh = (u0 + u1) / 2, (v0 + v1) / 2, (u1 - u0) / 4, (v1 - v0) / 4
    iu0, iu1 = int(max(cu - hw, 0) * fr.sx), int(min(cu + hw, fr.W - 1) * fr.sx) + 1
    iv0, iv1 = int(max(cv - hh, 0) * fr.sy), int(min(cv + hh, fr.H - 1) * fr.sy) + 1
    d, c = fr.depth[iv0:iv1, iu0:iu1], fr.conf[iv0:iv1, iu0:iu1]
    vals = d[(c == 2) & np.isfinite(d)] if (c == 2).any() else d[np.isfinite(d)].ravel()
    return None if vals.size == 0 else fr.unproject(cu, cv, float(np.median(vals)))


def locate_footprint(box, fr: Frame):
    """Where the object meets its supporting surface (robust for small, thin and glass items; POC 1).
    1. the box edge that is lowest in the world; 2. the surface height from LiDAR just beyond that edge;
    3. the camera ray through the contact point, intersected with that horizontal plane."""
    u0, v0, u1, v1 = box
    cu, cv = (u0 + u1) / 2, (v0 + v1) / 2
    edges = {"u1": (u1, cv), "u0": (u0, cv), "v1": (cu, v1), "v0": (cu, v0)}
    k = min(edges, key=lambda e: fr.ray(*edges[e])[1][1])
    bu, bv = edges[k]
    du, dv = {"u1": (1, 0), "u0": (-1, 0), "v1": (0, 1), "v0": (0, -1)}[k]
    size = max(u1 - u0, v1 - v0)
    ys = []
    for s in np.linspace(0.08, 0.35, 6) * max(size, 60):
        for lat in np.linspace(-0.5, 0.5, 5) * max(size, 60):
            u = bu + du * s + (lat if du == 0 else 0)
            v = bv + dv * s + (lat if dv == 0 else 0)
            if 0 <= u < fr.W and 0 <= v < fr.H:
                z = fr.depth_at(u, v, r=0, min_conf=2)
                if z is not None:
                    ys.append(fr.unproject(u, v, z)[1])
    if len(ys) < 4:
        return locate_median(box, fr)
    h = float(np.median(ys))
    o, d = fr.ray(bu, bv)
    if d[1] > -0.05:
        return locate_median(box, fr)
    t = (h - o[1]) / d[1]
    return o + t * d if 0.1 < t < 6 else locate_median(box, fr)


# ---------------------------------------------------------------- body-relative directions
def heading_deg(T):
    """Heading of the chest camera's optical axis on the floor: 0 = world -z, +90 = world +x (turning right)."""
    f = -T[:3, 2]
    return math.degrees(math.atan2(f[0], -f[2]))


def wrap180(a):
    return (a + 180.0) % 360.0 - 180.0


def relative_azimuth_deg(user_pos, heading, target):
    """Target direction relative to the user's heading: 0 ahead, +90 right, -90 left, 180 behind."""
    d = np.asarray(target, float) - np.asarray(user_pos, float)
    return wrap180(math.degrees(math.atan2(d[0], -d[2])) - heading)


def clock_position(rel_az):
    c = int(round(rel_az / 30.0)) % 12
    return 12 if c == 0 else c


def steps(horizontal_m, step_m=0.7):
    return max(1, int(round(horizontal_m / step_m)))


def horizontal_distance(a, b):
    d = np.asarray(b, float) - np.asarray(a, float)
    return float(math.hypot(d[0], d[2]))


def surface_name(height_m):
    """Name a support surface by its height (until the user names places in setup)."""
    if height_m < 0.2:
        return "floor"
    if height_m < 0.6:
        return "seat"
    if height_m < 0.85:
        return "table"
    if height_m < 1.05:
        return "counter"
    return "shelf"
