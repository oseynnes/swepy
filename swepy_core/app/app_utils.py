import sys
from tkinter import font as tkfont
from tkinter import ttk
from tkinter.messagebox import showinfo, showerror


def warn_no_video():
    showinfo(title='No video',
             message='Please load a DICOM file first')


def warn_wrong_entry():
    showerror(title='Wrong input',
              message='Please inform the frequency and scale fields with a number')


def warn_no_selection():
    showinfo(title='No Selection',
             message='Please select at least one file in the list')


def warn_empty_cache():
    showinfo(title='No previous results',
             message='The list of previously analysed files is empty')


def warn_no_swe_data():
    showinfo(title='No SWE data',
             message='No elastography data were found in the current selection.\n\n'
                     'Check that the ROI is placed over the coloured SWE map '
                     '(or use "Reset ROI"), then click "Analyse" again.')


def log_entry(name, string_var, ttk_table, row_id, var_type=float):
    """Save entry from tkinter entry to ttk.TreeView instance
    Args:
        name (str):
        string_var: variable to log in
        ttk_table: ttk.TreeView instance
        row_id (str): iid parameter of created row
        var_type (type): desired type of variable to log in
    Returns: variable inserted in ttk.TreeView instance
    """
    try:
        value = var_type(string_var.get()) if string_var.get().strip() else None
    except ValueError:  # entry is not a number of the expected type
        warn_wrong_entry()
        return
    if value is None:
        pass
    elif value >= 0:
        idx = 5 if isinstance(value, int) else 4  # with 4 pre-existing rows (0:3)
    else:
        warn_wrong_entry()
        return
    if value:
        if row_id in ttk_table.get_children():
            ttk_table.delete(row_id)
        ttk_table.insert(parent='',
                         index=idx,
                         iid=row_id,
                         values=(name, value))
    string_var.set('')
    return value


def enable_windows_dpi_awareness():
    """Make text and images sharp on Windows screens with display scaling (125%, 150%...).

    Without this, Windows stretches the whole window as a bitmap, which makes it blurry and
    often larger than the screen. Must be called before the Tk root window is created.
    """
    if not sys.platform.startswith('win'):
        return
    try:
        import ctypes
        try:
            ctypes.windll.shcore.SetProcessDpiAwareness(1)  # Windows 8.1 and later
        except (AttributeError, OSError):
            ctypes.windll.user32.SetProcessDPIAware()  # older Windows versions
    except Exception:  # never prevent the app from starting
        pass


def get_ui_scale(widget):
    """Return display scaling factor relative to a standard 96 DPI screen (macOS scales by itself)"""
    if sys.platform == 'darwin':
        return 1.0
    return max(1.0, widget.winfo_fpixels('1i') / 96)


def text_width(text, padding=20):
    """Width in pixels needed to display a text with the default font"""
    return tkfont.nametofont('TkDefaultFont').measure(text) + padding


def configure_style(root):
    """Adjust ttk style so the interface looks consistent across platforms and display scalings"""
    style = ttk.Style(root)
    if sys.platform.startswith('linux') and 'clam' in style.theme_names():
        style.theme_use('clam')  # the default Linux theme looks dated
    # Treeview rows do not grow with the font size on scaled displays (text gets clipped otherwise)
    linespace = tkfont.nametofont('TkDefaultFont').metrics('linespace')
    style.configure('Treeview', rowheight=int(linespace * 1.4))


def set_win_geometry(container, width, height):
    """Set window size and position relative to screen size, never exceeding the screen"""
    screen_width = container.winfo_screenwidth()
    screen_height = container.winfo_screenheight()
    width = min(width, int(screen_width * .95))
    height = min(height, int(screen_height * .88))  # leave room for task bar / dock
    center_x = max(0, int(screen_width / 2 - width / 2))
    center_y = max(0, int(screen_height / 3 - height / 3))
    container.geometry(f'{width}x{height}+{center_x}+{center_y}')
    container.minsize(min(800, width), min(500, height))


def center_window(window, parent):
    """Center a pop-up window over its parent window"""
    window.update_idletasks()
    x = parent.winfo_rootx() + (parent.winfo_width() - window.winfo_reqwidth()) // 2
    y = parent.winfo_rooty() + (parent.winfo_height() - window.winfo_reqheight()) // 3
    window.geometry(f'+{max(0, x)}+{max(0, y)}')
