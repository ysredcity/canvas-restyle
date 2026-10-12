"""几何工具：盒子 (x, y, w, h) 的包含与重叠。与具体工具无关。"""


def inside(a, b, tol=2):
    """a 完全落在 b 内。"""
    return a[0] >= b[0] - tol and a[1] >= b[1] - tol and a[0] + a[2] <= b[0] + b[2] + tol and a[1] + a[3] <= b[1] + b[3] + tol


def overlap_ratio(a, b):
    """重叠面积 / 较小者面积。"""
    w = min(a[0] + a[2], b[0] + b[2]) - max(a[0], b[0]); h = min(a[1] + a[3], b[1] + b[3]) - max(a[1], b[1])
    if w <= 0 or h <= 0: return 0
    return w * h / max(1, min(a[2] * a[3], b[2] * b[3]))
