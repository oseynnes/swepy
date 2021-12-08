import json
from pathlib import Path
from tkinter.messagebox import showinfo, showerror


def warn_no_video():
    showinfo(title='No video', message='Please load a Dicom file first')


def warn_no_number():
    showerror(title='Wrong input', message='Please enter a number')


def set_win_geometry(container, width, height):
    screen_width = container.winfo_screenwidth()
    screen_height = container.winfo_screenheight()
    center_x = int(screen_width / 2 - width / 2)
    center_y = int(screen_height / 3 - height / 3)
    container.geometry(f'{width}x{height}+{center_x}+{center_y}')


def add_to_paths(path):  # TODO: feed paths list to 'open recent' recent command of app menu
    """Add file path to a list of recent file paths, in a JSON file"""
    dir_path = Path.cwd() / 'src'
    json_path = dir_path / 'paths.json'

    if json_path.exists():
        with open(json_path, 'r') as file:
            paths = json.load(file)
            if path in paths['recent']:
                return
    elif dir_path.exists():
        paths = dict()
        paths['recent'] = []
    else:
        dir_path.mkdir()
        paths = dict()
        paths['recent'] = []

    paths['recent'].insert(0, path)
    if len(paths['recent']) > 10:
        del paths['recent'][-1]
    with open(json_path, 'w') as file:
        json.dump(paths, file)


def fetch_recent_paths():
    """fetch list of recent dicom file paths"""
    dir_path = Path.cwd() / 'src'
    json_path = dir_path / 'paths.json'

    if json_path.exists():
        with open(json_path, 'r') as file:
            paths = json.load(file)
            return list(paths.values())[0]
    else:
        return []
