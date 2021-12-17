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
        if not all([self.view.swe_fhz, self.view.max_scale]):
            utils.warn_wrong_entry()
            return
        self.data.swe_fhz = self.view.swe_fhz
        self.data.max_scale = self.view.max_scale
        self.data.roi_coords = self.view.img_panel.roi_coords
        self.data.analyse_roi(self.data.get_rois())
        self.output.replot_data(self.data.results['raw'][self.data.source_var],
                                self.data.source_var)
        self.output.add_to_file_list(self.data.path)
        utils.pickle_results(self.data.path, self.data.results)
        self.output.results = self.data.results

        # TODO: continue function
        pass


class Output(ttk.Frame):  # TODO: move to other module
    """Tab frame displaying analysis output"""

    def __init__(self, parent):
        super().__init__(parent)

        self.grid(row=0, column=0, columnspan=2, rowspan=5, sticky=tk.NSEW)
        self.columnconfigure(0, weight=1)
        self.columnconfigure(1, weight=3)

        self.results = None
        self.files_frame = ttk.LabelFrame(self, text='Analysed files')
        self.files_frame.grid(row=0, column=0, rowspan=4, padx=5, pady=5, sticky=tk.N)
        columns = ('file_name', 'path')
        self.tv = ttk.Treeview(self.files_frame, columns=columns, show='headings')
        self.tv.heading('file_name', text='File')
        self.tv.column('file_name', width=100)
        self.tv.heading('path', text='Path')
        self.tv.column('path', width=200)
        self.files = []
        self.tv.bind('<<TreeviewSelect>>', self.file_selected)
        self.tv.grid(row=0, column=0, padx=5, pady=5, sticky=tk.NSEW)

        self.add_scrollbars(self.files_frame)  # TODO: fix scroll bar

        self.save_frame = ttk.LabelFrame(self.files_frame, text='Save to')
        self.save_frame.grid(row=5, column=0, padx=5, pady=5, sticky=tk.EW)
        self.csv_btn = ttk.Button(self.save_frame,
                                  text='CSV',
                                  command=lambda: self.export_to('csv'))
        self.csv_btn.grid(column=0, row=0, sticky=tk.W, padx=5, pady=5)
        self.xlsx_btn = ttk.Button(self.save_frame,
                                  text='Excel',
                                  command=lambda: self.export_to('xlsx'))
        self.xlsx_btn.grid(column=1, row=0, sticky=tk.E, padx=5, pady=5)

        self.fig_frame = ttk.LabelFrame(self, text='Output')
        self.fig_frame.grid(row=0, column=1, rowspan=4, padx=5, pady=5, sticky=tk.NSEW)

        self.lf = ttk.LabelFrame(self, text='Variable')
        self.lf.grid(row=5, column=1, padx=5, pady=5)
        self.label_var = tk.StringVar()
        self.y_labels = {'velocity': 'Wave velocity (m/s)',
                         'shear_m': 'Shear modulus (KPa)',
                         'youngs_m': "Young's modulus (KPa"}
        grid_column = 0
        for key, label in self.y_labels.items():
            radio = ttk.Radiobutton(self.lf,
                                    text=label,
                                    value=key,
                                    command=self.change_plot,
                                    variable=self.label_var)
            radio.grid(column=grid_column, row=0, ipadx=10, ipady=10)
            grid_column += 1

    def change_variable(self):
        self.var = self.label_var.get()

    def change_plot(self):
        if self.results is None:
            return
        self.change_variable()
        D = self.results['raw'][self.var]
        self.replot_data(D, self.var)

    def replot_data(self, D, swe_var):
        """Reset widgets to plot new data
        Args:
            D: data 3D array of shape (n frames, height, width).
        Returns: None
        """
        for widget in self.fig_frame.winfo_children():
            widget.destroy()
        swe_vars = ['velocity', 'shear_m', 'youngs_m']
        assert (swe_var in swe_vars), "'swe_var' can only be 'velocity', 'shear_m' or 'youngs_m'"
        self.label_var.set(swe_var)
        self.change_variable()
        frame_dim = D.shape[0]
        plot_data = D.reshape(frame_dim, -1)

        figure = Figure(figsize=(6, 4), dpi=100)
        figure_canvas = FigureCanvasTkAgg(figure, self.fig_frame)
        # NavigationToolbar2Tk(figure_canvas, self.fig_frame)
        axes = figure.add_subplot()

        vp = axes.violinplot(plot_data.tolist(), widths=1,
                             showmeans=True, showmedians=True, showextrema=False)

        for body in vp['bodies']:
            body.set_facecolor('#D43F3A')
            body.set_alpha(1)
            body.set_edgecolor('#473535')

        vp['cmeans'].set_color('#473535')
        vp['cmedians'].set_color('white')

        std = np.std(D, axis=(1, 2))
        xy = [[l.vertices[:, 0].mean(), l.vertices[0, 1]] for l in vp['cmeans'].get_paths()]
        xy = np.array(xy)
        axes.vlines(xy[:, 0],
                    ymin=xy[:, 1] - std,
                    ymax=xy[:, 1] + std,
                    color='#473535',
                    lw=3,
                    zorder=1)

        axes.set_xlabel('SWE frames')
        axes.set_ylabel(self.y_labels[swe_var])
        axes.set_title(f'Median: {int(np.median(D))}, '
                       f'Mean: {int(D.mean())}, '
                       f'STD: {int(np.std(D))}')

        figure_canvas.get_tk_widget().pack(side=tk.TOP, fill=tk.BOTH, expand=1)

    def add_scrollbars(self, container):
        sb_x = ttk.Scrollbar(container, orient=tk.HORIZONTAL, command=self.tv.xview)
        sb_y = ttk.Scrollbar(container, orient=tk.VERTICAL, command=self.tv.yview)
        self.tv.configure(xscrollcommand=sb_x.set, yscrollcommand=sb_y.set)
        sb_x.grid(row=4, column=0, sticky='ew')
        sb_y.grid(row=0, column=1, sticky='ns')

    def add_to_file_list(self, path):
        """Add file name and path to list of analysed files"""
        self.files.append((path.name, path.resolve().parent))
        if path.name in self.tv.get_children():
            self.tv.delete(path.name)
        self.tv.insert('', tk.END, values=self.files[-1], iid=path.name)
        self.tv.focus(self.tv.get_children()[-1])

    def file_selected(self, event):
        rows = []
        for selected_item in self.tv.selection():
            item = self.tv.item(selected_item)
            row = item['values']
            rows.append(row)
        if len(rows) == 1:
            name = rows[0][0].split('.')[0]
            path = Path.cwd() / 'src' / f'{rows[0][0]}.pickle'
            self.results = utils.load_pickle(path)
            self.change_plot()

    def export_to(self, format):
        """Export stats for each unique SWE frame
        Args:
            format  (str): extension of exported file (currently csv and xlsx)
        Returns: None
        """
        dir_path = self.results['file'][0]
        name = self.results['file'][1]
        path = dir_path / f'{name}.{format}'
        dfs = pd.DataFrame.from_dict(self.results['stats'])
        if format == 'csv':
            dfs.to_csv(path, index_label='frame')
        if format == 'xlsx':
            dfs.to_excel(path, index_label='frame')


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
