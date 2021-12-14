import json
from pathlib import Path
from tkinter.messagebox import showinfo, showerror
import tkinter as tk
import numpy as np


def warn_no_video():
    showinfo(title='No video', message='Please load a Dicom file first')


def warn_wrong_entry():
    showerror(title='Wrong input',
              message='Please inform both the frequency and scale fields with a number')


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


def fetch_recent_paths():
    """fetch list of recent dicom file paths"""
    dir_path = Path.cwd() / 'src'
    json_path = dir_path / 'temp.json'

    if json_path.exists():
        temp = load_json(json_path)
        return temp['RECENT_PATHS']
    else:
        return []


def save_path(path):  # TODO: feed paths list to 'open recent' recent command of app menu
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


def log_entry(name, string_var, ttk_table, row, var_type=float):
    """Save entry from tkinter entry to ttk.TreeView instance"""
    try:
        var_type(string_var.get())
    except ValueError:
        warn_wrong_entry()
        return

    if row in ttk_table.get_children():
        ttk_table.delete(row)
    ttk_table.insert(parent='',
                     index=tk.END,
                     iid=row,
                     values=(name, var_type(string_var.get())))
    return var_type(string_var.get())


def closest_rgb(roi_rgb, color_profile_rgb):
    """
    Return indices of closest RGB values from scale to input RGB value
    :param roi_rgb: region of interest array
    :param color_profile_rgb: color scale array
    :return: array of scale_height indices
    """
    if len(roi_rgb.shape) == 3:
        roi_rgb = roi_rgb[np.newaxis, :, :, np.newaxis, :]
    elif len(roi_rgb.shape) == 4:
        roi_rgb = roi_rgb[:, :, :, np.newaxis, :]
    else:
        print(f'roi_rgb shape: {roi_rgb.shape}')
        raise ValueError('The ROI array must have 3 or 4 dimensions')
    # assert len(roi_rgb.shape) == 3, 'ROI array must be three-dimensional (H, W, 3)'
    assert len(color_profile_rgb.shape) == 2, 'Color scale array must be two-dimensional (H, 3)'
    rgb_distances = np.sqrt(np.sum((roi_rgb - color_profile_rgb) ** 2, axis=-1))
    # indices of closest corresponding RGB value in color bar
    min_indices = rgb_distances.argmin(-1)
    return min_indices
