"""Recognise on-screen labels (colour scale maximum, SWE frequency) to fill in user entries safely.

Scanners burn the settings into the image as text. swepy does not read the text, but remembers the exact
pixel pattern of each label together with the value the user entered for it. When a file shows a label
already seen, its value is filled in automatically; when it shows a new label, the entry is cleared so the
user has to enter it (instead of silently re-using the previous file's value).

On Mach30 exports, identical labels match pixel for pixel (0 differing pixels between files), while labels
differing by one character (e.g. "11.0" vs "12.0 m/s") differ by at least 7 pixels.
"""
import numpy as np

from swepy_core.processing import data_utils
from swepy_core.processing.io.pickle_io import load_pickle, save_pickle

MAX_DIFFERING_PIXELS = 2
TEXT_THRESHOLD = 110          # grey level of burned-in text
SCALE_REGION = (54, 68, 630, 720)   # rows, columns of the label above the colour bar (y0, y1, x0, x1)


def _grey(frame):
    frame = np.asarray(frame)
    return frame.astype(float).mean(axis=2) if frame.ndim == 3 else frame.astype(float)


def scale_label(frame):
    """Mask of the colour scale label (e.g. '>=12.0 m/s'), or None if no text is found"""
    y0, y1, x0, x1 = SCALE_REGION
    mask = _grey(frame)[y0:y1, x0:x1] > TEXT_THRESHOLD
    return mask if mask.sum() > 10 else None


def _text_lines(grey, x0, x1, y0, y1):
    on = (grey[y0:y1, x0:x1] > TEXT_THRESHOLD).any(axis=1)
    lines, y = [], 0
    while y < len(on):
        if on[y]:
            start = y
            while y < len(on) and on[y]:
                y += 1
            lines.append((y0 + start, y0 + y))
        y += 1
    return lines


def frequency_label(frame):
    """Mask of the SWE frequency line (e.g. 'Pen/1.1 Hz', first line under the 'SWE' heading), or None"""
    grey = _grey(frame)
    lines = _text_lines(grey, 0, 130, 150, min(300, grey.shape[0]))
    for (start, end), (next_start, _) in zip(lines, lines[1:]):
        if 5 <= end - start <= 10 and (grey[start:end, 0:45] > TEXT_THRESHOLD).sum() > 15:   # 'SWE' heading
            mask = grey[next_start - 1:next_start + 10, 0:130] > TEXT_THRESHOLD
            return mask if mask.sum() > 10 else None
    return None


def label_crop(frame, kind):
    """Image crop of a label, for display next to the entry fields"""
    frame = np.asarray(frame)
    if kind == 'scale':
        y0, y1, x0, x1 = SCALE_REGION
        return frame[y0:y1, x0:x1]
    grey = _grey(frame)
    lines = _text_lines(grey, 0, 130, 150, min(300, grey.shape[0]))
    for (start, end), (next_start, _) in zip(lines, lines[1:]):
        if 5 <= end - start <= 10 and (grey[start:end, 0:45] > TEXT_THRESHOLD).sum() > 15:
            return frame[next_start - 2:next_start + 11, 0:130]
    return None


def _store_path():
    return data_utils.get_cache_dir() / 'screen_labels.pickle'


def _load():
    try:
        return load_pickle(_store_path())
    except (OSError, EOFError, ValueError):
        return []


def recall(mask, kind):
    """Value previously entered for this exact label (dict), or None"""
    if mask is None:
        return None
    for entry in _load():
        if entry['kind'] == kind and entry['mask'].shape == mask.shape \
                and np.count_nonzero(entry['mask'] != mask) <= MAX_DIFFERING_PIXELS:
            return entry
    return None


def remember(mask, kind, **values):
    """Store (or update) the value entered by the user for a label"""
    if mask is None:
        return
    entries = [e for e in _load() if not (e['kind'] == kind and e['mask'].shape == mask.shape
                                          and np.count_nonzero(e['mask'] != mask) <= MAX_DIFFERING_PIXELS)]
    entries.append(dict(kind=kind, mask=mask, **values))
    save_pickle(entries, _store_path())


def forget_all():
    """Delete all remembered labels"""
    path = _store_path()
    if path.exists():
        path.unlink()
