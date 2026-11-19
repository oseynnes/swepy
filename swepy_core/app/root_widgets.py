import tkinter as tk
import tkinter.filedialog as fd
from pathlib import Path
from tkinter import ttk

from swepy_core.app import app_utils
from swepy_core.app.view_frames import apo_mode_enabled
from swepy_core.processing import data_utils


class MenuBar(tk.Menu):
    """Adding menu bar"""

    def __init__(self, parent):
        super().__init__(parent)

        self.app = parent
        self.path = None

        self.file_menu = tk.Menu(self, tearoff=0)
        self.add_cascade(label='File', underline=0, menu=self.file_menu)
        self.file_menu.add_command(label='Open...', command=lambda: self.app.paths_handler())

        self.history_submenu = tk.Menu(self.file_menu, tearoff=0)
        paths_list = data_utils.get_settings('RECENT_PATHS')
        for path in paths_list:
            self.history_submenu.add_command(label=path, command=lambda x=Path(path): self.app.reset(x))
        self.file_menu.add_cascade(label='Open recent', menu=self.history_submenu)

        self.file_menu.add_separator()
        self.file_menu.add_command(label='Export to CSV',
                                   command=lambda: self.app.output.save_panel.export('csv'))
        self.file_menu.add_command(label='Export to Excel',
                                   command=lambda: self.app.output.save_panel.export('xlsx'))
        self.file_menu.add_separator()
        self.file_menu.add_command(label='Clear all results', command=lambda: self.app.output.clear_results())
        self.file_menu.add_command(label='Clear history', command=lambda: self.delete_history())
        self.file_menu.add_command(label='Quit', command=self.app.destroy)

        self.edit_menu = tk.Menu(self, tearoff=0)
        self.add_cascade(label='Edit', underline=0, menu=self.edit_menu)
        self.edit_menu.add_command(label='Settings', command=lambda: self.open_settings())
        self.edit_menu.add_command(label='Forget remembered screen labels', command=self.forget_labels)

        self.help_menu = tk.Menu(self, tearoff=0)
        self.add_cascade(label='Help', underline=0, menu=self.help_menu)
        self.help_menu.add_command(label='Swepy README',
                                   command=lambda: data_utils.callback('https://tinyurl.com/swepy'))

    def forget_labels(self):
        """Delete values remembered for on-screen labels (scale, SWE frequency)"""
        from tkinter.messagebox import askyesno
        from swepy_core.processing import screen_labels
        if askyesno(title='Forget screen labels',
                    message='Forget the values remembered for on-screen scale and frequency labels? '
                            'They will have to be entered again.'):
            screen_labels.forget_all()

    def delete_history(self):
        self.history_submenu.delete(0, 'end')
        data_utils.delete_settings('RECENT_PATHS')

    def select_files(self):
        """Open file dialog and return list of selected paths (empty list if cancelled)"""
        # NB: no file type filter, so that DICOM files without extension are selectable
        initialdir = Path.home()
        recent_paths = data_utils.get_settings('RECENT_PATHS')
        if recent_paths and Path(recent_paths[0]).parent.exists():
            initialdir = Path(recent_paths[0]).parent
        paths = fd.askopenfilenames(initialdir=initialdir, title="Select DICOM file(s)")
        self.paths = [Path(path) for path in paths] if paths else []
        return self.paths

    def open_settings(self):
        """Instantiate Settings class"""
        settings = Settings(self)
        settings.grab_set()


