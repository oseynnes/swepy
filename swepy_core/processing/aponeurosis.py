"""Aponeurosis ROI: locate an aponeurosis on the B-mode image and build standard ROIs around it.

Principle (see docs/aponeurosis_mode.md):
    - The aponeurosis is a thin bright line on B-mode. In the SWE map, it appears as a ridge of higher
      shear wave velocity, blurred over a few mm by the limited resolution of SWE.
    - The line is located on the B-mode image (time-averaged, bottom field of view, without colour overlay),
      either from a click on the aponeurosis (the line is followed from the click) or from points clicked
      along it (manual line).
    - The ROI is a band of fixed half-width (default 1 mm) around the line, within the SWE box minus a margin.
    - A reference band in the adjacent muscle (default 3-8 mm from the line, on the chosen side) is also
      measured, to report values relative to muscle.

Coordinates: rows and columns are relative to the SWE box (B-mode region of the same size). Image coordinates
are obtained by adding the box origin (x0, y0) of the top field of view.
"""
import numpy as np
from scipy.ndimage import gaussian_filter, white_tophat

BAND_HALF_WIDTH_MM = 1.0       # half-width of the aponeurosis band
REF_NEAR_MM, REF_FAR_MM = 3.0, 8.0   # reference muscle band, distance from the line
EDGE_MARGIN_MM = 1.0           # part of the SWE box excluded (box outline and edge artefacts)
MIN_EDGE_DISTANCE_MM = 2.0     # below this distance between line and box edge, results are flagged
SEED_TOLERANCE_MM = 1.0        # a click must be within this distance of the aponeurosis
SUGGESTION_TOLERANCE_MM = 2.0  # tolerance when re-using the depth of a previous file


def ridge_image(bmode, px_mm):
    """Enhance thin bright horizontal-ish structures (aponeuroses, fasciae) of a B-mode image"""
    img = gaussian_filter(np.asarray(bmode, dtype=float), sigma=(1, 3))
    return white_tophat(img, size=(max(3, int(round(4 / px_mm))), 1))


def _dp(ridge, cols, start_scores, max_step=1, step_penalty=0.0):
    """Dynamic programming along columns: brightest continuous path (row change <= max_step per column)
    Returns rows of the path for each column in cols"""
    h = ridge.shape[0]
    score = start_scores.astype(float)
    backs = []
    for c in cols[1:]:
        candidates, moves = [], []
        for dy in range(-max_step, max_step + 1):
            shifted = np.full(h, -np.inf)
            if dy >= 0:
                shifted[dy:] = score[:h - dy] if dy else score
            else:
                shifted[:dy] = score[-dy:]
            candidates.append(shifted - step_penalty * abs(dy))
            moves.append(dy)
        candidates = np.array(candidates)
        best = candidates.argmax(axis=0)
        backs.append(np.arange(h) - np.array(moves)[best])     # previous row for each row
        score = candidates.max(axis=0) + ridge[:, c]
    rows = np.empty(len(cols), dtype=int)
    rows[-1] = int(np.argmax(score))
    for i in range(len(cols) - 1, 0, -1):
        rows[i - 1] = backs[i - 1][rows[i]]
    return rows


def track_line(bmode, px_mm, seed_col, seed_row, tolerance_mm=SEED_TOLERANCE_MM):
    """Follow the bright line passing near a seed point, to both sides of the box
    Args:
        bmode: B-mode image of the SWE box region
        px_mm: pixel size (mm)
        seed_col, seed_row: seed position (box coordinates), e.g. a click on the aponeurosis
        tolerance_mm: the line must pass within this distance of the seed
    Returns: row of the line in each column of the box
    """
    ridge = ridge_image(bmode, px_mm)
    h, w = ridge.shape
    seed_col, seed_row = int(np.clip(seed_col, 0, w - 1)), int(np.clip(seed_row, 0, h - 1))
    tol = max(1, int(round(tolerance_mm / px_mm)))
    start = np.full(h, -np.inf)
    lo, hi = max(0, seed_row - tol), min(h, seed_row + tol + 1)
    start[lo:hi] = ridge[lo:hi, seed_col]
    penalty = 0.05 * float(np.median(ridge[ridge > 0])) if (ridge > 0).any() else 0.0
    right = _dp(ridge, list(range(seed_col, w)), start, step_penalty=penalty)
    # the left part starts from the row chosen at the seed column by the right part
    rows = np.empty(w, dtype=int)
    rows[seed_col:] = right
    left_fixed = _dp(ridge, list(range(seed_col, -1, -1)), _single(h, right[0]), step_penalty=penalty)
    rows[:seed_col + 1] = left_fixed[::-1]
    return rows


def _single(h, row):
    start = np.full(h, -np.inf)
    start[row] = 0.0
    return start


