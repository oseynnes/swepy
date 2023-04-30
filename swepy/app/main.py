import tkinter as tk
from pathlib import Path
from tkinter import ttk

from swepy.app import app_utils
from swepy.app.output_frames import FilesPanel, HistoryPanel, SavePanel, FigPanel
from swepy.app.root_widgets import MenuBar
from swepy.app.view_frames import ImgPanel, TopPanel, LeftPanel
from swepy.processing import data_utils
from swepy.processing.data import DcmData
from swepy.processing.io import pickle_io


class View(ttk.Frame):
    """Tab frame displaying and controlling scan display and analysis"""

    def __init__(self, parent):
        super().__init__(parent)

        self.grid(row=0, column=0, rowspan=4, columnspan=2, sticky=tk.NSEW)
        self.columnconfigure(1, weight=4)
        self.rowconfigure(1, weight=4)

        self.block = tk.BooleanVar(self, True)

        self.ds = None
        self.img_array = None
        self.img_name = None
        self.swe_var = tk.StringVar()
        self.set_swe_var()
        self.cmap_loc_var = tk.StringVar()
        self.set_cmap_loc()

        self.controller = None

        self.img_panel = ImgPanel(self)
        self.canvas = self.img_panel.canvas
        self.fov_coords = None
        self.init_roi_coords = None
        self.init_roi_shape = None

        self.top = TopPanel(self)

        self.left_panel = LeftPanel(self)
        self.swe_fhz = None
        self.max_scale = None
        self.left_panel.enter_btn['command'] = self.get_usr_entry
        self.left_panel.reset_roi_btn['command'] = self.reset_rois
        self.left_panel.analyse_btn['command'] = self.process

    def set_swe_var(self):
        swe_var = data_utils.get_settings('SWE_VAR')
        if swe_var:
            self.swe_var.set(swe_var[0])
        else:
            self.swe_var.set('youngs_m')  # set default SWE variable to Young's modulus

    def set_cmap_loc(self):
        cmap_loc = data_utils.get_settings('CMAP_LOC')
        if cmap_loc:
            self.cmap_loc_var.set(cmap_loc[0])
        else:
            self.cmap_loc_var.set('local_cmap')  # set default choice to cmap in image

    def set_controller(self, controller):
        self.controller = controller

    def reset_rois(self):
        """Reset original ROI selection to initial values"""
        self.img_panel.roi_coords = self.init_roi_coords
        self.img_panel.shape.set(self.init_roi_shape)
        self.img_panel.set_rois()

    def process(self):
        """Check requirements and launch analysis"""
        if not all([self.swe_fhz, self.max_scale]):
            app_utils.warn_wrong_entry()
            return
        if self.ds:
            self.controller.analyse()
            self.block.set(False)
        else:
            app_utils.warn_no_video()
            return

    def get_usr_entry(self):
        """Log user entry, re-sample video and save to JSON file"""
        if self.ds:
            self.swe_fhz = app_utils.log_entry('SWE Fhz',
                                               self.left_panel.usr_fhz,
                                               self.left_panel.tv,
                                               'swe_row')
            self.max_scale = app_utils.log_entry('max. scale',
                                                 self.left_panel.usr_scale,
                                                 self.left_panel.tv,
                                                 'scale_row',
                                                 var_type=int)
            if isinstance(self.swe_fhz, (int, float)):
                self.get_swe_frames()
                data_utils.save_usr_input(self.swe_fhz, self.max_scale)
                data_utils.save_swe_var(self.swe_var.get())
            self.canvas.focus_set()
        else:
            app_utils.warn_no_video()
            return

    def get_swe_frames(self):
        """Set GUI to display and analyse SWE unique scans only"""
        self.img_panel.swe_array = self.controller.get_swe_array(self.swe_fhz)
        self.img_panel.current_array = self.img_panel.swe_array
        self.img_panel.ctrl.current_value.set(0)
        self.img_panel.activate_slider(self.img_panel.swe_array.shape[0])
        self.img_panel.ctrl.current_frame = 0
        self.img_panel.ctrl.update_frame()

    def update_dcm_info(self):
        """Populate table with info from DICOM header and json file"""
        self.left_panel.values = (self.ds.PatientName,
                                  data_utils.format_str_datetime(self.ds),
                                  self.ds.NumberOfFrames,
                                  self.ds.Rows,
                                  self.ds.Columns,
                                  data_utils.get_compression_status(self.ds.LossyImageCompression),
                                  self.ds.RecommendedDisplayFrameRate)  # get dcm info
        rows = (zip(self.left_panel.var_names, self.left_panel.values))
        for row in rows:
            self.left_panel.tv.insert(parent='', index=tk.END, values=row)

    def activate_arrowkeys(self):
        """Bind left and right arrow keys to change of image"""
        self.canvas.focus_set()
        self.canvas.bind('<Left>', self.img_panel.ctrl.left_key)
        self.canvas.bind('<Right>', self.img_panel.ctrl.right_key)

    def set_img_name(self):
        self.top.img_name.config(text=self.img_name)

    def load_file(self):
        """Pass variables and scan array to ImgPanel frame, update View frame"""
        self.img_panel.fov_coords = self.fov_coords
        self.img_panel.roi_coords = self.init_roi_coords
        self.img_panel.current_array = self.img_array
        self.img_panel.ctrl.update_frame()
        self.img_panel.activate_slider(self.ds.NumberOfFrames)
        self.img_panel.activate_draw()
        self.update_dcm_info()
        self.set_img_name()
        self.activate_arrowkeys()


