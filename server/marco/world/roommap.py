"""Room map: a coloured voxel point cloud in world coordinates, built from every frame's LiDAR depth."""
import numpy as np

from ..geometry import Frame


class RoomMap:
    def __init__(self, voxel_m=0.05, step=4):
        self.voxel, self.step = voxel_m, step
        self.cells = {}                       # (i, j, k) -> [x, y, z, r, g, b]

    def add(self, fr: Frame, rgb: np.ndarray, jpeg_scale: float):
        """Add one frame; returns the newly filled voxels as [[x, y, z, r, g, b], ...]."""
        pts, uvs = fr.point_cloud(step=self.step)
        if not len(pts):
            return []
        keys = np.floor(pts / self.voxel).astype(np.int64)
        h, w = rgb.shape[:2]
        new = []
        for key, p, (u, v) in zip(map(tuple, keys), pts, uvs):
            if key in self.cells:
                continue
            iu, iv = min(int(u * jpeg_scale), w - 1), min(int(v * jpeg_scale), h - 1)
            r, g, b = (int(c) for c in rgb[iv, iu][:3])
            cell = [round(float(p[0]), 3), round(float(p[1]), 3), round(float(p[2]), 3), r, g, b]
            self.cells[key] = cell
            new.append(cell)
        return new

    def points(self):
        return list(self.cells.values())
