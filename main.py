import tkinter as tk
from tkinter import ttk
from tkinter import filedialog as fd

from pathlib import Path

from PIL import ImageTk, Image

import utils
from processing import Data
from ttk_frames import ImgPanel, TopPanel, LeftPanel, DisplayControls


class View(ttk.Frame):
    def __init__(self, parent):
        super().__init__(parent)

        # TODO: add function to reset attributes and widgets
        self.ds = None
        self.img_array = None
        self.swe_array = None
        self.current_array = None
        self.img = None
        self.img_name = None

        self.controller = None

        self.img_panel = ImgPanel(self)
        self.canvas = self.img_panel.canvas
        self.fov_coords = None
        self.roi_coords = None
        self.n_frame = 0
        self.current_frame = 0

        self.top = TopPanel(self)

        self.left_panel = LeftPanel(self)
        self.swe_fhz = self.left_panel.swe_fhz
        self.left_panel.usr_entry.bind('<Return>', self.get_usr_entry)
        self.left_panel.btn_analyse['command'] = self.analyse

        self.controls = DisplayControls(self)
        self.controls.slider['command'] = self.update_slider
        self.controls.play_btn['command'] = self.toggle_play_pause
        self.frame_label_var = tk.StringVar()

    def set_controller(self, controller):
        self.controller = controller

    def analyse(self):
        self.controller.analyse()

    def get_usr_entry(self, event):
        if self.ds:
            self.save_fhz(event)
            self.get_swe_frames()
        else:
            utils.warn_no_video()
            return

    def save_fhz(self, event):
        try:
            float(self.left_panel.usr_value.get())
        except ValueError:
            utils.warn_no_number()
            return
        self.swe_fhz = float(self.left_panel.usr_value.get())
        if 'swe_row' in self.left_panel.tv.get_children():
            self.left_panel.tv.delete('swe_row')
        self.left_panel.tv.insert(parent='',
                                  index=tk.END,
                                  iid='swe_row',
                                  values=('SWE Fhz', self.swe_fhz))

    def get_swe_frames(self):
        self.swe_array = self.controller.get_swe_array(self.swe_fhz)
        self.current_array = self.swe_array
        self.controls.current_value.set(0)
        self.activate_slider(self.swe_array.shape[0])
        self.current_frame = 0
        self.update_frame(self.current_frame)

    def update_slider(self, event):
        if int(self.controls.current_value.get()) < self.n_frame:
            self.current_frame = int(self.controls.current_value.get())
            self.controls.frame_label.config(text=f'{self.current_frame + 1}/{self.n_frame}')
            self.update_frame(self.current_frame)

    def toggle_play_pause(self):
        if self.controls.pause:
            self.controls.pause = False
            self.controls.play_btn.config(text='Play')
            self.after_cancel(self.after_id)
        else:
            self.controls.pause = True
            self.controls.play_btn.config(text='Pause')
            self.play_video()

    def play_video(self):
        if self.ds:
            self.controls.current_value.set(self.current_frame)
            self.update_frame(self.current_frame)
            self.current_frame += 1
            if self.current_frame < self.n_frame:
                self.after_id = self.after(50, self.play_video)  # 50ms
            else:
                self.controls.pause = False
                self.controls.play_btn.config(text='Play')
                self.current_frame = 0
        else:
            utils.warn_no_video()
            return

    def update_dcm_info(self):
        self.left_panel.values = (self.ds.NumberOfFrames,
                                  self.ds.Rows,
                                  self.ds.Columns,
                                  self.ds.RecommendedDisplayFrameRate)  # get dcm info
        rows = (zip(self.left_panel.variables, self.left_panel.values))
        for row in rows:
            self.left_panel.tv.insert(parent='', index=tk.END, values=row)

    def activate_slider(self, n_frames):
        self.n_frame = n_frames
        self.controls.frame_label.config(text=f'{self.current_frame + 1}/{n_frames}')
        self.controls.slider.config(to=self.n_frame)
        self.controls.slider.config(state='normal')  # activate slider

    def set_img_name(self):
        self.top.img_name.config(text=self.img_name)

    def update_frame(self, frame_idx):
        self.img = ImageTk.PhotoImage(image=Image.fromarray(self.current_array[frame_idx]))
        self.canvas.create_image(0, 0, anchor=tk.NW, image=self.img)

    def load_file(self):
        self.current_array = self.img_array
        self.update_frame(self.current_frame)
        self.activate_slider(self.ds.NumberOfFrames)
        self.img_panel.activate_draw()
        self.update_dcm_info()
        self.set_img_name()
        self.img_panel.fov_coords = self.fov_coords
        self.left_panel.usr_entry.focus()


class Controller:
    def __init__(self, data, view):

        self.data = data
        self.view = view

    def save_roi_coords(self, coords):
        self.data.roi_coords = coords

    def get_dicom_data(self):
        # TODO: link to a ttk.Progressbar widget (dicom loading is a few seconds)
        self.data.load_dicom()
        self.view.ds = self.data.ds
        self.view.img_array = self.data.img_array
        self.view.img_name = self.data.img_name
        self.view.fov_coords = self.data.top_fov_coords
        self.view.roi_coords = self.data.roi_coords
        self.view.load_file()

    def get_swe_array(self, swe_fhz):
        return self.data.resample(swe_fhz)

    def analyse(self):
        self.data.roi_coords = self.view.img_panel.roi_coords  # TODO: choose to btw dictionary and array formats
        # TODO: continue function:
        #                   - select roi in each frame
        #                   - filter voids
        #                   - get relevant variables of SWE from RGB values in ROI and scale bar
        pass


class App(tk.Tk):
    def __init__(self):
        super().__init__()

        self.path = None
        data, view = self.set_classes()

        self.title('SwePy')
        window_width = 960
        window_height = 650
        utils.set_win_geometry(self, window_width, window_height)
        self.columnconfigure(0, weight=1)
        self.columnconfigure(1, weight=4)

        self.open_frame = ttk.Frame(self)
        self.open_frame.grid(row=0, column=0, sticky=tk.W)
        self.btn_open = ttk.Button(self.open_frame, text='Open dicom file')
        self.btn_open['command'] = self.reset
        self.btn_open.pack(fill='x', padx=5, pady=5)

    def set_classes(self):
        data = Data(self.path)
        view = View(self)
        view.grid(row=1, column=0, rowspan=4, sticky=tk.NSEW)
        return data, view

    def select_file(self):
        filetypes = (('dicom files', '*.dcm'), ('All files', '*.*'))
        initialdir = self.path.parent if self.path else '/'
        path = fd.askopenfilename(initialdir=initialdir, title="Select dicom file", filetypes=filetypes)
        self.path = Path(path)

    def reset(self):
        self.select_file()
        data, view = self.set_classes()
        data.path = self.path
        controller = Controller(data, view)
        view.set_controller(controller)
        controller.get_dicom_data()


if __name__ == '__main__':
    app = App()
    app.mainloop()

    # TODO: add doctrings to class(es) and functions
