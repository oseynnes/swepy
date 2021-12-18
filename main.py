import tkinter as tk
from pathlib import Path
from tkinter import ttk

from PIL import ImageTk, Image
from matplotlib.backends.backend_tkagg import (FigureCanvasTkAgg,
                                               NavigationToolbar2Tk)
from matplotlib.figure import Figure
import numpy as np
import pandas as pd
import utils
from processing import Data
from root_frames import MenuBar
from view_frames import ImgPanel, TopPanel, LeftPanel, DisplayControls
from output_frames import FilesFrame, SaveFrame, FigFrame


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
        self.swe_fhz = None
        self.max_scale = None
        # self.left_panel.fhz_entry.bind('<Return>', self.get_usr_entry)
        self.left_panel.enter_btn['command'] = self.get_usr_entry
        self.left_panel.reset_roi_btn['command'] = self.reset_rois
        self.left_panel.analyse_btn['command'] = self.analyse

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

    def get_usr_entry(self):
        """Log user entry, re-sample video and save to JSON file"""
        if self.ds:
            self.swe_fhz = utils.log_entry('SWE Fhz',
                                           self.left_panel.usr_fhz,
                                           self.left_panel.tv,
                                           'swe_row')
            self.max_scale = utils.log_entry('max. scale',
                                             self.left_panel.usr_scale,
                                             self.left_panel.tv,
                                             'scale_row',
                                             var_type=int)
            if isinstance(self.swe_fhz, (int, float)):
                self.get_swe_frames()
                utils.save_usr_input(self.swe_fhz, self.max_scale)
            self.canvas.focus_set()
        else:
            utils.warn_no_video()
            return

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
        """Populate table with info from dicom header and json file"""
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

    def right_key(self, event):
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

    def __init__(self, data, view, output):
        self.data = data
        self.view = view
        self.output = output

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
        if not all([self.view.swe_fhz, self.view.max_scale]):
            utils.warn_wrong_entry()
            return
        self.data.swe_fhz = self.view.swe_fhz
        self.data.max_scale = self.view.max_scale
        self.data.roi_coords = self.view.img_panel.roi_coords
        self.data.analyse_roi(self.data.get_rois())
        self.output.fig_frame.results = self.data.results
        self.output.fig_frame.replot_data(self.data.results['raw'][self.data.source_var],
                                          self.data.source_var)
        self.output.add_to_file_list(self.data.path)
        utils.pickle_results(self.data.path, self.data.results)


class Output(ttk.Frame):  # TODO: move to other module
    """Tab frame displaying analysis output"""

    def __init__(self, parent):
        super().__init__(parent)

        self.grid(row=0, column=0, columnspan=2, rowspan=5, sticky=tk.NSEW)
        self.columnconfigure(0, weight=1)
        self.columnconfigure(1, weight=3)

        self.results = None

        self.files_frame = FilesFrame(self)
        self.files = []
        self.files_frame.tv.bind('<<TreeviewSelect>>', self.file_selected)

        self.add_scrollbars(self.files_frame)  # TODO: fix scroll bar

        self.save_frame = SaveFrame(self)
        self.save_frame.csv_btn['command'] = \
            lambda: self.save_frame.export_to(self.results, 'csv')
        self.save_frame.xlsx_btn['command'] = \
            lambda: self.save_frame.export_to(self.results, 'xlsx')

        self.fig_frame = FigFrame(self)

    def add_scrollbars(self, container):
        sb_x = ttk.Scrollbar(container, orient=tk.HORIZONTAL, command=self.files_frame.tv.xview)
        sb_y = ttk.Scrollbar(container, orient=tk.VERTICAL, command=self.files_frame.tv.yview)
        self.files_frame.tv.configure(xscrollcommand=sb_x.set, yscrollcommand=sb_y.set)
        sb_x.grid(row=4, column=0, sticky='ew')
        sb_y.grid(row=0, column=1, sticky='ns')

    def add_to_file_list(self, path):
        """Add file name and path to list of analysed files"""
        self.files.append((path.name, path.resolve().parent))
        if path.name in self.files_frame.tv.get_children():
            self.files_frame.tv.delete(path.name)
        self.files_frame.tv.insert('', tk.END, values=self.files[-1], iid=path.name)
        self.files_frame.tv.focus(self.files_frame.tv.get_children()[-1])

    def file_selected(self, event):
        rows = []
        for selected_item in self.files_frame.tv.selection():
            item = self.files_frame.tv.item(selected_item)
            row = item['values']
            rows.append(row)
        if len(rows) == 1:
            name = rows[0][0].split('.')[0]
            path = Path.cwd() / 'src' / f'{name}.pickle'
            self.fig_frame.results = utils.load_pickle(path)
            self.fig_frame.change_plot()

    def clear_output(self):
        # TODO: connect clear output to menu command
        # clear treeview
        # clear figure
        # delete output files
        pass


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

        self.nb = ttk.Notebook(self)
        self.nb.grid()
        self.load_file()
        self.output = Output(self.nb)
        self.nb.add(self.view, text='Image processing')
        self.nb.add(self.output, text='Results')

    def load_file(self):
        """Instantiate classes specific to a file"""
        self.data = Data(self.path)
        self.view = View(self.nb)

    def reset(self, path=None):
        """Reset file processing"""
        self.path = path if path else self.mb.select_file()
        utils.save_path(str(self.path.resolve()))
        self.nb.forget(self.view)
        self.load_file()
        self.data.path = self.path
        # self.output.add_to_file_list(self.path)
        self.nb.insert(0, self.view, text='Image processing')
        self.nb.select(self.view)
        controller = Controller(self.data, self.view, self.output)
        self.view.set_controller(controller)
        controller.get_dicom_data()


if __name__ == '__main__':
    app = App()
    app.mainloop()

    # TODO: - add doctrings to functions
    #       - fix window and widgets resize
