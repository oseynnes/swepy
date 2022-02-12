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

        self.usr_params = utils.load_settings('SWE_PARAM')
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
        self.roi_coords = None
        self.polyg1 = self.polyg2 = self.start_x = self.start_y = None
        self.x = self.y = 0
        self.fov_coords = {'x0': 0,
                           'y0': 0,
                           'x1': int(self.canvas['width']),
                           'y1': int(self.canvas['height']) / 2}

        self.current_array = None
        self.img = None
        self.img_name = None

        self.ctrl = DisplayControls(self)
        self.frame_label_var = tk.StringVar()

    def activate_draw(self):
        self.canvas.bind('<Button-1>', self.on_button_press)
        self.canvas.bind('<B1-Motion>', self.on_move_press)
        self.canvas.bind('<ButtonRelease-1>', self.on_button_release)

    def activate_slider(self, n_frames):
        self.n_frames = n_frames
        self.ctrl.frame_label.config(text=f'{self.ctrl.current_frame + 1}/{n_frames}')
        self.ctrl.slider.config(to=self.n_frames)
        self.ctrl.slider.config(state='normal')  # activate slider

    def isin_fov(self):
        in_x_bounds = self.fov_coords['x0'] <= self.start_x <= self.fov_coords['x1']
        in_y_bounds = self.fov_coords['y0'] <= self.start_y <= self.fov_coords['y1']
        return in_x_bounds and in_y_bounds

    def set_rois(self):
        if self.roi_coords:
            self.draw_rois(self.roi_coords['x0'],
                           self.roi_coords['y0'],
                           self.roi_coords['x1'],
                           self.roi_coords['y1'])

    def draw_rois(self, x1, y1, x2, y2):
        if self.polyg1:
            self.del_rois()
        self.polyg1 = self.canvas.create_rectangle(x1, y1, x2, y2, outline='red')
        self.polyg2 = self.canvas.create_rectangle(x1, y1 + 225, x2, y2 + 225, outline='red')

    def del_rois(self):
        self.canvas.delete(self.polyg1, self.polyg2)

    def on_button_press(self, event):
        # save mouse drag start position
        self.start_x = self.canvas.canvasx(event.x)
        self.start_y = self.canvas.canvasy(event.y)
        if not self.polyg1:
            self.draw_rois(self.x, self.y, 1, 1)

    def on_move_press(self, event):
        # expand rectangle as you drag the mouse
        cur_x, cur_y = (event.x, event.y)
        self.roi_offset = 225 if self.isin_fov() else -225
        self.canvas.coords(self.polyg1, self.start_x, self.start_y, cur_x, cur_y)
        self.canvas.coords(self.polyg2,
                           self.start_x,
                           self.start_y + self.roi_offset,
                           cur_x,
                           cur_y + self.roi_offset)
        self.points = self.polyg1 if self.isin_fov() else self.polyg2

    def on_button_release(self, event):
        keys = ('x0', 'y0', 'x1', 'y1')
        self.roi_coords = dict(zip(keys, self.canvas.coords(self.points)))
        self.roi_coords = {k: int(v) for k, v in self.roi_coords.items()}


class DisplayControls(ttk.Frame):
    """Panel of GUI displaying widgets to display images"""

    def __init__(self, parent):
        super().__init__(parent)

        self.img_panel = parent

        self.grid(row=4, column=1, sticky=tk.EW)

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


if __name__ == '__main__':

    class Draw(ttk.Frame):
        def __init__(self, parent):
            super().__init__(parent)

            self.canvas = tk.Canvas(self, width=720, height=540, bg='black', cursor="cross")
            self.canvas.grid(row=1, column=1, rowspan=3, sticky=tk.NSEW, padx=5, pady=5)
            self.grid(row=1, column=1, rowspan=3, sticky=tk.NSEW, padx=5, pady=5)
            self.columnconfigure(1, weight=4)
            self.rowconfigure(1, weight=4)

            self.roi_coords = None
            self.polyg1 = self.polyg2 = self.start_x = self.start_y = None
            self.x = self.y = 0
            self.fov_coords = {'x0': 0,
                               'y0': 0,
                               'x1': int(self.canvas['width']),
                               'y1': int(self.canvas['height']) / 2}

            self.current_array = None
            self.img = None
            self.img_name = None

        def activate_draw(self):
            self.canvas.bind('<Button-1>', self.on_button_press)
            self.canvas.bind('<B1-Motion>', self.on_move_press)
            self.canvas.bind('<ButtonRelease-1>', self.on_button_release)

        def isin_fov(self):
            in_x_bounds = self.fov_coords['x0'] <= self.start_x <= self.fov_coords['x1']
            in_y_bounds = self.fov_coords['y0'] <= self.start_y <= self.fov_coords['y1']
            return in_x_bounds and in_y_bounds

        def set_rois(self):
            if self.roi_coords:
                self.draw_rois(self.roi_coords['x0'],
                               self.roi_coords['y0'],
                               self.roi_coords['x1'],
                               self.roi_coords['y1'])

        def draw_rois(self, x1, y1, x2, y2):
            if self.polyg1:
                self.del_rois()
            self.polyg1 = self.canvas.create_rectangle(x1, y1, x2, y2, outline='red')
            self.polyg2 = self.canvas.create_rectangle(x1, y1 + 225, x2, y2 + 225, outline='red')

        def del_rois(self):
            self.canvas.delete(self.polyg1, self.polyg2)

        def on_button_press(self, event):
            # save mouse drag start position
            self.start_x = self.canvas.canvasx(event.x)
            self.start_y = self.canvas.canvasy(event.y)
            if not self.polyg1:
                self.draw_rois(self.x, self.y, 1, 1)

        def on_move_press(self, event):
            cur_x, cur_y = (event.x, event.y)
            self.roi_offset = 225 if self.isin_fov() else -225
            self.canvas.coords(self.polyg1, self.start_x, self.start_y, cur_x, cur_y)
            self.canvas.coords(self.polyg2,
                               self.start_x,
                               self.start_y + self.roi_offset,
                               cur_x,
                               cur_y + self.roi_offset)
            self.points = self.polyg1 if self.isin_fov() else self.polyg2

        def on_button_release(self, event):
            keys = ('x0', 'y0', 'x1', 'y1')
            self.roi_coords = dict(zip(keys, self.canvas.coords(self.points)))
            self.roi_coords = {k: int(v) for k, v in self.roi_coords.items()}
            print(f'ROI coords: {self.roi_coords}')


    class App(tk.Tk):
        def __init__(self):
            super().__init__()
            self.geometry('800x600')


    app = App()
    draw = Draw(app)
    draw.activate_draw()
    app.mainloop()