class Controller:
    """Routing data between View (GUI) and Data (DICOM) classes"""

    def __init__(self, data, view, output):
        self.data = data
        self.view = view
        self.output = output

    def get_dicom_data(self):
        """Load DICOM data in View frame"""
        self.data.load_dicom()
        self.view.ds = self.data.ds
        self.view.img_array = self.data.img_array
        self.view.img_name = self.data.img_name
        self.view.fov_coords = self.data.top_fov_coords
        self.view.init_roi_coords = self.data.roi_coords
        self.view.load_file()

    def get_swe_array(self, swe_fhz):
        """Call method to get array of SWE unique scans"""
        return self.data.resample(swe_fhz)

    def set_swe_variable(self):
        """Set chosen SWE variable for analysis and plotting"""
        self.data.analysis_swe_var = self.view.swe_var.get()
        self.output.fig_panel.plot_swe_var.set(self.view.swe_var.get())

    def analyse(self):
        """Get data and call methods for analysis and preview"""
        self.data.swe_fhz = self.view.swe_fhz
        self.data.max_scale = self.view.max_scale
        self.set_swe_variable()
        self.view.img_panel.get_top_coords()
        self.data.roi_coords = self.view.img_panel.roi_coords
        self.data.analyse_roi(cmap_loc=self.view.cmap_loc_var.get())
        self.output.results = self.data.results
        self.output.fig_panel.change_plot()
        self.output.update_tv(self.data.path)
        data_utils.pickle_results(self.data.path, self.data.results)


class Output(ttk.Frame):
    """Tab frame displaying analysis output"""

    def __init__(self, parent):
        super().__init__(parent)

        self.grid(row=0, column=0, columnspan=2, rowspan=6, padx=5, pady=5, sticky=tk.NSEW)
        self.columnconfigure(0, weight=1)
        self.columnconfigure(1, weight=3)

        self.results = None

        self.files_panel = FilesPanel(self)
        self.tv_files = []
        self.tv_selection = set()
        self.files_panel.tv.bind('<<TreeviewSelect>>', self.update_tv_selection)

        # self.add_scrollbars(self.files_panel)  # TODO: fix scroll bar

        self.previous = HistoryPanel(self)
        self.previous.load_btn['command'] = self.load_previous
        self.previous.clear_all_btn['command'] = self.clear_results

        self.save_panel = SavePanel(self)

        self.fig_panel = FigPanel(self)

    # def add_scrollbars(self, container):
    #     sb_x = ttk.Scrollbar(container, orient=tk.HORIZONTAL, command=self.files_panel.tv.xview)
    #     sb_y = ttk.Scrollbar(container, orient=tk.VERTICAL, command=self.files_panel.tv.yview)
    #     self.files_panel.tv.configure(xscrollcommand=sb_x.set, yscrollcommand=sb_y.set)
    #     sb_x.grid(row=1, column=0, sticky='ew')
    #     sb_y.grid(row=0, column=1, sticky='ns')

    def update_tv(self, path):
        """Add file name and path to list of analysed files"""
        self.tv_files.append((path.name, path.resolve().parent))
        if path.name in self.files_panel.tv.get_children():
            self.files_panel.tv.delete(path.name)
        self.files_panel.tv.insert('', tk.END, values=self.tv_files[-1], iid=path.name)
        self.files_panel.tv.focus(self.files_panel.tv.get_children()[-1])

    def update_tv_selection(self, event):
        """Update list of selected rows in list of analysed files"""
        self.tv_selection.clear()
        for selected_item in self.files_panel.tv.selection():
            item = self.files_panel.tv.item(selected_item)
            row = item['values']
            self.tv_selection.add(tuple(row))
        rows = list(self.tv_selection)
        name = rows[0][0].split('.')[0] if '.' in rows[0][0] else rows[0][0]  # TODO: fix when clearing output table
        path = Path.cwd().parent / 'src' / 'cache' / f'{name}.pickle'
        self.results = pickle_io.load_pickle(path)
        self.fig_panel.change_plot()

    def clear_results(self):
        self.files_panel.clear_treeview()
        self.fig_panel.clear_figure()
        data_utils.clear_pickle()

    def load_previous(self):
        """Check if cached results exist and load cached results from previous analyses"""
        paths = self.previous.select_cached()
        if paths:
            self.files_panel.load_tv_from_pickle(paths)


