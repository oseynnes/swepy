import json
import math
import pickle
import tkinter as tk
from pathlib import Path
from tkinter.messagebox import showinfo, showerror

import numpy as np


def warn_no_video():
    showinfo(title='No video', message='Please load a Dicom file first')


def warn_wrong_entry():
    showerror(title='Wrong input',
              message='Please inform the frequency and scale fields with a number')


def set_win_geometry(container, width, height):
    screen_width = container.winfo_screenwidth()
    screen_height = container.winfo_screenheight()
    center_x = int(screen_width / 2 - width / 2)
    center_y = int(screen_height / 3 - height / 3)
    container.geometry(f'{width}x{height}+{center_x}+{center_y}')


def load_json(path):
    """Return a content object for a JSON file"""
    with open(path, 'r') as file:
        return json.load(file)


def save_json(content, path):
    """save a content object in a JSON file"""
    with open(path, 'w') as file:
        json.dump(content, file)


def load_pickle(path):
    """Return a content object from a pickle file"""
    with open(path, 'rb') as handle:
        return pickle.load(handle)


def save_pickle(content, path):
    """Pickle a content object"""
    with open(path, 'wb') as handle:
        pickle.dump(content, handle, protocol=pickle.HIGHEST_PROTOCOL)


def load_settings(param):
    """Load settings from previous analyses"""
    dir_path = Path.cwd() / 'src'
    json_path = dir_path / 'temp.json'

    if json_path.exists():
        temp = load_json(json_path)
        if param in temp:
            return temp[param]
    else:
        return []


def save_path(path):
    """Add file path to a list of recent file paths, in a JSON file"""
    dir_path = Path.cwd() / 'src'
    json_path = dir_path / 'temp.json'

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
    dir_path = Path.cwd() / 'src'
    json_path = dir_path / 'temp.json'

    if json_path.exists():
        temp = load_json(json_path)
        temp['SWE_PARAM'] = [fhz, scale]
        save_json(temp, json_path)


def pickle_results(file_path, data):
    """Add analysis results to a JSON file
    Args:
        file_path (pathlib.PosixPath): path to analysed file
        data (dict): analysis results
    Returns: None
    """
    dir_path = Path.cwd() / 'src'
    pickle_path = dir_path / f'{file_path.name}.pickle'

    temp = {str(file_path): data}
    save_pickle(temp, pickle_path)


def log_entry(name, string_var, ttk_table, row, var_type=float):
    """Save entry from tkinter entry to ttk.TreeView instance"""
    if len(string_var.get()) == 0:
        value = None
    elif var_type(string_var.get()) >= 0:
        value = var_type(string_var.get())
        idx = 5 if isinstance(value, int) else 4  # with 4 pre-existing rows (0:3)
    else:
        print(f'{name}: {string_var.get()}, {type(string_var.get())}')
        warn_wrong_entry()
        return
    if value:
        if row in ttk_table.get_children():
            ttk_table.delete(row)
        ttk_table.insert(parent='',
                         index=idx,
                         iid=row,
                         values=(name, value))
    string_var.set('')
    return value


def closest_rgb(roi_rgb, color_profile_rgb):
    """
    Get indices of closest RGB values from scale to input RGB value
    Args:
        roi_rgb: region of interest array
        color_profile_rgb: color scale array
    Returns: array of scale_height indices
    """
    if len(roi_rgb.shape) == 3:
        roi_rgb = roi_rgb[np.newaxis, :, :, np.newaxis, :]
    elif len(roi_rgb.shape) == 4:
        roi_rgb = roi_rgb[:, :, :, np.newaxis, :]
    else:
        raise ValueError(f'ROI shape: {roi_rgb.shape}. Must have 3 or 4 dimensions')
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
        value (float): value
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
