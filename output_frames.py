import tkinter as tk
import tkinter.filedialog as fd
from pathlib import Path
from tkinter import ttk

import numpy as np
import pandas as pd
from matplotlib.backends.backend_tkagg import (FigureCanvasTkAgg,
                                               NavigationToolbar2Tk)
from matplotlib.figure import Figure

import utils


class FilesPanel(ttk.LabelFrame):
    """Panel of output tab listing analysed files"""

    def __init__(self, parent):
        super().__init__(parent)

        self.config(text='Analysed files')
        self.grid(row=0, column=0, padx=5, pady=5, sticky=tk.NSEW)

        columns = ('file_name', 'path')
        self.tv = ttk.Treeview(self, columns=columns, show='headings')
        self.tv.heading('file_name', text='File')
        self.tv.column('file_name', width=100)
        self.tv.heading('path', text='Path')
        self.tv.column('path', width=200)
        self.tv.grid(row=0, column=0, padx=5, pady=5, sticky=tk.NSEW)

    def load_tv_from_pickle(self, paths):
        cached = [utils.load_pickle(path) for path in paths]
        rows = [results['file'] for results in cached]
        for row in rows:
            self.tv.insert('', tk.END, values=row, iid=row[0])

    def clear_treeview(self):
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
        filetypes = (('Cached files', '*.pickle'),)
        initialdir = Path.cwd() / 'src' / 'cache'
        paths = fd.askopenfilenames(initialdir=initialdir, title="Select file(s)", filetypes=filetypes)
        if paths:
            return paths
        else:
            utils.warn_empty_cache()
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
                import_path = Path.cwd() / 'src' / 'cache' / f'{name}.pickle'
                results = utils.load_pickle(import_path)
                export_path = Path(row[1]) / f'{name}.{file_format}'  # TODO: make results folder if it does not exists
                dfs = pd.DataFrame.from_dict(results['stats'])
                if file_format == 'csv':
                    dfs.to_csv(export_path, index_label='frame')
                if file_format == 'xlsx':
                    dfs.to_excel(export_path, index_label='frame')
        else:
            utils.warn_no_selection()
            return


class FigPanel(ttk.Frame):
    """Panel of output tab holding preview figure"""

    def __init__(self, parent):
        super().__init__(parent)

        self.output = parent

        self.grid(row=0, column=1, rowspan=4, padx=5, pady=5, sticky=tk.NSEW)

        self.lf0 = ttk.LabelFrame(self, text='Preview')
        self.lf0.grid(row=0, column=1, rowspan=3, padx=5, pady=5, sticky=tk.NSEW)

        self.lf1 = ttk.LabelFrame(self, text='Variable')
        self.lf1.grid(row=4, column=1, padx=5, pady=5, sticky=tk.NSEW)
        self.label_var = tk.StringVar()
        self.label_var.set('youngs_m')
        self.y_labels = {'velocity': 'Wave velocity (m/s)',
                         'shear_m': 'Shear modulus (KPa)',
                         'youngs_m': "Young's modulus (KPa"}
        grid_column = 0
        for key, label in self.y_labels.items():
            radio = ttk.Radiobutton(self.lf1,
                                    text=label,
                                    value=key,
                                    command=self.change_plot,
                                    variable=self.label_var)
            radio.grid(column=grid_column, row=0, ipadx=10, ipady=10)
            grid_column += 1

        self.replot_data(D=np.zeros([1, 600, 600]), swe_var='youngs_m')

    def change_variable(self):
        self.var = self.label_var.get()

    def change_plot(self):
        if self.output.results is None:
            return
        self.change_variable()
        D = self.output.results['raw'][self.var]
        self.replot_data(D, self.var)

    def replot_data(self, D, swe_var):
        """Reset widgets to plot new data
        Args:
            D: data 3D array of shape (n frames, height, width).
        Returns: None
        """
        for widget in self.lf0.winfo_children():
            widget.destroy()
        swe_vars = ['velocity', 'shear_m', 'youngs_m']
        assert (swe_var in swe_vars), "'swe_var' can only be 'velocity', 'shear_m' or 'youngs_m'"
        self.label_var.set(swe_var)
        self.change_variable()
        frame_dim = D.shape[0]
        plot_data = D.reshape(frame_dim, -1)

        figure = Figure(figsize=(6, 4), dpi=100)
        figure_canvas = FigureCanvasTkAgg(figure, self.lf0)
        NavigationToolbar2Tk(figure_canvas, self.lf0)
        axes = figure.add_subplot()

        if np.mean(D) > 0:
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
            axes.set_title(f"{self.output.results['file'][0]}, "
                           f"Median: {int(np.median(D))}, "
                           f"Mean: {int(D.mean())}, "
                           f"STD: {int(np.std(D))}")

        figure_canvas.get_tk_widget().pack(side=tk.TOP, fill=tk.BOTH, expand=1)

    def clear_figure(self):
        for widget in self.lf0.winfo_children():
            widget.destroy()
