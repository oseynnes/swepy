import tkinter as tk
from pathlib import Path
from tkinter import ttk

import utils
from output_frames import FilesPanel, HistoryPanel, SavePanel, FigPanel
from processing import Data
from root_widgets import MenuBar
from view_frames import ImgPanel, TopPanel, LeftPanel


class View(ttk.Frame):
    """Tab frame displaying and controlling scan display and analysis"""

    def __init__(self, parent):
        super().__init__(parent)

        self.grid(row=0, column=0, rowspan=4, columnspan=2, sticky=tk.NSEW)
        self.columnconfigure(1, weight=4)
        self.rowconfigure(1, weight=4)

        self.ds = None
        self.img_array = None
        self.img_name = None

        self.controller = None

        self.img_panel = ImgPanel(self)
        self.canvas = self.img_panel.canvas
        self.fov_coords = None
        self.init_roi_coords = None

        self.top = TopPanel(self)

        self.left_panel = LeftPanel(self)
        self.swe_fhz = None
        self.max_scale = None
        self.left_panel.enter_btn['command'] = self.get_usr_entry
        self.left_panel.reset_roi_btn['command'] = self.reset_rois
        self.left_panel.analyse_btn['command'] = self.analyse

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
        """Set GUI to display and analyse SWE unique scans only"""
        self.img_panel.swe_array = self.controller.get_swe_array(self.swe_fhz)
        self.img_panel.current_array = self.img_panel.swe_array
        self.img_panel.ctrl.current_value.set(0)
        self.img_panel.activate_slider(self.img_panel.swe_array.shape[0])
        self.img_panel.ctrl.current_frame = 0
        self.img_panel.ctrl.update_frame()

    def update_dcm_info(self):
        """Populate table with info from dicom header and json file"""
        self.left_panel.values = (self.ds.NumberOfFrames,
                                  self.ds.Rows,
                                  self.ds.Columns,
                                  self.ds.RecommendedDisplayFrameRate)  # get dcm info
        rows = (zip(self.left_panel.variables, self.left_panel.values))
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
    """Routing data between View (GUI) and Data (dicom) classes"""

    def __init__(self, data, view, output):
        self.data = data
        self.view = view
        self.output = output

    def get_dicom_data(self):
        """Load dicom data in View frame"""

        # TODO: link to a ttk.Progressbar widget (dicom loading is a few seconds)
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

    def analyse(self):
        """Get data and call methods for analysis and preview"""

        if not all([self.view.swe_fhz, self.view.max_scale]):
            utils.warn_wrong_entry()
            return
        self.data.swe_fhz = self.view.swe_fhz
        self.data.max_scale = self.view.max_scale
        self.data.roi_coords = self.view.img_panel.roi_coords
        self.data.analyse_roi(self.data.get_rois())
        self.output.results = self.data.results
        self.output.fig_panel.replot_data(self.data.results['raw'][self.data.source_var],
                                          self.data.source_var)
        self.output.update_tv(self.data.path)
        utils.pickle_results(self.data.path, self.data.results)


class Output(ttk.Frame):
    """Tab frame displaying analysis output"""

    def __init__(self, parent):
        super().__init__(parent)

        self.app = parent

        self.grid(row=0, column=0, columnspan=2, rowspan=6, padx=5, pady=5, sticky=tk.NSEW)
        self.columnconfigure(0, weight=1)
        self.columnconfigure(1, weight=3)

        self.results = None

        self.files_panel = FilesPanel(self)
        self.tv_files = []
        self.tv_selection = set()
        self.files_panel.tv.bind('<<TreeviewSelect>>', self.update_tv_selection)

        self.add_scrollbars(self.files_panel)  # TODO: fix scroll bar

        self.previous = HistoryPanel(self)
        self.previous.load_btn['command'] = self.load_previous
        self.previous.clear_all_btn['command'] = self.clear_all

        self.save_panel = SavePanel(self)

        self.fig_panel = FigPanel(self)

    def add_scrollbars(self, container):
        sb_x = ttk.Scrollbar(container, orient=tk.HORIZONTAL, command=self.files_panel.tv.xview)
        sb_y = ttk.Scrollbar(container, orient=tk.VERTICAL, command=self.files_panel.tv.yview)
        self.files_panel.tv.configure(xscrollcommand=sb_x.set, yscrollcommand=sb_y.set)
        sb_x.grid(row=1, column=0, sticky='ew')
        sb_y.grid(row=0, column=1, sticky='ns')

    def update_tv(self, path):
        """Add file name and path to list of analysed files"""
        self.tv_files.append((path.name, path.resolve().parent))
        if path.name in self.files_panel.tv.get_children():
            self.files_panel.tv.delete(path.name)
        self.files_panel.tv.insert('', tk.END, values=self.tv_files[-1], iid=path.name)
        self.files_panel.tv.focus(self.files_panel.tv.get_children()[-1])

    def update_tv_selection(self, event):
        """Update list of selected rows in list of analysed files"""
        for selected_item in self.files_panel.tv.selection():
            item = self.files_panel.tv.item(selected_item)
            row = item['values']
            self.tv_selection.add(tuple(row))
        rows = list(self.tv_selection)
        name = rows[0][0].split('.')[0]
        path = Path.cwd() / 'src' / 'cache' / f'{name}.pickle'
        self.results = utils.load_pickle(path)
        self.fig_panel.change_plot()

    def clear_all(self):
        self.files_panel.clear_treeview()
        self.fig_panel.clear_figure()
        utils.clear_pickle()

    def load_previous(self):
        """Load cached results from previous analyses"""
        paths = self.previous.select_cached()
        self.files_panel.load_tv_from_pickle(paths)


class App(tk.Tk):
    """Root window of tkinter app"""

    def __init__(self):
        super().__init__()

        self.title('SwePy')
        window_width = 990
        window_height = 690
        utils.set_win_geometry(self, window_width, window_height)
        self.columnconfigure(1, weight=4)
        self.rowconfigure(0, weight=1)  # NB: image only resize up to its size

        self.path = None

        self.mb = MenuBar(self)
        self.config(menu=self.mb)

        self.nb = ttk.Notebook(self)
        self.nb.grid(row=0, column=0, rowspan=4, columnspan=2, sticky=tk.NSEW)
        self.columnconfigure(0, weight=1)
        self.columnconfigure(1, weight=4)
        self.load_file()
        self.output = Output(self.nb)
        self.nb.add(self.view, text='Image processing')
        self.nb.add(self.output, text='Results')

    def load_file(self):
        """Instantiate classes specific to a dicom file"""

        self.data = Data(self.path)
        self.view = View(self.nb)

    def reset(self, path=None):
        """Reset file processing
        Args:
            path: pathlib path to dicom file
        Returns: None
        """

        self.path = path if path else self.mb.select_file()
        if self.path:
            self.nb.forget(self.view)
            self.load_file()
            self.data.path = self.path
            self.nb.insert(0, self.view, text='Image processing')
            self.nb.select(self.view)
            controller = Controller(self.data, self.view, self.output)
            self.view.set_controller(controller)
            controller.get_dicom_data()
        else:
            return


if __name__ == '__main__':
    app = App()
    app.mainloop()

    # TODO: - add doctrings to all functions
