import webbrowser
from pathlib import Path

import numpy as np
from matplotlib.colors import LinearSegmentedColormap

from swepy.processing.io.json_io import load_json, save_json
from swepy.processing.io.pickle_io import save_pickle


# warnings.simplefilter('ignore')  # Fix NumPy issues.


def settings_io(temp=None):
    """Load settings from previous analyses"""
    dir_path = Path.cwd().parent / 'src' / 'cache'
    json_path = dir_path / 'settings.json'

    if temp:
        save_json(temp, json_path)
    else:
        if json_path.exists():
            temp = load_json(json_path)
            return temp
            # if param in temp:
            #     return temp[param]
        else:
            return {}


def get_settings(param):
    """Load a parameter settings from previous analyses"""
    temp = settings_io()
    if param in temp:
        return temp[param]
    else:
        return []


def delete_settings(param=None):
    """Delete a parameter settings or all settings from previous analyses
    Args:
        param: parameter for which settings should be deleted
    Returns: None
    """
    temp = settings_io()
    if param:
        temp[param].clear()
    else:
        for parameter in temp.values:
            parameter.clear()
    settings_io(temp)


def set_settings_paths():
    """Set path for json file containing settings"""
    dir_path = Path.cwd().parent / 'src' / 'cache'
    json_path = dir_path / 'settings.json'
    return dir_path, json_path


def save_path(path):
    """Add file path to a list of recent file paths, in a JSON file"""
    dir_path, json_path = set_settings_paths()
    if json_path.exists():
        temp = load_json(json_path)
        if path in temp['RECENT_PATHS']:
            return
    elif dir_path.exists():
        temp = dict()
        temp['RECENT_PATHS'] = []
    else:
        dir_path.mkdir()
        temp = dict()
        temp['RECENT_PATHS'] = []

    temp['RECENT_PATHS'].insert(0, path)
    if len(temp['RECENT_PATHS']) > 10:
        del temp['RECENT_PATHS'][-1]
    save_json(temp, json_path)


def save_usr_input(fhz, scale):
    """Save SWE frequency and max. scale from colour bar"""
    dir_path, json_path = set_settings_paths()
    if json_path.exists():
        temp = load_json(json_path)
        temp['SWE_PARAM'] = [fhz, scale]
        save_json(temp, json_path)


def save_roi_coords(roi_coords):
    """Save roi coordinates from 1st analysed file"""
    dir_path, json_path = set_settings_paths()
    if json_path.exists():
        temp = load_json(json_path)
        temp['ROI_COORDS'] = [roi_coords]
        save_json(temp, json_path)


def save_swe_var(swe_var):
    """Save SWE variable chosen by user"""
    dir_path, json_path = set_settings_paths()
    if json_path.exists():
        temp = load_json(json_path)
        temp['SWE_VAR'] = [swe_var]
        save_json(temp, json_path)


def save_cmap_source(cmap_loc):
    """Save cmap preference"""
    dir_path, json_path = set_settings_paths()
    if json_path.exists():
        temp = load_json(json_path)
        temp['CMAP_LOC'] = [cmap_loc]
        save_json(temp, json_path)


def save_sat_thresh(sat_thresh):
    """Save chosen saturation level"""
    dir_path, json_path = set_settings_paths()
    if json_path.exists():
        temp = load_json(json_path)
        temp['SAT_THRESH'] = [sat_thresh]
        save_json(temp, json_path)


def pickle_results(file_path, data):
    """Add analysis results to a pickle file
    Args:
        file_path (pathlib.PosixPath): path to analysed file
        data (dict): analysis results
    Returns: None
    """
    dir_path = Path.cwd().parent / 'src' / 'cache'
    pickle_path = dir_path / f'{file_path.stem}.pickle'

    save_pickle(data, pickle_path)


def closest_rgb(roi_rgb, color_profile_rgb):
    """
    Get indices of closest RGB values from scale to input RGB value
    Args:
        roi_rgb: region of interest array
        color_profile_rgb: color scale array
    Returns: array of scale_height indices
    """
    if len(roi_rgb.shape) == 3:
        roi_rgb = roi_rgb[:, :, np.newaxis, :]
    elif len(roi_rgb.shape) == 2:
        roi_rgb = roi_rgb[:, np.newaxis, :]
    else:
        raise ValueError(f'ROI shape: {roi_rgb.shape}. Must have 2 or 3 dimensions')
    assert len(color_profile_rgb.shape) == 2, 'Color scale array must be two-dimensional (H, 3)'
    rgb_distances = np.sqrt(np.sum((roi_rgb - color_profile_rgb) ** 2, axis=-1))
    # indices of closest corresponding RGB value in color bar
    min_indices = rgb_distances.argmin(-1)
    return min_indices


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
    src_path = Path.cwd().parent / 'src' / 'cache'
    paths = list(Path(src_path).rglob('*.pickle'))
    for path in paths:
        path.unlink()


def get_compression_status(ds_value):
    """Indicate if file is compressed based on 'LossyImageCompression' tag of DICOM file"""
    compression = 'yes' if int(ds_value) > 0 else 'no'
    return compression


def mean_lowest_stdev_subarray(arr, return_mask=False):
    """
    Finds the five successive values in the input array (or its row means if it's 2D) that result in the lowest
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
    min_n_frame = 5
    # Check if the input is a 2D array
    if arr.ndim == 2:
        if arr.shape[1] < 5:
            print(f'Video file contains less than 5 frames. Using only {arr.shape[1]} frames.')
            min_n_frame = arr.shape[1]

        # Compute the mean of each column to form a 1D array
        mean_array = np.nanmean(arr, axis=1)
    elif arr.ndim == 1:
        if len(arr) < 5:
            print(f'Video file contains less than 5 frames. Using only {len(arr)} frames.')
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
