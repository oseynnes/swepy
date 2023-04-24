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
             message='No elastography data were found in the current selection.'
                     ' Programme is closing.')


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
    if len(string_var.get()) == 0:
        value = None
    elif var_type(string_var.get()) >= 0:
        value = var_type(string_var.get())
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


def set_win_geometry(container, width, height):
    """Set window position relative to screen size"""
    screen_width = container.winfo_screenwidth()
    screen_height = container.winfo_screenheight()
    center_x = int(screen_width / 2 - width / 2)
    center_y = int(screen_height / 3 - height / 3)
    container.geometry(f'{width}x{height}+{center_x}+{center_y}')
