import tkinter as tk
from tkinter import ttk

from PIL import ImageTk, Image

import utils


class TopPanel(ttk.Frame):
    """Panel of GUI displaying file name"""

    def __init__(self, parent):
        super().__init__(parent)
        options = {'fill': 'x', 'padx': 5, 'pady': 5}

        self.grid(row=0, column=1, sticky=tk.EW)

        self.img_name = ttk.Label(self, anchor=tk.CENTER, text='')
        self.img_name.pack(**options)


class LeftPanel(ttk.Frame):
    """Panel of GUI displaying widgets related to file opening and analysis"""

    def __init__(self, parent):
        super().__init__(parent)

        self.grid(row=1, column=0, rowspan=3, sticky=tk.NSEW)

        self.input_frame = ttk.LabelFrame(self, text='User input')
        self.input_frame.grid(row=0, column=0, sticky=tk.NSEW)

        fhz_label = ttk.Label(self.input_frame, text='SWE fhz:')
        fhz_label.grid(column=0, row=0, sticky=tk.W, padx=5)
        self.usr_fhz = tk.StringVar()
        self.fhz_entry = ttk.Entry(self.input_frame, width=4, textvariable=self.usr_fhz)
        self.fhz_entry.grid(column=1, row=0, sticky=tk.E, padx=5)

        scale_label = ttk.Label(self.input_frame, text='max. scale:')
        scale_label.grid(column=0, row=1, sticky=tk.W, padx=5)
        self.usr_scale = tk.StringVar()
        self.scale_entry = ttk.Entry(self.input_frame, width=4, textvariable=self.usr_scale)
        self.scale_entry.grid(column=1, row=1, sticky=tk.E, padx=5)

        self.usr_params = utils.get_settings('SWE_PARAM')
        if self.usr_params:
            self.usr_fhz.set(self.usr_params[0])
            self.usr_scale.set(self.usr_params[1])

        self.enter_btn = ttk.Button(self.input_frame, text='OK', width=2)
        self.enter_btn.grid(column=1, row=3, sticky=tk.E, padx=5, pady=5)

        self.space_frame = ttk.Frame(self)
        self.space_frame.grid(row=1, column=0, sticky=tk.NSEW)
        spacer = tk.Label(self.space_frame, text='')
        spacer.grid()

        self.tree_frame = ttk.Frame(self)
        self.tree_frame.grid(row=2, column=0, sticky=tk.NSEW)
        columns = ('dcm_property', 'value')
        self.variables = ('No. of frames', 'No. of rows', 'No. of columns', 'B mode Fhz')
        self.values = (None,)
        self.tv = ttk.Treeview(self.tree_frame, columns=columns, show='headings')
        self.tv.heading('dcm_property', text="DCM Property")
        self.tv.column('dcm_property', width=100)
        self.tv.heading("value", text="Value")
        self.tv.column('value', width=50)
        self.tv.grid(sticky=tk.NSEW)

        self.reset_roi_btn = ttk.Button(self.tree_frame, text="Reset ROI", width=8)
        self.reset_roi_btn.grid(sticky=tk.W)

        self.analyse_btn = ttk.Button(self.tree_frame, text="Analyse", width=8)
        self.analyse_btn.grid(sticky=tk.W)