class Settings(tk.Toplevel):
    """Set controls for app settings"""

    def __init__(self, parent):
        super().__init__(parent)

        self.menu = parent
        self.title('Settings')
        self.transient(parent.app)
        self.resizable(False, False)
        self.configure(padx=5, pady=5)
        self.protocol('WM_DELETE_WINDOW', self.close)
        self.last_valid_thresh = self.menu.app.data.sat_thresh_var.get()

        # user entry for % of max scale above which pixels will be quantified as saturated
        # implementation based on https://stackoverflow.com/a/43826075/13147488
        self.sat_frame = ttk.LabelFrame(self, text='Pixel saturation threshold (% of max scale)', padding=5)
        self.sat_frame.grid(row=0, column=0, sticky=tk.NSEW, padx=5, pady=5)
        self.usr_entry = ttk.Entry(self.sat_frame,
                                   width=6,
                                   textvariable=self.menu.app.data.sat_thresh_var,
                                   validate='key',
                                   validatecommand=(self.sat_frame.register(self.is_number), '%P'))
        self.usr_entry.grid(row=0, column=0, padx=(0, 10))
        self.current_value = ttk.Label(self.sat_frame, text=f'threshold: {self.menu.app.data.sat_thresh_var.get()}%')
        self.current_value.grid(row=0, column=1, sticky=tk.W)
        self.current_value.bind('<<UpdateNeeded>>', self.update_current_value)

        # user entry for origin of colour map to use for scaling
        # The external map is a standard colour scale ('Jet') from ElastoGUI programme
        self.cmap_frame = ttk.LabelFrame(self, text='Source of colour map', padding=5)
        self.cmap_frame.grid(row=1, column=0, sticky=tk.NSEW, padx=5, pady=5)
        self.cmap_labels = {'local_cmap': 'From image',
                            'external_cmap': 'Standard reference (experimental)'}
        grid_column = 0
        for key, label in self.cmap_labels.items():
            radio = ttk.Radiobutton(self.cmap_frame,
                                    text=label,
                                    value=key,
                                    variable=self.menu.app.view.cmap_loc_var,
                                    command=lambda: self.log_cmap_loc())

            radio.grid(column=grid_column, row=0, padx=(0, 10), pady=2)
            grid_column += 1

        # aponeurosis mode (hidden by default) and half-width of the band around the aponeurosis (standard: 1 mm)
        self.apo_frame = ttk.LabelFrame(self, text='Aponeurosis mode', padding=5)
        self.apo_frame.grid(row=2, column=0, sticky=tk.NSEW, padx=5, pady=5)
        self.apo_enabled = tk.BooleanVar(value=apo_mode_enabled())
        ttk.Checkbutton(self.apo_frame, text='Enable aponeurosis ROI shapes (see docs/aponeurosis_mode.md)',
                        variable=self.apo_enabled, command=self.toggle_apo_mode).grid(row=0, column=0, columnspan=3,
                                                                                    sticky=tk.W, pady=(0, 5))
        ttk.Label(self.apo_frame, text='Band half-width (mm):').grid(row=1, column=0, sticky=tk.W)
        current = data_utils.get_settings('APO_HALF_WIDTH_MM')
        self.apo_width = tk.StringVar(value=f'{float(current[0]):g}' if current else '1')
        ttk.Entry(self.apo_frame, width=6, textvariable=self.apo_width, validate='key',
                  validatecommand=(self.apo_frame.register(self.is_positive_number), '%P')).grid(row=1, column=1, padx=5)
        ttk.Label(self.apo_frame, text='standard: 1').grid(row=1, column=2, sticky=tk.W)
        self.apo_width.trace_add('write', lambda *_: self.save_apo_width())

        self.close_btn = ttk.Button(self, text='Close', command=self.close)
        self.close_btn.grid(column=0, row=3, sticky=tk.E, padx=5, pady=5)

        app_utils.center_window(self, parent.app)

    def is_number(self, value):
        if value == '':  # allow clearing the field while typing a new value
            return True
        try:
            int(value)
        except ValueError:
            return False
        self.last_valid_thresh = int(value)
        self.current_value.event_generate('<<UpdateNeeded>>', when='tail')
        data_utils.save_sat_thresh(value)
        return True

    @staticmethod
    def is_positive_number(value):
        if value == '':
            return True
        try:
            return float(value) > 0
        except ValueError:
            return False

    def toggle_apo_mode(self):
        """Save choice and show/hide the aponeurosis ROI shapes in the current view"""
        enabled = self.apo_enabled.get()
        data_utils.set_setting('APO_MODE', [enabled])
        view = self.menu.app.view
        was_apo = view.img_panel.is_apo()
        view.img_panel.set_apo_enabled(enabled)
        if enabled:
            # switch directly to the aponeurosis ROI, so the line is proposed without further steps
            view.img_panel.shape.set('apo_auto')
            data_utils.set_setting('ROI_SHAPE', ['apo_auto'])
            if view.ds:
                view.img_panel.reset_draw()
                view.on_shape_change()
        elif was_apo and view.ds:
            view.reset_rois()                # back to the default ROI (SWE box)

    def save_apo_width(self):
        if self.apo_width.get():
            data_utils.set_setting('APO_HALF_WIDTH_MM', [float(self.apo_width.get())])

    def close(self):
        """Restore last valid threshold if the entry was left empty, then close window"""
        if self.usr_entry.get() == '':
            self.menu.app.data.sat_thresh_var.set(self.last_valid_thresh)
        self.destroy()

    def update_current_value(self, event):
        w = event.widget
        number = self.last_valid_thresh
        w['text'] = f'threshold: {number}%'

    def log_cmap_loc(self):
        data_utils.save_cmap_source(self.menu.app.view.cmap_loc_var.get())
