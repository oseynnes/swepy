import tkinter as tk
from tkinter import ttk

from PIL import ImageTk, Image

from swepy_core.app.app_utils import text_width, warn_no_video
from swepy_core.processing import data_utils

ROI_SHAPES = {'rectangle': 'Rectangle', 'polygon': 'Polygon',
              'apo_auto': 'Aponeurosis', 'apo_manual': 'Apo (manual)'}
APO_SHAPES = ('apo_auto', 'apo_manual')


def apo_mode_enabled():
    """Whether the aponeurosis mode is enabled (Edit > Settings; disabled by default)"""
    value = data_utils.get_settings('APO_MODE')
    return bool(value and value[0])


class TopPanel(ttk.Frame):
    """Panel of GUI displaying file name"""

    def __init__(self, parent):
        super().__init__(parent)
        options = {'fill': 'x', 'padx': 5, 'pady': 5}

        self.grid(row=0, column=1, sticky=tk.EW)

        self.img_name = ttk.Label(self, anchor=tk.CENTER, text='No file loaded (File > Open...)')
        self.img_name.pack(**options)


class LeftPanel(ttk.Frame):
    """Panel of GUI displaying app related to file opening and analysis"""

    def __init__(self, parent):
        super().__init__(parent, padding=(5, 0, 0, 5))

        self.view = parent

        self.grid(row=1, column=0, sticky=tk.NSEW)
        self.columnconfigure(0, weight=1)
        self.rowconfigure(2, weight=1)

        self.input_frame = ttk.LabelFrame(self, text='User input', padding=5)
        self.input_frame.grid(row=0, column=0, sticky=tk.EW, pady=(0, 5))
        self.input_frame.columnconfigure(1, weight=1)

        fhz_label = ttk.Label(self.input_frame, text='SWE fhz:')
        fhz_label.grid(column=0, row=0, sticky=tk.W, padx=5, pady=2)
        self.usr_fhz = tk.StringVar()
        self.fhz_entry = ttk.Entry(self.input_frame, width=7, textvariable=self.usr_fhz)
        self.fhz_entry.grid(column=1, row=0, sticky=tk.E, padx=5, pady=2)

        scale_label = ttk.Label(self.input_frame, text='max. scale:')
        scale_label.grid(column=0, row=1, sticky=tk.W, padx=5, pady=2)
        self.usr_scale = tk.StringVar()
        self.scale_entry = ttk.Entry(self.input_frame, width=7, textvariable=self.usr_scale)
        self.scale_entry.grid(column=1, row=1, sticky=tk.E, padx=5, pady=2)

        self.usr_params = data_utils.get_settings('SWE_PARAM')
        if self.usr_params:
            self.usr_fhz.set(self.usr_params[0])
            self.usr_scale.set(self.usr_params[1])

        self.enter_btn = ttk.Button(self.input_frame, text='Set values')
        self.enter_btn.grid(column=1, row=2, sticky=tk.E, padx=5, pady=5)

        # enlarged on-screen labels, to read values easily, and status of the entries
        self.label_frame = ttk.Frame(self.input_frame)
        self.label_frame.grid(column=0, row=3, columnspan=2, sticky=tk.W, padx=5)
        self.fhz_crop = ttk.Label(self.label_frame)
        self.fhz_crop.grid(row=0, column=0, sticky=tk.W)
        self.scale_crop = ttk.Label(self.label_frame)
        self.scale_crop.grid(row=1, column=0, sticky=tk.W)
        self.crop_images = []
        self.entry_status = ttk.Label(self.input_frame, text='', wraplength=text_width('x' * 34))
        self.entry_status.grid(column=0, row=4, columnspan=2, sticky=tk.W, padx=5)

        self.swe_var_frame = ttk.LabelFrame(self, text='Scale variable', padding=5)
        self.swe_var_frame.grid(row=1, column=0, sticky=tk.EW, pady=(0, 5))
        # NB: a scale in kPa can show Young's (E) or shear (\u03BC) modulus, depending on scanner settings
        self.variable_labels = {'velocity': 'V (m/s)',
                                'shear_m': '\u03BC (kPa)',
                                'youngs_m': "E (kPa)"}
        grid_column = 0
        for key, label in self.variable_labels.items():
            radio = ttk.Radiobutton(self.swe_var_frame,
                                    text=label,
                                    value=key,
                                    variable=self.view.swe_var,
                                    command=lambda: self.log_swe_var())
            radio.grid(column=grid_column, row=0, padx=(0, 10), pady=2)
            grid_column += 1

        self.tree_frame = ttk.Frame(self)
        self.tree_frame.grid(row=2, column=0, sticky=tk.NSEW)
        self.tree_frame.columnconfigure(0, weight=1)
        self.tree_frame.rowconfigure(0, weight=1)
        columns = ('dcm_property', 'value')
        self.var_names = ('Scan ID',
                          'Date/time',
                          'No. of frames',
                          'No. of rows',
                          'No. of columns',
                          'Lossy compression',
                          'B mode Fhz')
        self.values = (None,)
        # 7 rows of file properties + 2 rows of user input
        self.tv = ttk.Treeview(self.tree_frame, columns=columns, show='headings', height=9)
        self.tv.heading('dcm_property', text="File properties", anchor=tk.W)
        self.tv.column('dcm_property', width=text_width('Lossy compression'), stretch=False)
        self.tv.heading("value", text="Value", anchor=tk.W)
        self.tv.column('value', width=text_width('00/00/0000 00:00:00'), stretch=True)
        self.tv.grid(row=0, column=0, columnspan=3, sticky=tk.NSEW)

        self.reset_roi_btn = ttk.Button(self.tree_frame, text="Reset ROI")
        self.reset_roi_btn.grid(row=1, column=0, sticky=tk.W, pady=5)

        # shows decoded values over the whole SWE box, to place the ROI away from stiff structures
        self.value_map_btn = ttk.Button(self.tree_frame, text="Value map")
        self.value_map_btn.grid(row=1, column=1, padx=5, pady=5)

        self.analyse_btn = ttk.Button(self.tree_frame, text="Analyse")
        self.analyse_btn.grid(row=1, column=2, sticky=tk.E, pady=5)

    def show_label_crops(self, fhz_crop, scale_crop, zoom=2):
        """Display enlarged crops of the frequency and scale labels of the image"""
        self.crop_images = []
        for widget, crop in ((self.fhz_crop, fhz_crop), (self.scale_crop, scale_crop)):
            if crop is None or crop.size == 0:
                widget.config(image='')
                continue
            img = Image.fromarray(crop)
            img = ImageTk.PhotoImage(img.resize((img.width * zoom, img.height * zoom), Image.NEAREST))
            self.crop_images.append(img)  # keep a reference (tkinter does not)
            widget.config(image=img)

    def set_entry_status(self, text, colour):
        self.entry_status.config(text=text, foreground=colour)

    def log_swe_var(self):
        """Save last chosen SWE variable"""
        data_utils.save_swe_var(self.view.swe_var.get())


