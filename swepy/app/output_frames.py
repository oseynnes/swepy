import tkinter as tk
import tkinter.filedialog as fd
from pathlib import Path
from tkinter import ttk

import numpy as np
import pandas as pd
import pandastable
from matplotlib.backends.backend_tkagg import (FigureCanvasTkAgg, NavigationToolbar2Tk)
from matplotlib.figure import Figure

from swepy.processing import data_utils
from swepy.processing.io.pickle_io import load_pickle
from swepy.app.app_utils import warn_empty_cache, warn_no_selection


class FilesPanel(ttk.LabelFrame):
    """Panel of output tab listing analysed files"""

    def __init__(self, parent):
        super().__init__(parent)

        self.config(text='Analysed files')
        self.grid(row=0, column=0, padx=5, pady=5, sticky=tk.NW)

        columns = ('file_name', 'path')
        self.tv = ttk.Treeview(self, columns=columns, show='headings')
        self.tv.heading('file_name', text='File')
        self.tv.column('file_name', minwidth=100)
        self.tv.heading('path', text='Path', anchor=tk.W)
        self.tv.column('path', minwidth=500)
        self.tv.pack(ipadx=5, ipady=5, fill=tk.BOTH, expand=True)
        self.add_scrollbars()

    def add_scrollbars(self):
        self.sb_x = ttk.Scrollbar(self, orient=tk.HORIZONTAL, command=self.tv.xview)
        self.sb_y = ttk.Scrollbar(self, orient=tk.VERTICAL, command=self.tv.yview)
        self.tv.configure(xscrollcommand=self.sb_x.set, yscrollcommand=self.sb_y.set)
        self.sb_x.pack(side='bottom', fill='x')
        self.sb_y.pack(side='right', fill='y')

    def load_tv_from_pickle(self, paths):
        """Load cached results from previous analyses"""
        cached = [load_pickle(path) for path in paths]
        rows = [results['file'] for results in cached]
        for row in rows:
            self.tv.insert('', tk.END, values=row, iid=row[0])

    def clear_treeview(self):
        """Clear table with analysed files"""
        self.tv.delete(*self.tv.get_children())


class HistoryPanel(ttk.LabelFrame):
    """Panel of output tab holding commands to access/delete cached previous results"""

    def __init__(self, parent):
        super().__init__(parent)

        self.output = parent

        self.config(text='Previous results')
        self.grid(row=1, column=0, padx=5, pady=5, sticky=tk.EW)

        self.load_btn = ttk.Button(self, text='Load')
        self.load_btn.grid(column=0, row=0, sticky=tk.W, padx=5, pady=5)

        self.clear_all_btn = ttk.Button(self, text='Clear all')
        self.clear_all_btn.grid(column=2, row=0, sticky=tk.E, padx=5, pady=5)

    @staticmethod
    def select_cached():
        """Retrieve cached results files if there are any"""
        filetypes = (('Cached files', '*.pickle'),)
        initialdir = Path.cwd().parent / 'src' / 'cache'
        paths = fd.askopenfilenames(initialdir=initialdir, title="Select file(s)", filetypes=filetypes)
        if paths:
            return paths
        else:
            warn_empty_cache()
            return


class SavePanel(ttk.LabelFrame):
    """Panel of output tab holding commands to save data"""

    def __init__(self, parent):
        super().__init__(parent)

        self.output = parent

        self.config(text='Save selection to')
        self.grid(row=2, column=0, padx=5, pady=5, sticky=tk.EW)

        self.csv_btn = ttk.Button(self, text='CSV')
        self.csv_btn.grid(column=0, row=0, sticky=tk.W, padx=5, pady=5)
        self.xlsx_btn = ttk.Button(self, text='Excel')
        self.xlsx_btn.grid(column=1, row=0, sticky=tk.E, padx=5, pady=5)
        self.csv_btn['command'] = lambda: self.export('csv',
                                                      list(self.output.tv_selection),
                                                      everything=False)
        self.xlsx_btn['command'] = lambda: self.export('xlsx',
                                                       list(self.output.tv_selection),
                                                       everything=False)

    def export(self, file_format, selection=None, everything=True):
        """Export stats for each unique SWE frame
        Args:
            file_format (str): extension of exported file (currently csv and xlsx)
            selection (list): rows selected in treeview
            everything:
        Returns: None
        """
        all_rows = [self.output.files_panel.tv.item(child)['values']
                    for child in self.output.files_panel.tv.get_children()]
        rows = all_rows if everything else selection
        if rows:
            for row in rows:
                name = row[0].split('.')[0]
                import_path = Path.cwd().parent / 'src' / 'cache' / f'{name}.pickle'
                results = load_pickle(import_path)
                export_path = Path(row[1]) / f'{name}.{file_format}'  # TODO: make results folder if it does not exists
                dfs = pd.DataFrame.from_dict(results['stats'])
                if file_format == 'csv':
                    dfs.to_csv(export_path, index_label='frame')
                if file_format == 'xlsx':
                    dfs.to_excel(export_path, index_label='frame')
        else:
            warn_no_selection()
            return