class App(tk.Tk):
    """Root window of tkinter app"""

    def __init__(self):
        super().__init__()

        self.title('SwePy')
        self.window_width = 1100
        self.window_height = 760
        app_utils.set_win_geometry(self, self.window_width, self.window_height)
        self.columnconfigure(1, weight=4)
        self.rowconfigure(0, weight=1)  # NB: image only resize up to its size

        self.path = None

        self.mb = MenuBar(self)
        self.config(menu=self.mb)

        self.nb = ttk.Notebook(self)
        self.nb.grid(row=0, column=0, rowspan=4, columnspan=2, sticky=tk.NSEW)
        self.columnconfigure(0, weight=1)
        self.columnconfigure(1, weight=4)
        self.set_img_proc()
        self.output = Output(self.nb)
        self.nb.add(self.view, text='Image processing')
        self.nb.add(self.output, text='Results')

    def set_img_proc(self):
        """Instantiate classes specific to a DICOM file"""

        self.data = DcmData(self.path)
        self.view = View(self.nb)

    def reset(self, path):
        """Reset file processing
        Args:
            path: pathlib path to DICOM file
        Returns: None
        """
        if path:
            self.path = path
            self.nb.forget(self.view)
            self.set_img_proc()
            self.data.path = self.path
            data_utils.save_path(str(self.path.resolve()))
            self.nb.insert(0, self.view, text='Image processing')
            self.nb.select(self.view)
            controller = Controller(self.data, self.view, self.output)
            self.view.set_controller(controller)
            self.display_loading_msg()
            self.update_idletasks()
            self.check_loading_status()
            controller.get_dicom_data()

    def display_loading_msg(self):
        """Display message while file is loading"""
        self.popup = tk.Toplevel(self)
        root_x, root_y = self.winfo_rootx(), self.winfo_rooty()
        offset_w, offset_h = int(self.window_width / 2), int(self.window_height * .3)
        self.popup.geometry(f'+{root_x + offset_w}+{root_y + offset_h}')
        msg = tk.Label(self.popup, text="DICOM file loading", padx=10, pady=10)
        msg.grid(row=0, column=0)

    def check_loading_status(self):
        """Check whether DICOM file is loaded"""
        if self.data.ds:
            self.popup.destroy()
        else:
            self.after(10, self.check_loading_status)

    def paths_handler(self):
        """Handle single/multiple path selection(s)"""
        paths = self.mb.select_files()
        if len(paths) > 0:
            self.reset(paths[0])
            self.wait_variable(self.view.block)
            if len(paths) > 1 and self.view.block.get() is False:
                cached_path = Path.cwd().parent / 'src' / 'cache' / f'{paths[0].stem}.pickle'
                cached_file1 = pickle_io.load_pickle(cached_path)
                roi_coords = cached_file1['roi_coords']
                roi_shape = cached_file1['roi_shape']
                self.view.block.set(True)
                for i, path in enumerate(paths[1:]):
                    self.reset(path)
                    self.view.get_usr_entry()
                    self.view.init_roi_coords = roi_coords  # load detected or user drawn (from 1st file) roi coords
                    self.view.init_roi_shape = roi_shape
                    self.view.reset_rois()
                    self.view.init_roi_coords = self.data.roi_coords  # load detected roi coords for 'reset' button
                    self.wait_variable(self.view.block)
                    self.view.process()
                self.nb.select(self.output)

# if __name__ == '__main__':
#     app = App()
#     app.mainloop()

# TODO: add doctrings to all functions