class ImgPanel(ttk.Frame):
    """Panel of GUI displaying images"""

    def __init__(self, parent):
        super().__init__(parent)

        self.view = parent

        # NB: images are displayed at their native size (1 image pixel = 1 canvas pixel),
        # because ROI coordinates drawn on the canvas are used directly as image indices.
        self.canvas = tk.Canvas(self, width=720, height=540, bg='black', cursor="cross")
        self.grid(row=1, column=1, sticky=tk.NSEW, padx=5, pady=(0, 5))

        self.n_frames = 0
        self.top_fov_coords = {'x0': 0,
                               'y0': 0,
                               'x1': int(self.canvas['width']),
                               'y1': int(self.canvas['height']) / 2}

        self.fov_y_offset = 225  # default for Mach30 top/bottom layout, replaced by DICOM value
        self.new_roi = tk.BooleanVar()
        self.new_roi.set(True)
        self.roi_coords = []
        self.polyg_top = self.polyg_down = None

        self.current_array = None
        self.img = None
        self.img_name = None

        # Video controls
        self.ctrl = DisplayControls(self)
        self.frame_label_var = tk.StringVar()

        # Choice of ROI shape (remembered between files)
        self.roi_frame = ttk.LabelFrame(self, text='ROI shape', labelanchor='w')
        self.shape = tk.StringVar()
        saved_shape = data_utils.get_settings('ROI_SHAPE')
        self.shape.set(saved_shape[0] if saved_shape and saved_shape[0] in ROI_SHAPES else 'rectangle')
        self.shape_radios = {}
        for column, (value, text) in enumerate(ROI_SHAPES.items()):
            radio = ttk.Radiobutton(self.roi_frame, text=text, value=value, variable=self.shape,
                                    command=self.on_shape_change)
            radio.grid(column=column, row=0, padx=5, pady=5)
            self.shape_radios[value] = radio

        # Aponeurosis mode: reference side and feedback on the detected line
        self.apo_frame = ttk.LabelFrame(self, text='Aponeurosis', padding=(5, 2))
        ttk.Label(self.apo_frame, text='Muscle reference:').grid(row=0, column=0, sticky=tk.W)
        self.apo_side = tk.IntVar(value=1)
        ttk.Radiobutton(self.apo_frame, text='below (UP)', value=1, variable=self.apo_side,
                        command=lambda: self.view.update_apo()).grid(row=0, column=1, padx=5)
        ttk.Radiobutton(self.apo_frame, text='above (LOW)', value=-1, variable=self.apo_side,
                        command=lambda: self.view.update_apo()).grid(row=0, column=2, padx=5)
        legend = ttk.Frame(self.apo_frame)
        legend.grid(row=1, column=0, columnspan=4, sticky=tk.W)
        ttk.Label(legend, text='Drawing:').pack(side=tk.LEFT)
        ttk.Label(legend, text='  — aponeurosis line', foreground='goldenrod').pack(side=tk.LEFT)
        ttk.Label(legend, text='  ▭ aponeurosis ROI (result)', foreground='green').pack(side=tk.LEFT)
        ttk.Label(legend, text='  ┄ muscle reference', foreground='darkorange').pack(side=tk.LEFT)
        self.apo_status = ttk.Label(self.apo_frame, text='', foreground='grey')
        self.apo_status.grid(row=2, column=0, columnspan=4, sticky=tk.W)
        self.apo_result = None      # dict with band, reference and line coordinates, and line descriptors
        self.apo_points = []        # points clicked along the aponeurosis (manual line)
        self.apo_items = []         # canvas items of the aponeurosis drawing

        # Pack bottom widgets first: if the window is too small, the image gets cropped
        # rather than the controls disappearing
        self.apo_frame.pack(side=tk.BOTTOM, anchor=tk.W, fill=tk.X, pady=(2, 0))
        self.roi_frame.pack(side=tk.BOTTOM, anchor=tk.W, pady=(5, 0))
        self.apo_enabled = True
        self.ctrl.pack(side=tk.BOTTOM, fill=tk.X)
        self.canvas.pack(side=tk.TOP, anchor=tk.NW, fill=tk.BOTH, expand=True)
        self.set_apo_enabled(apo_mode_enabled())

    # Specific functions
    def is_apo(self):
        return self.shape.get() in APO_SHAPES

    def set_apo_enabled(self, enabled):
        """Show or hide the aponeurosis mode (ROI shapes and panel)"""
        if enabled == self.apo_enabled:
            return
        self.apo_enabled = enabled
        for value in APO_SHAPES:
            if enabled:
                self.shape_radios[value].grid()
            else:
                self.shape_radios[value].grid_remove()
        if enabled:
            self.apo_frame.pack(side=tk.BOTTOM, anchor=tk.W, fill=tk.X, pady=(2, 0), before=self.roi_frame)
        else:
            self.apo_frame.pack_forget()
            if self.is_apo():              # back to the standard ROI
                self.shape.set('rectangle')
                data_utils.set_setting('ROI_SHAPE', ['rectangle'])
                self.reset_draw()

    def on_shape_change(self):
        """Save ROI shape and start a new ROI of this shape"""
        data_utils.set_setting('ROI_SHAPE', [self.shape.get()])
        self.reset_draw()
        self.view.on_shape_change()

    def activate_draw(self):
        self.canvas.bind('<Button-1>', self.on_button_press)
        self.canvas.bind("<Double-1>", self.on_double_click)

    def to_top(self, x, y):
        """Image coordinates of a point in the top field of view (clicks can be in either view)"""
        in_top = self.top_fov_coords['y0'] <= y <= self.top_fov_coords['y1']
        return x, y if in_top else y - self.fov_y_offset

    def set_apo(self, result):
        """Use an aponeurosis band (and reference) as ROI, and draw it"""
        self.apo_result = result
        self.roi_coords = list(result['band']) if result else []
        self.new_roi.set(True)
        self.set_rois()

    def clear_apo(self):
        self.apo_result = None
        self.apo_points = []
        self.canvas.delete(*self.apo_items)
        self.apo_items = []

    def _draw_both(self, method, coords, **options):
        """Draw an item in the top field of view and its mirror in the bottom one"""
        flat = [v for point in coords for v in point]
        self.apo_items.append(method(flat, **options))
        self.apo_items.append(method([v + self.fov_y_offset if i % 2 else v for i, v in enumerate(flat)], **options))

    def draw_apo(self):
        self.canvas.delete(*self.apo_items)
        self.apo_items = []
        result = self.apo_result
        if result:
            if len(result['reference']) > 2:
                self._draw_both(self.canvas.create_polygon, result['reference'], fill='', outline='orange',
                                width=1, dash=(3, 2))
            if len(result['band']) > 2:
                self._draw_both(self.canvas.create_polygon, result['band'], fill='', outline='green', width=2)
            if len(result['line']) > 1:
                self._draw_both(self.canvas.create_line, result['line'], fill='yellow', width=1)
        elif self.apo_points:
            for x, y in self.apo_points:
                self._draw_both(self.canvas.create_oval, [(x - 2, y - 2), (x + 2, y + 2)], fill='yellow', outline='yellow')
            if len(self.apo_points) > 1:
                self._draw_both(self.canvas.create_line, self.apo_points, fill='yellow', width=1)

    def activate_slider(self, n_frames):
        self.n_frames = n_frames
        self.ctrl.frame_label.config(text=f'{self.ctrl.current_frame + 1}/{n_frames}')
        self.ctrl.slider.config(to=self.n_frames)
        self.ctrl.slider.config(state='normal')  # activate slider

    def clear_coords(self):
        self.roi_coords = []

    def isin_top_fov(self):
        """Check if ROI is drawn in top or bottom field of view"""
        x_start, y_start = self.roi_coords[0]
        in_x_bounds = self.top_fov_coords['x0'] <= x_start <= self.top_fov_coords['x1']
        in_y_bounds = self.top_fov_coords['y0'] <= y_start <= self.top_fov_coords['y1']
        return in_x_bounds and in_y_bounds

    def mirror_coords(self, coords=None):
        """Generate mirror coordinates of ROI in other field of view,
        when FoVs are in "top-bottom" configuration
        Args:
            coords: (x, y) coordinates for polygon points
        Returns: offset list of (x, y) coordinates
        """
        roi_coords = self.roi_coords if not coords else coords
        roi_offset = self.fov_y_offset if self.isin_top_fov() else -self.fov_y_offset
        if isinstance(roi_coords[0], tuple):
            m_coords = [(coord[0], coord[1] + roi_offset) for coord in roi_coords]
        elif isinstance(roi_coords[0], int):
            m_coords = [c if not i % 2 else c + roi_offset for i, c in enumerate(roi_coords)]
        else:
            raise Exception('Error due to format of ROI coordinates')
        return m_coords

    def reset_draw(self):
        self.clear_coords()
        self.clear_apo()
        self.canvas.delete(self.polyg_top, self.polyg_down)
        self.activate_draw()

    def get_top_coords(self):
        """Set coordinates of ROI in top field of view as the main ones"""
        self.roi_coords = self.roi_coords if self.isin_top_fov() else self.mirror_coords()
        self.new_roi.set(True)

    def set_rois(self):
        if self.is_apo():
            self.draw_apo()
            return
        # NB: a rectangle needs 2 corners (only 1 exists while the user is drawing it)
        if self.shape.get() == 'rectangle' and len(self.roi_coords) < 2:
            return
        if self.roi_coords:
            self.draw_rois()

    def draw_rois(self):
        self.canvas.delete(self.polyg_top, self.polyg_down)
        if self.shape.get() == 'rectangle':
            self.draw_rectangle()
        elif self.shape.get() == 'polygon':
            self.draw_polygon()

    def draw_rectangle(self):
        self.polyg_top = self.canvas.create_rectangle(self.roi_coords,
                                                      outline='green',
                                                      width=2)
        self.polyg_down = self.canvas.create_rectangle(*self.mirror_coords(),
                                                       outline='green',
                                                       width=2)
        self.get_top_coords()

    def draw_polygon(self):
        if len(self.roi_coords) == 2:
            self.polyg_top = self.canvas.create_line(self.roi_coords,
                                                     fill='green',
                                                     width=2)
            self.polyg_down = self.canvas.create_line(self.mirror_coords(),
                                                      fill='green',
                                                      width=2)
        elif len(self.roi_coords) > 2:
            self.polyg_top = self.canvas.create_polygon(self.roi_coords,
                                                        fill='',
                                                        outline='green',
                                                        width=2)
            self.polyg_down = self.canvas.create_polygon(self.mirror_coords(),
                                                         fill='',
                                                         outline='green',
                                                         width=2)

    def on_double_click(self, event):
        if self.shape.get() == 'apo_manual':
            if len(self.apo_points) >= 2:
                self.view.apo_from_points(self.apo_points)
            return
        if self.shape.get() == 'polygon':
            self.get_top_coords()

    def on_button_press(self, event):
        if self.shape.get() == 'apo_auto':          # click on the aponeurosis: follow the line from there
            self.view.apo_from_click(*self.to_top(event.x, event.y))
            return
        if self.shape.get() == 'apo_manual':        # points along the aponeurosis, double-click to finish
            if self.apo_result:                      # a finished line: start a new one
                self.clear_apo()
                self.roi_coords = []
            point = self.to_top(event.x, event.y)
            if not self.apo_points or point != self.apo_points[-1]:
                self.apo_points.append(point)
            self.view.show_apo_hint()
            self.draw_apo()
            return
        if self.new_roi.get():
            self.reset_draw()
        self.new_roi.set(False)
        x, y = event.x, event.y
        self.roi_coords.append((x, y))
        self.canvas.delete(self.polyg_top, self.polyg_down)
        if len(self.roi_coords) == 1:
            pt_coords = (x - 1, y - 1, x + 1, y + 1)
            self.polyg_top = self.canvas.create_oval(pt_coords,
                                                     fill='green',
                                                     outline='green',
                                                     width=5)
            self.polyg_down = self.canvas.create_oval(self.mirror_coords(pt_coords),
                                                      fill='green',
                                                      outline='green',
                                                      width=5)
        else:
            self.draw_rois()