class FigPanel(ttk.Frame):
    """Panel of output tab holding preview figure"""

    def __init__(self, parent):
        super().__init__(parent)

        self.output = parent

        self.grid(row=0, column=1, rowspan=5, padx=5, pady=5, sticky=tk.NSEW)

        self.lf0 = ttk.LabelFrame(self, text='Preview')
        self.lf0.pack(ipadx=5, ipady=5, fill=tk.X)
        self.figure = Figure()
        self.figure_canvas = FigureCanvasTkAgg(self.figure, self.lf0)
        NavigationToolbar2Tk(self.figure_canvas, self.lf0)
        self.figure_canvas.get_tk_widget().pack(side=tk.TOP, fill=tk.BOTH, expand=1)

        self.lf1 = ttk.LabelFrame(self, text='Variable', labelanchor='w')
        self.lf1.pack(ipadx=5, ipady=5, fill=tk.X)
        self.plot_swe_var = tk.StringVar()
        self.plot_swe_var.set('youngs_m')
        self.y_labels = {'velocity': 'Wave velocity (m/s)',
                         'shear_m': 'Shear modulus (KPa)',
                         'youngs_m': "Young's modulus (KPa"}
        grid_column = 0
        for key, label in self.y_labels.items():
            radio = ttk.Radiobutton(self.lf1,
                                    text=label,
                                    value=key,
                                    command=self.change_plot,
                                    variable=self.plot_swe_var)
            radio.grid(column=grid_column, row=0, ipadx=10, ipady=10)
            grid_column += 1

        self.results_btn_frame = ttk.Frame(self)
        self.results_btn_frame.pack()
        self.results_btn = ttk.Button(self.results_btn_frame, text='Display in table', command=self.display_results)
        self.results_btn.grid(row=0, column=1, padx=5, pady=5, sticky=tk.NSEW)

        # TODO: Add figure with colour analysis

    def change_plot(self):
        """Load results and call function to refresh plot"""
        if self.output.results is None:
            return
        D = self.output.results['raw'][self.plot_swe_var.get()]
        self.replot_data(D, self.plot_swe_var.get())

    def replot_data(self, D, swe_var):
        """Reset app to plot new data
        Args:
            D: data 3D array of shape (n frames, height, width).
            swe_var: variable to calculate, can only be either 'velocity', 'shear_m' or 'youngs_m'
        Returns: None
        """

        swe_vars = ['velocity', 'shear_m', 'youngs_m']
        assert (swe_var in swe_vars), "'swe_var' can only be 'velocity', 'shear_m' or 'youngs_m'"
        # self.plot_swe_var.set(swe_var)
        frame_dim = D.shape[0]
        plot_data = D.reshape(frame_dim, -1)

        self.figure.clear()
        axes = self.figure.add_subplot()
        if np.nanmean(D) > 0:
            data_lists = [x for x in plot_data.tolist()]
            filtered_lists = data_utils.filter_nans(data_lists)
            vp = axes.violinplot(filtered_lists,
                                 widths=1,
                                 showmeans=True,
                                 showmedians=True,
                                 showextrema=False)

            for body in vp['bodies']:
                body.set_facecolor('navy')
                body.set_alpha(.5)
                body.set_edgecolor('#473535')

            vp['cmeans'].set_color('orange')
            vp['cmedians'].set_color('white')

            std = np.nanstd(D, axis=1)
            xy = [[l.vertices[:, 0].mean(), l.vertices[0, 1]] for l in vp['cmeans'].get_paths()]
            xy = np.array(xy)
            axes.scatter(xy[:, 0], xy[:, 1], s=20, c="orange", marker="o", zorder=3)
            axes.vlines(xy[:, 0],
                        ymin=xy[:, 1] - std,
                        ymax=xy[:, 1] + std,
                        color='#473535',
                        lw=3,
                        zorder=1)

            axes.set_xlabel('SWE frames')
            axes.set_ylabel(self.y_labels[swe_var])
            axes.set_title(f"{self.output.results['file'][0]}, "
                           f"Median: {round(np.nanmedian(D), 2)}, "
                           f"Mean: {round(np.nanmean(D), 2)}, "
                           f"STD: {round(np.nanstd(D), 2)}")

        self.figure_canvas.draw_idle()

    def clear_figure(self):
        for widget in self.lf0.winfo_children():
            widget.destroy()

    def display_results(self):
        """Display results in a popup table"""
        # adapted from https://stackoverflow.com/a/71827719/13147488
        if not self.output.results:
            return
        else:
            res_dict = self.output.results['stats']
            df = pd.DataFrame.from_dict(res_dict)
        table_frame = tk.Toplevel(self)
        table_frame.title(self.output.results['file'][0])
        root_x, root_y = self.winfo_rootx(), self.winfo_rooty()
        offset_w = int(self.winfo_width())
        table_frame.geometry(f'+{root_x + offset_w}+{root_y}')
        tk.Label(table_frame, text="Results").grid(row=0, column=1, columnspan=3)
        table = pandastable.Table(table_frame, dataframe=df)
        table.show()
