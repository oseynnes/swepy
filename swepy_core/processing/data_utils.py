import os
import sys
import webbrowser
from pathlib import Path

import numpy as np
from matplotlib.colors import LinearSegmentedColormap

from swepy_core.processing.io.json_io import load_json, save_json
from swepy_core.processing.io.pickle_io import save_pickle

MAX_RECENT_PATHS = 10


def get_cache_dir():
    """Return the folder holding swepy settings and cached results, creating it if needed.

    The folder is user specific and independent of where swepy is installed or launched from:
        - Windows: %APPDATA%\\swepy
        - macOS: ~/Library/Application Support/swepy
        - Linux: $XDG_DATA_HOME/swepy (default ~/.local/share/swepy)
    It can be overridden with the SWEPY_HOME environment variable.
    """
    if os.environ.get('SWEPY_HOME'):
        dir_path = Path(os.environ['SWEPY_HOME'])
    elif sys.platform.startswith('win'):
        dir_path = Path(os.environ.get('APPDATA', Path.home() / 'AppData' / 'Roaming')) / 'swepy'
    elif sys.platform == 'darwin':
        dir_path = Path.home() / 'Library' / 'Application Support' / 'swepy'
    else:
        dir_path = Path(os.environ.get('XDG_DATA_HOME', Path.home() / '.local' / 'share')) / 'swepy'
    dir_path.mkdir(parents=True, exist_ok=True)
    return dir_path


def get_settings_path():
    """Return path of the JSON file containing user settings"""
    return get_cache_dir() / 'settings.json'


def get_cached_results_path(name):
    """Return path of the pickle file caching the results of an analysed file
    Args:
        name: name of the analysed file, with or without extension
    Returns: pathlib path to the pickle file
    """
    name = str(name)
    exact = get_cache_dir() / f'{name}.pickle'
    if exact.exists():
        return exact
    return get_cache_dir() / f'{Path(name).stem}.pickle'


def load_settings():
    """Load settings from previous analyses (empty dict if none or unreadable)"""
    json_path = get_settings_path()
    if not json_path.exists():
        return {}
    try:
        return load_json(json_path)
    except (OSError, ValueError):  # unreadable or corrupted settings file
        return {}


def save_settings(temp):
    """Save settings dictionary to JSON file"""
    save_json(temp, get_settings_path())


def set_setting(param, value):
    """Save a single parameter setting"""
    temp = load_settings()
    temp[param] = value
    save_settings(temp)


def get_settings(param):
    """Load a parameter settings from previous analyses"""
    return load_settings().get(param, [])


def delete_settings(param=None):
    """Delete a parameter settings or all settings from previous analyses
    Args:
        param: parameter for which settings should be deleted
    Returns: None
    """
    temp = load_settings()
    if param:
        temp[param] = []
    else:
        for key in temp:
            temp[key] = []
    save_settings(temp)


def save_path(path):
    """Add file path to a list of recent file paths, in a JSON file"""
    temp = load_settings()
    recent = temp.setdefault('RECENT_PATHS', [])
    if path in recent:
        return
    recent.insert(0, path)
    del recent[MAX_RECENT_PATHS:]
    save_settings(temp)


def save_usr_input(fhz, scale):
    """Save SWE frequency and max. scale from colour bar"""
    set_setting('SWE_PARAM', [fhz, scale])


def save_roi_coords(roi_coords):
    """Save roi coordinates from 1st analysed file"""
    set_setting('ROI_COORDS', [roi_coords])


def save_swe_var(swe_var):
    """Save SWE variable chosen by user"""
    set_setting('SWE_VAR', [swe_var])


def save_cmap_source(cmap_loc):
    """Save cmap preference"""
    set_setting('CMAP_LOC', [cmap_loc])


def save_sat_thresh(sat_thresh):
    """Save chosen saturation level"""
    set_setting('SAT_THRESH', [sat_thresh])


def pickle_results(file_path, data):
    """Add analysis results to a pickle file
    Args:
        file_path (pathlib.Path): path to analysed file
        data (dict): analysis results
    Returns: None
    """
    pickle_path = get_cache_dir() / f'{file_path.stem}.pickle'
    save_pickle(data, pickle_path)