class DisplayControls(ttk.Frame):
    """Panel of GUI displaying app to display images"""

    def __init__(self, parent):
        super().__init__(parent)

        self.img_panel = parent

        self.current_frame = 0

        self.pause = False  # control video pause
        self.play_btn = ttk.Button(self, width=6, text="Play")
        self.play_btn.pack(side='left')
        self.play_btn['command'] = self.toggle_play_pause

        self.current_value = tk.DoubleVar()
        self.slider = ttk.Scale(self, from_=0, to=0, variable=self.current_value)
        self.slider['state'] = 'disabled'
        self.slider.pack(side='left', padx=5, pady=5, expand=True, fill='both')
        self.slider['command'] = self.update_slider

        self.frame_label = ttk.Label(self, width=10, text='')
        self.frame_label.pack(side='left')

    def update_slider(self, event):
        if int(self.current_value.get()) < self.img_panel.n_frames:
            self.current_frame = int(self.current_value.get())
            self.frame_label.config(text=f'{self.current_frame + 1}/{self.img_panel.n_frames}')
            self.update_frame()
            self.img_panel.canvas.focus_set()

    def toggle_play_pause(self):
        if self.pause:
            self.pause = False
            self.play_btn.config(text='Play')
            self.after_cancel(self.after_id)
            self.img_panel.canvas.focus_set()
        else:
            self.pause = True
            self.play_btn.config(text='Pause')
            self.play_video()

    def play_video(self):
        if self.img_panel.current_array is not None:
            self.update_frame()
            self.current_frame += 1
            if self.current_frame < self.img_panel.n_frames:
                self.after_id = self.after(50, self.play_video)  # 50ms
            else:
                self.pause = False
                self.play_btn.config(text='Play')
                self.current_frame = 0
        else:
            warn_no_video()
            return

    def update_frame(self):
        self.current_value.set(self.current_frame)
        self.frame_label.config(text=f'{self.current_frame + 1}/{self.img_panel.n_frames}')
        self.image = Image.fromarray(self.img_panel.current_array[self.current_frame])
        self.img = ImageTk.PhotoImage(image=self.image)
        self.img_panel.canvas.create_image(0, 0, anchor=tk.NW, image=self.img)
        self.img_panel.set_rois()

    def left_key(self, event):
        if int(self.current_value.get()) > 0:
            self.current_frame -= 1
            self.update_frame()

    def right_key(self, event):
        if int(self.current_value.get()) < self.img_panel.n_frames - 1:
            self.current_frame += 1
            self.update_frame()