class ImgPanel(ttk.Frame):
    """Panel of GUI displaying images"""

    def __init__(self, parent):
        super().__init__(parent)

        self.view = parent

        self.canvas = tk.Canvas(self, width=720, height=540, bg='black', cursor="cross")
        self.canvas.grid(row=1, column=1, rowspan=3, sticky=tk.NSEW, padx=5, pady=5)
        self.grid(row=1, column=1, rowspan=3, sticky=tk.NSEW, padx=5, pady=5)
        self.columnconfigure(1, weight=4)
        self.rowconfigure(1, weight=4)

        self.n_frames = 0
        self.top_fov_coords = {'x0': 0,
                               'y0': 0,
                               'x1': int(self.canvas['width']),
                               'y1': int(self.canvas['height']) / 2}

        self.new_roi = tk.BooleanVar()
        self.new_roi.set(True)
        self.roi_coords = []
        self.polyg1 = self.polyg2 = None

        self.current_array = None
        self.img = None
        self.img_name = None

        # Video controls
        self.ctrl = DisplayControls(self)
        self.frame_label_var = tk.StringVar()

        # Choice of ROI shape
        self.btn_frame = ttk.LabelFrame(self, text='ROI shape')
        self.shape = tk.StringVar()
        self.shape.set('rectangle')

        ttk.Radiobutton(
            self.btn_frame,
            text='Rectangle',
            value='rectangle',
            variable=self.shape,
            command=self.reset_draw).grid(column=0, row=0, padx=5, pady=5)

        ttk.Radiobutton(
            self.btn_frame,
            text='Polygon',
            value='polygon',
            variable=self.shape,
            command=self.reset_draw).grid(column=1, row=0, padx=5, pady=5)

        self.btn_frame.grid(column=1, row=4, padx=5, pady=5, sticky='ew')

    # Specific functions
    def activate_draw(self):
        self.canvas.bind('<Button-1>', self.on_button_press)
        if self.shape.get() == 'polygon':
            self.canvas.bind("<Double-1>", self.on_double_click)

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
            coords (list): (x, y) coordinates for polygon points
        Returns: offset list of (x, y) coordinates
        """
        roi_coords = self.roi_coords if not coords else coords
        roi_offset = 225 if self.isin_top_fov() else -225
        if isinstance(roi_coords[0], tuple):
            m_coords = [(coord[0], coord[1] + roi_offset) for coord in roi_coords]
        elif isinstance(roi_coords[0], int):
            m_coords = [c if not i % 2 else c + roi_offset for i, c in enumerate(roi_coords)]
        else:
            raise Exception('Error due to format of ROI coordinates')
        return m_coords

    def reset_draw(self):
        self.clear_coords()
        self.canvas.delete(self.polyg1, self.polyg2)
        self.activate_draw()

    def get_top_coords(self):
        """Set coordinates of ROI in top field of view as the main ones"""
        self.roi_coords = self.roi_coords if self.isin_top_fov() else self.mirror_coords()
        self.new_roi.set(True)

    def set_rois(self):
        if self.roi_coords:
            self.draw_rois()

    def draw_rois(self):
        self.canvas.delete(self.polyg1, self.polyg2)
        if self.shape.get() == 'rectangle':
            self.draw_rectangle()
        elif self.shape.get() == 'polygon':
            self.draw_polygon()

    def draw_rectangle(self):
        self.polyg1 = self.canvas.create_rectangle(self.roi_coords,
                                                   outline='green',
                                                   width=2)
        self.polyg2 = self.canvas.create_rectangle(*self.mirror_coords(),
                                                   outline='green',
                                                   width=2)
        self.get_top_coords()

    def draw_polygon(self):
        if len(self.roi_coords) == 2:
            self.polyg1 = self.canvas.create_line(self.roi_coords,
                                                  fill='green',
                                                  width=2)
            self.polyg2 = self.canvas.create_line(self.mirror_coords(),
                                                  fill='green',
                                                  width=2)
        elif len(self.roi_coords) > 2:
            self.polyg1 = self.canvas.create_polygon(self.roi_coords,
                                                     fill='',
                                                     outline='green',
                                                     width=2)
            self.polyg2 = self.canvas.create_polygon(self.mirror_coords(),
                                                     fill='',
                                                     outline='green',
                                                     width=2)

    def on_double_click(self, event):
        self.get_top_coords()

    def on_button_press(self, event):
        if self.new_roi.get():
            self.reset_draw()
        self.new_roi.set(False)
        x, y = event.x, event.y
        self.roi_coords.append((x, y))
        self.canvas.delete(self.polyg1, self.polyg2)
        if len(self.roi_coords) == 1:
            pt_coords = (x - 1, y - 1, x + 1, y + 1)
            self.polyg1 = self.canvas.create_oval(pt_coords,
                                                  fill='green',
                                                  outline='green',
                                                  width=5)
            self.polyg2 = self.canvas.create_oval(self.mirror_coords(pt_coords),
                                                  fill='green',
                                                  outline='green',
                                                  width=5)
        else:
            self.draw_rois()


class DisplayControls(ttk.Frame):
    """Panel of GUI displaying widgets to display images"""

    def __init__(self, parent):
        super().__init__(parent)

        self.img_panel = parent

        self.grid(row=5, column=1, sticky=tk.EW)

        self.current_frame = 0

        self.pause = False  # control video pause
        self.play_btn = ttk.Button(self, width=5, text="Play")
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
            utils.warn_no_video()
            return

    def update_frame(self):
        self.current_value.set(self.current_frame)
        self.frame_label.config(text=f'{self.current_frame + 1}/{self.img_panel.n_frames}')
        self.img = ImageTk.PhotoImage(image=Image.fromarray(self.img_panel.current_array[self.current_frame]))
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