def find_refresh_timing(changes, nominal_period, spike_ratio=2.5, min_hit_rate=0.3):
    """Find when SWE maps are refreshed in a cine loop.

    Within the SWE box, consecutive frames are identical (apart from compression noise) until the
    SWE map is refreshed, which produces a spike in frame-to-frame change. Candidate periods
    (in frames) close to the nominal period, and phases, are scored by the fraction of their
    predicted refresh positions falling on a spike. Refreshes that leave the map unchanged
    (e.g. uniform maps) produce no spike, hence the tolerance on that fraction.

    Args:
        changes: 1D array, changes[i] = mean absolute pixel change between frames i and i+1
        nominal_period (float): expected refresh period in frames (B-mode frame rate / SWE frequency)
        spike_ratio (float): a change larger than spike_ratio x median change counts as a spike
        min_hit_rate (float): minimal fraction of predicted refreshes that must fall on spikes
    Returns: (period, first_refresh_frame), or None if no clear periodic refresh is found
        (e.g. static or uniform SWE map)
    """
    changes = np.asarray(changes, dtype=float).copy()
    if len(changes) < 4:
        return None
    changes[0] = np.median(changes)  # change between frames 0 and 1 is unreliable in some files
    noise = np.median(changes)
    spikes = changes > spike_ratio * max(noise, 1e-6)
    if not spikes.any():
        return None

    # actual refresh periods are within a few % of nominal ones (e.g. 13 vs 12.5 frames);
    # the search range excludes multiples of the period, which would skip maps
    lo = max(2, int(np.floor(nominal_period * .75)))
    hi = min(int(np.ceil(nominal_period * 1.33)), len(changes) // 2)
    scores = {}  # period -> (hit rate, mean change at hits, phase)
    for period in range(lo, hi + 1):
        best = None
        for phase in range(period):
            hits = spikes[phase::period]
            candidate = (hits.mean(), changes[phase::period].mean(), phase)
            if best is None or candidate[:2] > best[:2]:
                best = candidate
        scores[period] = best
    if not scores:
        return None
    period = max(scores, key=lambda p: scores[p][:2])
    if scores[period][0] < min_hit_rate:
        return None
    return period, scores[period][2] + 1


def select_swe_frames(n_frames, period, first_refresh):
    """Return index of one frame per SWE map: the middle frame of each refresh interval.

    Frame 0 is ignored; maps partially visible at the start and end of the clip are included.
    """
    refreshes = list(range(first_refresh, n_frames, period))
    bounds = [1] + [r for r in refreshes if r > 1] + [n_frames]
    return np.array([(start + stop - 1) // 2 for start, stop in zip(bounds[:-1], bounds[1:]) if stop > start])


def closest_rgb(roi_rgb, color_profile_rgb):
    """
    Get indices of closest RGB values from scale to input RGB value
    Args:
        roi_rgb: region of interest array
        color_profile_rgb: color scale array
    Returns: array of scale_height indices
    """
    if roi_rgb.ndim not in (2, 3, 4):
        raise ValueError(f'ROI shape: {roi_rgb.shape}. Must have 2 to 4 dimensions (..., 3)')
    assert len(color_profile_rgb.shape) == 2, 'Color scale array must be two-dimensional (H, 3)'
    # Images contain few distinct colours: match each distinct colour once (much faster, less memory)
    colours, inverse = np.unique(roi_rgb.reshape(-1, roi_rgb.shape[-1]), axis=0, return_inverse=True)
    rgb_distances = np.sqrt(np.sum((colours[:, np.newaxis, :] - color_profile_rgb) ** 2, axis=-1))
    # indices of closest corresponding RGB value in color bar
    min_indices = rgb_distances.argmin(-1)
    return min_indices[inverse.ravel()].reshape(roi_rgb.shape[:-1])


def colour_positions(roi_rgb, color_profile_rgb, chunk=4096):
    """Continuous position of each colour along the colour bar (0 = top row, n-1 = bottom row)

    The colour bar is treated as a path through RGB space joining consecutive bar colours, and each
    colour is projected onto the closest point of this path. Scanners draw SWE maps with many more
    colours than the bar has rows (e.g. 1370 vs 110 colours in an uncompressed Mach30 export), lying
    between bar colours: this recovers values between bar rows instead of rounding them to the nearest row.
    Args:
        roi_rgb: array of colours (..., 3)
        color_profile_rgb: colour bar array (n rows, 3), top row first
        chunk (int): number of distinct colours processed at once (limits memory use)
    Returns: array of float positions, shape roi_rgb.shape[:-1]
    """
    profile = np.asarray(color_profile_rgb, dtype=float)
    assert profile.ndim == 2, 'Color scale array must be two-dimensional (H, 3)'
    colours, inverse = np.unique(roi_rgb.reshape(-1, roi_rgb.shape[-1]), axis=0, return_inverse=True)
    starts, segments = profile[:-1], np.diff(profile, axis=0)
    seg_len2 = np.maximum((segments ** 2).sum(-1), 1e-12)
    positions = np.empty(len(colours))
    for first in range(0, len(colours), chunk):
        c = colours[first:first + chunk, np.newaxis, :].astype(float)
        t = np.clip(((c - starts) * segments).sum(-1) / seg_len2, 0, 1)  # projection on each segment
        dist = ((starts + t[..., np.newaxis] * segments - c) ** 2).sum(-1)
        best = dist.argmin(1)
        positions[first:first + chunk] = best + t[np.arange(len(best)), best]
    return positions[inverse.ravel()].reshape(roi_rgb.shape[:-1])


def convert_shear_m(mu, to_unit, decimals=4, rho=1000):
    """
    convert shear modulus to shear wave velocity or Young's modulus
    Args:
        mu (float): shear modulus (kPa) to convert
        to_unit (str): variable to convert to. "velocity" or "youngs_m"
        decimals (int): number of decimals to round to
        rho (float): tissue density. Default: 1000 kg m-3 for skeletal muscle
    Returns: target conversion
    """
    assert (to_unit in {'velocity', 'youngs_m'}), \
        "'to_unit' can only be 'velocity' or 'youngs_m'"
    velocity = np.round(np.sqrt(mu * 1000 / rho), decimals)
    epsilon = np.round(3 * mu, decimals)
    return velocity if to_unit == 'velocity' else epsilon


def convert_youngs_m(epsilon, to_unit, decimals=4, rho=1000):
    """convert Young's modulus to shear wave velocity or shear modulus
    Args:
        epsilon (float): Young's modulus (kPa) to convert
        to_unit (str): variable to convert to. "velocity" or "shear_m"
        decimals (int): number of decimals to round to
        rho (float): tissue density. Default: 1000 kg m-3 for skeletal muscle
    Returns: target conversion
    """
    assert (to_unit in {'velocity', 'shear_m'}), \
        "'to_unit' can only be 'velocity' or 'shear_m'"
    mu = np.round(epsilon / 3, decimals)
    velocity = np.round(np.sqrt(mu * 1000 / rho), decimals)
    return velocity if to_unit == 'velocity' else mu


def convert_velocity(velocity, to_unit, decimals=4, rho=1000):
    """convert shear wave velocity to shear modulus or Young's modulus
    Args:
        velocity (float): shear wave velocity (m/s) to convert
        to_unit (str): variable to convert to. "shear_m" or "youngs_m"
        decimals (int): number of decimals to round to
        rho (float): tissue density. Default: 1000 kg m-3 for skeletal muscle
    Returns: target conversion
    """
    assert (to_unit in {'shear_m', 'youngs_m'}), \
        "'to_unit' can only be 'shear_m' or 'youngs_m'"
    mu = np.round((rho * velocity ** 2) / 1000, decimals)
    epsilon = np.round(3 * mu, decimals)
    return mu if to_unit == 'shear_m' else epsilon


def convert_swe(value, swe_var, to_unit, decimals=4, rho=1000):
    """convert variable measured from shear wave elastography
    Args:
        value: value
        swe_var (str): variable to convert from. "velocity, "shear_m" or "youngs_m"
        to_unit (str): variable to convert to. "velocity, "shear_m" or "youngs_m"
        decimals (int): number of decimals to round to
        rho (float): tissue density. Default: 1000 kg m-3 for skeletal muscle
    Returns: target conversion
    """
    swe_vars = ('velocity', 'shear_m', 'youngs_m')
    functions = (convert_velocity, convert_shear_m, convert_youngs_m)
    f = dict(zip(swe_vars, functions))
    assert (swe_var in swe_vars), "'swe_var' can only be 'velocity', 'shear_m' or 'youngs_m'"
    assert (to_unit in swe_vars), "'to_unit' can only be 'velocity', 'shear_m' or 'youngs_m'"
    return f[swe_var](value, to_unit, decimals, rho)


def get_area(coords):
    """Calculate rectangular area
    Args:
        coords (dict): roi coordinates
    Returns: area in pixel
    """
    l1 = coords['x1'] - coords['x0']
    l2 = coords['y1'] - coords['y0']
    return l1 * l2


def callback(url):
    """open webpage"""
    webbrowser.open_new(url)


def filter_nans(lists):
    """Filter nan values out of nested lists
    Args:
        lists: nested lists
    Returns: nested lists without nan values
    """
    filtered = [list(filter(lambda x: x == x, inner_list)) for inner_list in lists]
    return filtered


def rect_polygonise(rect_coord):
    """Generate a list of coordinates for all points of a rectangular selection
    Args:
        rect_coord: list of 2 (x, y) coordinates to define rectangle
    Returns: list of all 4 (x, y) coordinates
    """
    x0 = rect_coord[0][0]
    y0 = rect_coord[0][1]
    x1 = rect_coord[1][0]
    y1 = rect_coord[1][1]
    return [(x0, y0), (x1, y0), (x1, y1), (x0, y1)]


def stretch_colormap(cmap, n=255):
    """Interpolate color map to n colors

    Args:
        cmap: color map to interpolate
        n: number of colours in the interpolated color map

    Returns:
        the interpolated color map

    Notes:
        adapted from https://stackoverflow.com/a/67985432/13147488
    """
    cmap_object = LinearSegmentedColormap.from_list('', np.array(cmap) / 255, 256)
    cmap_interpolated = (cmap_object(np.linspace(0, 1, n)) * 255).astype(np.uint8)
    return cmap_interpolated[:, :3]


def format_str_datetime(dicom_meta):
    """Format string containing date and time information for display
    Args:
        dicom_meta: pydicom object (dictionary like) metadata from dicom file

    Returns: formated string as 'dd/mm/yyyy hh:mm:ss'

    """
    s = dicom_meta.get('AcquisitionDateTime', '(missing)')
    elts = s[0:4], s[4:6], s[6:8], s[8:10], s[10:12], s[12:14]
    date = '/'.join(elts[0:3][::-1])
    time = ':'.join(elts[3:6])
    return ' '.join((date, time))


def clear_pickle():
    """Delete pickle files from cache directory"""
    for path in get_cache_dir().glob('*.pickle'):
        path.unlink()


def get_compression_status(ds_value):
    """Indicate if file is compressed based on 'LossyImageCompression' tag of DICOM file"""
    compression = 'yes' if int(ds_value) > 0 else 'no'
    return compression


def mean_lowest_stdev_subarray(arr, return_mask=False, n=5):
    """
    Finds the n (default 5) successive values in the input array (or its row means if it's 2D) that result in the lowest
    standard deviation, calculates their average, and returns a boolean mask for the selected values.

    Args:
        arr (numpy.ndarray): A 1D or 2D numpy array of values.

    Returns:
        tuple: A tuple containing:
            - float: The average of the five successive values with the lowest standard deviation.
            - numpy.ndarray: A 1D boolean mask array indicating the values that are kept.

    Raises:
        ValueError: If the input is a 1D array with fewer than 5 elements, or any row in a 2D array has fewer than 5 elements.
    """
    min_n_frame = n
    # Check if the input is a 2D array
    if arr.ndim == 2:
        if arr.shape[0] < n:  # rows are frames
            print(f'Fewer than {n} values available. Using only {arr.shape[0]} frames.')
            min_n_frame = arr.shape[0]

        # Compute the mean of each column to form a 1D array
        mean_array = np.nanmean(arr, axis=1)
    elif arr.ndim == 1:
        if len(arr) < n:
            print(f'Fewer than {n} values available. Using only {len(arr)} frames.')
            min_n_frame = len(arr)

        mean_array = arr
    else:
        raise ValueError("Input must be a 1D or 2D numpy array")

    # Initialize variables to store the minimum standard deviation and its corresponding subarray
    min_std_dev = float('inf')
    best_start_index = None

    # Iterate over possible starting indices for subarrays of length 5 or less
    for i in range(len(mean_array) - (min_n_frame - 1)):
        subarray = mean_array[i:i + min_n_frame]  # Get a subarray of consecutive elements
        std_dev = np.std(subarray)  # Calculate the standard deviation of the subarray

        # Check if the current standard deviation is the smallest found so far
        if std_dev < min_std_dev:
            min_std_dev = std_dev
            best_start_index = i

    # Create a boolean mask for the selected values
    mask = np.zeros(len(mean_array), dtype=bool)
    mask[best_start_index:best_start_index + min_n_frame] = True

    # Calculate the average of the subarray with the lowest standard deviation
    average_of_best_subarray = np.mean(mean_array[best_start_index:best_start_index + min_n_frame])

    if return_mask:
        return average_of_best_subarray, mask
    else:
        return average_of_best_subarray