def candidate_lines(bmode, px_mm, skip_top_mm=3.0, skip_bottom_mm=1.5, n=3, separation_mm=2.5):
    """Strongest continuous bright lines of the box (strongest first), each with its mean ridge strength"""
    ridge = ridge_image(bmode, px_mm)
    h, w = ridge.shape
    lo, hi = int(skip_top_mm / px_mm), h - int(skip_bottom_mm / px_mm)
    work = ridge.copy()
    work[:lo] = 0
    work[hi:] = 0
    lines = []
    for _ in range(n):
        start = np.where((np.arange(h) >= lo) & (np.arange(h) < hi), work[:, 0], -np.inf)
        rows = _dp(work, list(range(w)), start)
        strength = float(np.mean(ridge[rows, np.arange(w)]))
        lines.append((rows, strength))
        sep = int(round(separation_mm / px_mm))
        for c, r in enumerate(rows):                       # suppress this line before searching the next one
            work[max(0, r - sep):r + sep + 1, c] = 0
    return lines


def suggest_line(bmode, px_mm, previous_depth_row=None):
    """Suggest the aponeurosis line automatically
    Args:
        previous_depth_row: row of the aponeurosis in a previous recording of the same structure (box
            coordinates), e.g. the previous file of the same plane and aponeurosis. Tested on pilot data:
            LONG 100%, TRANS LOW 97%, TRANS UP 86% correct (vs 100%, 95%, 70% for the strongest line).
    Returns: (rows, how) where how describes the rule used
    """
    h, w = bmode.shape
    if previous_depth_row is not None and 0 <= previous_depth_row < h:
        return track_line(bmode, px_mm, w // 2, int(previous_depth_row), SUGGESTION_TOLERANCE_MM), 'depth of previous file'
    return candidate_lines(bmode, px_mm, n=1)[0][0], 'strongest line'


def line_from_points(points, w, h):
    """Line rows for each column from points clicked along the aponeurosis (manual line)
    Args:
        points: list of (col, row) in box coordinates, at least 2
    Returns: rows (float, NaN outside the clicked extent)
    """
    pts = sorted(points)
    cols, rows = np.array([p[0] for p in pts], float), np.array([p[1] for p in pts], float)
    out = np.full(w, np.nan)
    inside = (np.arange(w) >= cols.min()) & (np.arange(w) <= cols.max())
    out[inside] = np.clip(np.interp(np.arange(w)[inside], cols, rows), 0, h - 1)
    return out


def band_polygon(rows, h, w, px_mm, near_mm, far_mm, side=0, margin_mm=EDGE_MARGIN_MM):
    """Polygon (box coordinates) of a band following the line
    Args:
        rows: line row for each column (NaN where undefined)
        near_mm, far_mm: band limits from the line (side=0: symmetric band of half-width far_mm)
        side: 0 = centred on the line, 1 = below (deeper), -1 = above
    Returns: (polygon as list of (col, row), fraction of the intended band area inside the box)
    """
    m = int(round(margin_mm / px_mm))
    cols = np.arange(w)
    valid = ~np.isnan(rows) & (cols >= m) & (cols <= w - 1 - m)
    rows = np.asarray(rows, float)
    if side == 0:
        top, bottom = rows - far_mm / px_mm, rows + far_mm / px_mm
    elif side > 0:
        top, bottom = rows + near_mm / px_mm, rows + far_mm / px_mm
    else:
        top, bottom = rows - far_mm / px_mm, rows - near_mm / px_mm
    intended = (bottom - top)[valid].sum()
    top, bottom = np.clip(top, m, h - 1 - m), np.clip(bottom, m, h - 1 - m)
    keep = valid & (bottom - top >= 1)
    if keep.sum() < 2:
        return [], 0.0
    c = cols[keep]
    upper = [(int(x), int(round(y))) for x, y in zip(c, top[keep])]
    lower = [(int(x), int(round(y))) for x, y in zip(c[::-1], bottom[keep][::-1])]
    covered = (bottom - top)[keep].sum()
    return upper + lower, float(covered / intended) if intended else 0.0


def geometry(rows, h, px_mm, bmode=None):
    """Quality descriptors of the line: depth, tilt, distance to the box edges, coverage, visibility"""
    rows = np.asarray(rows, float)
    valid = ~np.isnan(rows)
    cols = np.arange(len(rows))[valid]
    r = rows[valid]
    slope = np.polyfit(cols, r, 1)[0] if len(cols) > 1 else 0.0
    edge = np.minimum(r, h - 1 - r) * px_mm
    info = {'line_coverage_%': 100 * valid.mean(),
            'line_tilt_deg': float(np.degrees(np.arctan(slope))),
            'min_edge_distance_mm': float(edge.min()) if len(edge) else np.nan,
            'median_edge_distance_mm': float(np.median(edge)) if len(edge) else np.nan}
    if bmode is not None and len(cols):
        b = gaussian_filter(np.asarray(bmode, float), sigma=(1, 2))
        on = b[np.round(r).astype(int), cols]
        off = []
        for d in (-3, 3):                                    # B-mode 3 mm above and below the line
            rr = np.clip(np.round(r + d / px_mm).astype(int), 0, h - 1)
            off.append(b[rr, cols])
        info['bmode_line_contrast'] = float(np.median(on) / max(np.median(np.concatenate(off)), 1e-6))
    info['edge_warning'] = bool(info['min_edge_distance_mm'] < MIN_EDGE_DISTANCE_MM)
    return info
