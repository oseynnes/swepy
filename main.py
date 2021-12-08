import tkinter as tk
from tkinter import ttk

from PIL import ImageTk, Image

import utils
from processing import Data
from ttk_frames import MenuBar, ImgPanel, TopPanel, LeftPanel, DisplayControls


class View(ttk.Frame):
    """Accessing tkinter frames composing the GUI"""

    def __init__(self, parent):
        super().__init__(parent)

        self.grid(row=0, column=0, rowspan=4, sticky=tk.NSEW)

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
        self.init_roi_coords = None
        self.roi_coords = self.img_panel.roi_coords
        self.n_frame = 0
        self.current_frame = 0

        self.top = TopPanel(self)

        self.left_panel = LeftPanel(self)
        self.swe_fhz = self.left_panel.swe_fhz
        self.left_panel.usr_entry.bind('<Return>', self.get_usr_entry)
        self.left_panel.btn_reset_roi['command'] = self.reset_rois
        self.left_panel.btn_analyse['command'] = self.analyse

        self.controls = DisplayControls(self)
        self.controls.slider['command'] = self.update_slider
        self.controls.play_btn['command'] = self.toggle_play_pause
        self.frame_label_var = tk.StringVar()

    def set_controller(self, controller):
        self.controller = controller

    def reset_rois(self):
        self.img_panel.roi_coords = self.init_roi_coords
        self.img_panel.set_rois()

    def analyse(self):
        if self.ds:
            self.controller.analyse()
        else:
            utils.warn_no_video()
            return

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
        # self.activate_arrowkeys()
        self.canvas.focus_set()

    def get_swe_frames(self):
        self.swe_array = self.controller.get_swe_array(self.swe_fhz)
        self.current_array = self.swe_array
        self.controls.current_value.set(0)
        self.activate_slider(self.swe_array.shape[0])
        self.current_frame = 0
        self.update_frame()

    def update_slider(self, event):
        if int(self.controls.current_value.get()) < self.n_frame:
            self.current_frame = int(self.controls.current_value.get())
            self.controls.frame_label.config(text=f'{self.current_frame + 1}/{self.n_frame}')
            self.update_frame()
            self.canvas.focus_set()

    def toggle_play_pause(self):
        if self.controls.pause:
            self.controls.pause = False
            self.controls.play_btn.config(text='Play')
            self.after_cancel(self.after_id)
            self.canvas.focus_set()
        else:
            self.controls.pause = True
            self.controls.play_btn.config(text='Pause')
            self.play_video()

    def play_video(self):
        if self.ds:
            self.update_frame()
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

    def activate_arrowkeys(self):
        self.canvas.focus_set()
        self.canvas.bind('<Left>', self.left_key)
        self.canvas.bind('<Right>', self.right_key)

    def left_key(self, event):
        if int(self.controls.current_value.get()) > 0:
            self.current_frame -= 1
            self.update_frame()

    def right_key(self, event):  # TODO: test arrow keys functions
        if int(self.controls.current_value.get()) < self.n_frame - 1:
            self.current_frame += 1
            self.update_frame()

    def set_img_name(self):
        self.top.img_name.config(text=self.img_name)

    def update_frame(self):
        self.controls.current_value.set(self.current_frame)
        self.controls.frame_label.config(text=f'{self.current_frame + 1}/{self.n_frame}')
        self.img = ImageTk.PhotoImage(image=Image.fromarray(self.current_array[self.current_frame]))
        self.canvas.create_image(0, 0, anchor=tk.NW, image=self.img)
        self.img_panel.set_rois()

    def load_file(self):
        self.img_panel.fov_coords = self.fov_coords
        self.img_panel.roi_coords = self.init_roi_coords
        self.current_array = self.img_array
        self.update_frame()
        self.activate_slider(self.ds.NumberOfFrames)
        self.img_panel.activate_draw()
        self.update_dcm_info()
        self.set_img_name()
        self.activate_arrowkeys()


class Controller:
    """Routing data between View (GUI) and Data (dicom) classes"""

    def __init__(self, data, view, results):
        self.data = data
        self.view = view
        self.results = results

    def save_roi_coords(self, coords):
        self.data.roi_coords = coords

    def get_dicom_data(self):
        # TODO: link to a ttk.Progressbar widget (dicom loading is a few seconds)
        self.data.load_dicom()
        self.view.ds = self.data.ds
        self.view.img_array = self.data.img_array
        self.view.img_name = self.data.img_name
        self.view.fov_coords = self.data.top_fov_coords
        self.view.init_roi_coords = self.data.roi_coords
        self.view.load_file()

    def get_swe_array(self, swe_fhz):
        return self.data.resample(swe_fhz)

    def analyse(self):
        self.data.roi_coords = self.view.img_panel.roi_coords
        # TODO: continue function:
        #                   - select roi in each frame
        #                   - filter voids
        #                   - get relevant variables of SWE from RGB values in ROI and scale bar
        pass


class Results(ttk.Frame):
    def __init__(self, parent):
        super().__init__(parent)

        self.grid(row=0, column=0, columnspan=2, rowspan=4, sticky=tk.NSEW)
        self.columnconfigure(0, weight=1)
        self.columnconfigure(1, weight=4)

        self.file_list_frame = ttk.LabelFrame(self, text='Analysed files')
        self.file_list_frame.grid(row=0, column=0, rowspan=4, padx=5, pady=5, sticky=tk.NSEW)
        test_btn = ttk.Button(self.file_list_frame)
        test_btn.pack()

        self.fig_frame = ttk.LabelFrame(self, text='Output')
        self.canvas = tk.Canvas(self.fig_frame, bg='white')
        self.canvas.grid(row=0, column=1, rowspan=4, sticky=tk.NSEW, padx=5, pady=5)
        self.fig_frame.grid(row=0, column=1, rowspan=4, padx=5, pady=5, sticky=tk.NSEW)


class App(tk.Tk):
    """Root window of tkinter app"""

    def __init__(self):
        super().__init__()

        self.title('SwePy')
        window_width = 950
        window_height = 690
        utils.set_win_geometry(self, window_width, window_height)
        self.columnconfigure(0, weight=1)
        self.columnconfigure(1, weight=4)
        self.resizable(False, False)  # prevent resizing for now

        self.path = None

        self.mb = MenuBar(self)
        self.config(menu=self.mb)

        # create tab system
        self.nb = ttk.Notebook(self)
        self.nb.grid()
        self.load_file()
        self.results = Results(self.nb)
        self.nb.add(self.view, text='Image processing')
        self.nb.add(self.results, text='Results')
        # TODO: try and implement display of results in its own tab

    def load_file(self):
        self.data = Data(self.path)
        self.view = View(self.nb)

    def reset(self, path=None):
        self.path = path if path else self.mb.select_file()
        utils.add_to_paths(str(self.path.resolve()))
        self.nb.forget(self.view)
        self.load_file()
        self.data.path = self.path
        self.nb.insert(0, self.view, text='Image processing')
        self.nb.select(self.view)
        controller = Controller(self.data, self.view, self.results)
        self.view.set_controller(controller)
        controller.get_dicom_data()


if __name__ == '__main__':
    app = App()
    app.mainloop()

    # TODO: - add doctrings to functions
    #       - fix window and widgets resize
