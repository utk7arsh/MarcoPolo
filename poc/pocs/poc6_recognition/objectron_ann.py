"""Read-only stdlib protobuf parsing of Objectron annotation.pbdata (untrusted data: parse, never execute).

Schema (objectron/schema/annotation_data.proto):
  Sequence { repeated Object objects = 1; repeated FrameAnnotation frame_annotations = 2; }
  FrameAnnotation { int32 frame_id = 1; repeated ObjectAnnotation annotations = 2; float timestamp = 3; ... }
  ObjectAnnotation { int32 object_id = 1; repeated AnnotatedKeyPoint keypoints = 2; float visibility = 3; }
  AnnotatedKeyPoint { int32 id = 1; Point3D point_3d = 2; Point2D point_2d = 3; }
  Point2D { float x = 1; float y = 2; float depth = 3; }   (x, y normalised to [0, 1])
"""
import struct
import sys


def varint(b, i):
    s = o = 0
    while True:
        c = b[i]; i += 1
        o |= (c & 0x7F) << s
        if not c & 0x80:
            return o, i
        s += 7


def fields(b):
    i, n = 0, len(b)
    while i < n:
        k, i = varint(b, i)
        fn, wt = k >> 3, k & 7
        if wt == 0:
            v, i = varint(b, i)
        elif wt == 1:
            v = b[i:i + 8]; i += 8
        elif wt == 2:
            ln, i = varint(b, i); v = b[i:i + ln]; i += ln
        elif wt == 5:
            v = b[i:i + 4]; i += 4
        else:
            raise ValueError("bad wire type")
        yield fn, wt, v


def f32(v):
    return struct.unpack("<f", v)[0]


def boxes(path):
    """Per frame: (frame_id, timestamp, [(x0,y0,x1,y1) normalised, visibility]) from the 2D keypoints."""
    data = open(path, "rb").read()
    out = []
    for fn, wt, v in fields(data):
        if fn != 2 or wt != 2:
            continue
        fid, ts, objs = None, None, []
        for g, wg, w in fields(v):
            if g == 1 and wg == 0:
                fid = w
            elif g == 3 and wg == 5:
                ts = f32(w)
            elif g == 2 and wg == 2:
                xs, ys, vis = [], [], None
                for h, wh, x in fields(w):
                    if h == 3 and wh == 5:
                        vis = f32(x)
                    if h == 2 and wh == 2:
                        for q, wq, y in fields(x):
                            if q == 3 and wq == 2:
                                pt = {r: f32(z) for r, wr, z in fields(y) if wr == 5}
                                if 1 in pt and 2 in pt:
                                    xs.append(pt[1]); ys.append(pt[2])
                if xs:
                    objs.append(((min(xs), min(ys), max(xs), max(ys)), vis))
        out.append((fid, ts, objs))
    return out


if __name__ == "__main__":
    b = boxes(sys.argv[1])
    print(len(b), "frames; first:", b[0], "\nmid:", b[len(b) // 2])
