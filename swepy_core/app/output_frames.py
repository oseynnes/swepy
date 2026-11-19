import tkinter as tk
import tkinter.filedialog as fd
from pathlib import Path
from tkinter import ttk
from tkinter.messagebox import showerror, showinfo

import numpy as np
import pandas as pd
import pandastable
from matplotlib.backends.backend_tkagg import (FigureCanvasTkAgg, NavigationToolbar2Tk)
from matplotlib.figure import Figure

from swepy_core.processing import data_utils, summary
from swepy_core.processing.io.pickle_io import load_pickle, save_pickle
from swepy_core.app.app_utils import get_ui_scale, text_width, warn_empty_cache, warn_no_selection
from swepy_core.app.value_map import ValueMapWindow


HIGHLIGHT = 'FFF2CC'  # Excel fill colour of the main result


def main_result_names(results):
    """Names of summary rows and per-map columns holding the main result of a recording"""
    measured = summary.measured_var(results)
    rows = ['main_result', 'main_result_description']
    columns = [f'{measured}_median'] if measured else []
    return rows, columns


def highlight_excel(sheet, df, names, by_rows=False, index_col=False):
    """Highlight the main result in an exported Excel sheet (bold, coloured)
    Args:
        sheet: openpyxl worksheet the table df was written to (header in row 1)
        df: written table
        names (list): names of rows (first column) or columns to highlight
        by_rows (bool): highlight rows whose first cell is in names, else columns named in names
        index_col (bool): whether the sheet starts with an index column
    """
    from openpyxl.styles import Font, PatternFill
    fill, bold = PatternFill('solid', start_color=HIGHLIGHT), Font(bold=True)
    if by_rows:
        for row, name in enumerate(df.iloc[:, 0], start=2):
            if name in names:
                for col in range(1, df.shape[1] + 1):
                    sheet.cell(row=row, column=col).fill = fill
                    sheet.cell(row=row, column=col).font = bold
    else:
        for col, name in enumerate(df.columns, start=2 if index_col else 1):
            if name in names:
                for row in range(1, df.shape[0] + 2):
                    sheet.cell(row=row, column=col).fill = fill
                sheet.cell(row=1, column=col).font = bold


def display_frame(df):
    """Table converted to text for display (pandastable fails on missing values with recent pandas):
    missing values as empty cells, numbers with 4 significant digits"""
    def fmt(v):
        if v is None or (isinstance(v, (float, np.floating)) and np.isnan(v)):
            return ''
        if isinstance(v, (float, np.floating)):
            return f'{v:.4g}'
        return str(v)
    return pd.DataFrame({col: [fmt(v) for v in df[col]] for col in df.columns}, dtype=object)


class FilesPanel(ttk.LabelFrame):
    """Panel of output tab listing analysed files"""

    def __init__(self, parent):
        super().__init__(parent)

        self.config(text='Analysed files', padding=5)
        self.grid(row=0, column=0, padx=5, pady=5, sticky=tk.NSEW)

        columns = ('file_name', 'path')
        self.tv = ttk.Treeview(self, columns=columns, show='headings', height=3)
        self.tv.heading('file_name', text='File', anchor=tk.W)
        self.tv.column('file_name', width=text_width('C0000000.dcm'), minwidth=60, stretch=False)
        self.tv.heading('path', text='Path', anchor=tk.W)
        # path column scrolls horizontally rather than forcing a very wide window
        self.tv.column('path', width=text_width('x' * 30), minwidth=100, stretch=True)
        self.add_scrollbars()  # NB: scrollbars packed first, so they are never squeezed out
        self.tv.pack(fill=tk.BOTH, expand=True)

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
            if self.tv.exists(row[0]):  # already listed
                continue
            self.tv.insert('', tk.END, values=row, iid=row[0])

    def clear_treeview(self):
        """Clear table with analysed files"""
        self.tv.delete(*self.tv.get_children())


class HistoryPanel(ttk.LabelFrame):
    """Panel of output tab holding commands to access/delete cached previous results"""

    def __init__(self, parent):
        super().__init__(parent)

        self.output = parent

        self.config(text='Previous results', padding=5)
        self.grid(row=1, column=0, padx=5, pady=5, sticky=tk.EW)
        self.columnconfigure(1, weight=1)

        self.load_btn = ttk.Button(self, text='Load')
        self.load_btn.grid(column=0, row=0, sticky=tk.W, padx=5, pady=5)

        self.clear_all_btn = ttk.Button(self, text='Clear all')
        self.clear_all_btn.grid(column=2, row=0, sticky=tk.E, padx=5, pady=5)

    @staticmethod
    def select_cached():
        """Retrieve cached results files if there are any"""
        filetypes = (('Cached files', '*.pickle'),)
        initialdir = data_utils.get_cache_dir()
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

        self.config(text='Save selection to', padding=5)
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
        self.combine_btn = ttk.Button(self, text='Combine selection...', command=self.export_combined)
        self.combine_btn.grid(column=0, row=1, columnspan=2, sticky=tk.W, padx=5, pady=(0, 5))

    def export(self, file_format, selection=None, everything=True):
        """Export summary and per-map statistics of each analysed file, next to the DICOM file
        (Excel: one file with 'summary' and 'per_map' sheets; CSV: <name>.csv and <name>_summary.csv)
        Args:
            file_format (str): extension of exported file (currently csv and xlsx)
            selection (list): rows selected in treeview
            everything (bool): export all analysed files rather than the selection
        Returns: None
        """
        all_rows = [self.output.files_panel.tv.item(child)['values']
                    for child in self.output.files_panel.tv.get_children()]
        rows = all_rows if everything else selection
        if not rows:
            warn_no_selection()
            return
        exported = []
        for row in rows:
            import_path = data_utils.get_cached_results_path(row[0])
            name = import_path.stem
            results = load_pickle(import_path)
            per_map = summary.per_map_table(results)
            summary_df = summary.summary_table(results)
            export_path = Path(row[1]) / f'{name}.{file_format}'
            if file_format == 'csv':
                per_map.to_csv(export_path, index_label='map')
                summary_df.to_csv(Path(row[1]) / f'{name}_summary.csv', index=False)
            if file_format == 'xlsx':
                with pd.ExcelWriter(export_path, engine='openpyxl') as writer:
                    summary_df.to_excel(writer, sheet_name='summary', index=False)
                    per_map.to_excel(writer, sheet_name='per_map', index_label='map')
                    rows, columns = main_result_names(results)
                    highlight_excel(writer.sheets['summary'], summary_df, rows, by_rows=True)
                    highlight_excel(writer.sheets['per_map'], per_map, columns, index_col=True)
            exported.append(export_path.name)
        showinfo(title='Export', message=f'Exported {len(exported)} file(s), next to the DICOM files:\n'
                                         + '\n'.join(exported))

    def export_combined(self):
        """Export one table combining the summaries of the selected files (e.g. repeated acquisitions
        of one condition), with mean, SD and CV% between files"""
        tv = self.output.files_panel.tv
        rows = [tv.item(item)['values'] for item in tv.selection()]
        if not rows:
            warn_no_selection()
            return
        path = fd.asksaveasfilename(title='Save combined summary',
                                    initialdir=Path(rows[0][1]),
                                    initialfile='combined_summary.xlsx',
                                    defaultextension='.xlsx',
                                    filetypes=(('Excel', '*.xlsx'), ('CSV', '*.csv')))
        if not path:
            return
        results = [load_pickle(data_utils.get_cached_results_path(row[0])) for row in rows]
        combined = summary.combine(results)
        if Path(path).suffix.lower() == '.csv':
            combined.to_csv(path, index=False)
        else:
            with pd.ExcelWriter(path, engine='openpyxl') as writer:
                combined.to_excel(writer, index=False, sheet_name='combined')
                highlight_excel(writer.sheets['combined'], combined, ['main_result', 'main_result_description'])


class QualityPanel(ttk.LabelFrame):
    """Panel of output tab to set quality filters, and re-apply them to all analysed files"""

    labels = {'max_void_pct': 'Max. void pixels (% of ROI)',
              'max_saturated_pct': 'Max. saturated pixels (% of ROI)',
              'ignore_first_s': 'Ignore maps in the first (s)'}

    def __init__(self, parent):
        super().__init__(parent, text='Quality filters (per SWE map)', padding=5)

        self.output = parent
        self.grid(row=3, column=0, padx=5, pady=5, sticky=tk.EW)
        self.columnconfigure(0, weight=1)

        quality = summary.get_quality_settings()
        validate = (self.register(self.is_positive_number), '%P')
        self.vars = {}
        for row, (key, label) in enumerate(self.labels.items()):
            ttk.Label(self, text=label).grid(row=row, column=0, sticky=tk.W, pady=1)
            var = tk.StringVar(value=f'{quality[key]:g}')
            ttk.Entry(self, width=6, textvariable=var, validate='key',
                      validatecommand=validate).grid(row=row, column=1, sticky=tk.E, pady=1)
            self.vars[key] = var
        self.defaults_btn = ttk.Button(self, text='Defaults', command=self.reset_defaults)
        self.defaults_btn.grid(row=3, column=0, sticky=tk.W, pady=(5, 0))
        self.apply_btn = ttk.Button(self, text='Apply', command=self.apply)
        self.apply_btn.grid(row=3, column=1, sticky=tk.E, pady=(5, 0))

    @staticmethod
    def is_positive_number(value):
        """Validate entry of a positive number (empty allowed while typing)"""
        if value == '':
            return True
        try:
            return float(value) >= 0
        except ValueError:
            return False

    def reset_defaults(self):
        for key, var in self.vars.items():
            var.set(f'{summary.DEFAULT_QUALITY[key]:g}')

    def apply(self):
        """Save filters, and re-apply them to all analysed files (and to future analyses)"""
        try:
            quality = {key: float(var.get()) for key, var in self.vars.items()}
        except ValueError:
            showerror(title='Wrong input', message='Please enter a number in each quality filter field')
            return
        for key, value in quality.items():
            data_utils.set_setting(key.upper(), [value])
        tv = self.output.files_panel.tv
        for item in tv.get_children():
            path = data_utils.get_cached_results_path(tv.item(item)['values'][0])
            if path.exists():
                save_pickle(summary.apply_quality(load_pickle(path), quality), path)
        if self.output.results:
            summary.apply_quality(self.output.results, quality)
            self.output.fig_panel.change_plot()


class FigPanel(ttk.Frame):
    """Panel of output tab holding preview figure"""

    def __init__(self, parent):
        super().__init__(parent)

        self.output = parent

        self.grid(row=0, column=1, rowspan=6, padx=5, pady=5, sticky=tk.NSEW)

        # Plot controls go in the left column of the Results tab (under the save buttons),
        # so the figure can use all the remaining space and shrink on small screens
        self.lf1 = ttk.LabelFrame(self.output, text='Variable', padding=5)
        self.lf1.grid(row=4, column=0, padx=5, pady=5, sticky=tk.EW)
        self.results_btn_frame = ttk.Frame(self.output)
        self.results_btn_frame.grid(row=5, column=0, padx=5, pady=5, sticky=tk.EW)

        self.lf0 = ttk.LabelFrame(self, text='Preview', padding=5)
        self.lf0.pack(side=tk.TOP, fill=tk.BOTH, expand=True)
        # match figure resolution to display scaling, so plot text is readable on HiDPI screens
        self.figure = Figure(figsize=(6, 4), dpi=100 * get_ui_scale(self), layout='constrained')
        self.figure_canvas = FigureCanvasTkAgg(self.figure, self.lf0)
        NavigationToolbar2Tk(self.figure_canvas, self.lf0)
        self.figure_canvas.get_tk_widget().pack(side=tk.TOP, fill=tk.BOTH, expand=1)

        self.plot_swe_var = tk.StringVar()
        self.plot_swe_var.set('youngs_m')
        self.y_labels = {'velocity': 'Wave velocity (m/s)',
                         'shear_m': 'Shear modulus (kPa)',
                         'youngs_m': "Young's modulus (kPa)"}
        grid_row = 0
        for key, label in self.y_labels.items():
            radio = ttk.Radiobutton(self.lf1,
                                    text=label,
                                    value=key,
                                    command=self.change_plot,
                                    variable=self.plot_swe_var)
            radio.grid(column=0, row=grid_row, sticky=tk.W, pady=2)
            grid_row += 1

        # plot type: time course of per-map medians (default) or distribution of values in each map
        ttk.Separator(self.lf1).grid(column=0, row=grid_row, sticky=tk.EW, pady=4)
        view_frame = ttk.Frame(self.lf1)
        view_frame.grid(column=0, row=grid_row + 1, sticky=tk.W)
        ttk.Label(view_frame, text='Plot:').pack(side=tk.LEFT)
        saved_view = data_utils.get_settings('PLOT_VIEW')
        self.plot_view = tk.StringVar(value=saved_view[0] if saved_view else 'time')
        for value, text in (('time', 'Time course'), ('violin', 'Distributions')):
            ttk.Radiobutton(view_frame, text=text, value=value, variable=self.plot_view,
                            command=self.change_view).pack(side=tk.LEFT, padx=(5, 0))

        self.results_btn = ttk.Button(self.results_btn_frame, text='Display in table', command=self.display_results)
        self.results_btn.grid(row=0, column=0, padx=5, sticky=tk.W)
        self.map_btn = ttk.Button(self.results_btn_frame, text='Value map', command=self.show_value_map)
        self.map_btn.grid(row=0, column=1, padx=5, sticky=tk.W)

    def change_view(self):
        data_utils.set_setting('PLOT_VIEW', [self.plot_view.get()])
        self.change_plot()

    def change_plot(self):
        """Load results and call function to refresh plot"""
        if self.output.results is None:
            return
        self.replot_data(self.output.results, self.plot_swe_var.get())

    def replot_data(self, results, swe_var):
        """Plot per-map results: time course of medians (default) or distribution of values in each map
        Args:
            results (dict): analysis results
            swe_var: variable to plot, can only be either 'velocity', 'shear_m' or 'youngs_m'
        Returns: None
        """
        assert swe_var in summary.SWE_VARS, "'swe_var' can only be 'velocity', 'shear_m' or 'youngs_m'"
        stats = results['stats']
        values = results['raw'][swe_var]
        n_maps = values.shape[0]
        included = np.asarray(stats.get('included', np.ones(n_maps, dtype=bool)), dtype=bool)
        reasons = np.asarray(stats.get('exclusion_reason', [''] * n_maps), dtype=object)
        summ = summary.summarise(results)
        unit = summary.UNITS[swe_var]
        mean_of_medians = summ[f'{swe_var}_mean_of_map_medians']
        show_reference = 'reference_median' in stats and swe_var == summary.measured_var(results)

        self.figure.clear()
        axes = self.figure.add_subplot()
        if self.plot_view.get() == 'violin':
            x, medians = self._plot_distributions(axes, values, included)
        else:
            x, medians = self._plot_time_course(axes, results, values, included, show_reference)
        if np.isfinite(mean_of_medians):
            axes.axhline(mean_of_medians, color='C1' if self.plot_view.get() == 'violin' else 'C0', ls='--', lw=1,
                         label=f'mean of map medians ({mean_of_medians:.2f} {unit})')
        self._annotate_exclusions(axes, x, medians, included, reasons)
        axes.set_ylabel(self.y_labels[swe_var])
        axes.legend(fontsize='small', loc='best')

        title = f"{results['file'][0]}\n"
        if summ['n_maps_included']:
            title += (f"Mean of map medians: {mean_of_medians:.2f} {unit}  "
                      f"(SD between maps {summ[f'{swe_var}_SD_between_maps']:.2f}, "
                      f"CV {summ[f'{swe_var}_CV%_between_maps']:.1f}%)  |  "
                      f"{summ['n_maps_included']}/{summ['n_maps']} maps")
        else:
            title += 'No map passed the quality filters'
        if summ.get('reference_mean_of_map_medians') is not None and show_reference:
            title += (f"\nMuscle reference: {summ['reference_mean_of_map_medians']:.2f} {unit}  "
                      f"(ratio {summ.get('main_to_reference_ratio', float('nan')):.2f})")
        axes.set_title(title, fontsize='medium')
        if summ.get('apo_edge_warning'):  # concerns this recording: shown as a warning
            axes.text(.01, .98, f"Aponeurosis {summ['apo_min_edge_distance_mm']:.1f} mm from the SWE box edge "
                                f"(edge artefacts possible).",
                      transform=axes.transAxes, va='top', fontsize='small', color='firebrick')
        if summ.get('scale_warning'):     # resolution of the colour scale: a recommendation for future recordings
            # below the x axis label, so it never overlaps the data
            axes.annotate(f"Note: few colour levels of the scale are used (median level "
                          f"{summ['median_colour_level']:.0f} of {summ['colour_levels_in_scale']}).\n"
                          f"For future recordings, a lower max. scale would give a finer resolution.",
                          xy=(0.5, 0), xycoords=axes.xaxis.label, xytext=(0, -4), textcoords='offset points',
                          ha='center', va='top', fontsize='x-small', color='dimgrey', style='italic')
        self.figure_canvas.draw_idle()

    @staticmethod
    def _plot_time_course(axes, results, values, included, show_reference):
        """Per-map median over time, with spread within each map (IQR) and the muscle reference
        Returns: x positions and medians of the maps"""
        stats = results['stats']
        n_maps = values.shape[0]
        if 'time_s' in stats:
            x = np.asarray(stats['time_s'], dtype=float)
            axes.set_xlabel('time (s)')
        else:  # results from older versions
            x = np.arange(1, n_maps + 1, dtype=float)
            axes.set_xlabel('SWE map')
        q25, medians, q75 = summary.per_map_stats(values)['q25_median_q75']
        axes.fill_between(x, q25, q75, color='C0', alpha=.15, step='mid', label='IQR within map')
        axes.plot(x, medians, '-', color='C0', lw=1, alpha=.5)
        axes.plot(x[included], medians[included], 'o', color='C0', label='map median')
        if (~included).any():
            axes.plot(x[~included], np.nan_to_num(medians[~included], nan=0), 'x', color='grey', ms=8,
                      mew=2, label='excluded map')
        shown = [q25, q75, medians]
        if show_reference:
            ref = np.asarray(stats['reference_median'], dtype=float)
            axes.plot(x, ref, 's-', color='darkorange', ms=4, lw=1, label='muscle reference (map medians)')
            shown.append(ref)
        finite = np.concatenate([np.asarray(v, float)[np.isfinite(v)] for v in shown])
        if finite.size:
            top = finite.max()
            axes.set_ylim(0, top * 1.15 if top > 0 else 1)
        return x, medians

    @staticmethod
    def _plot_distributions(axes, values, included):
        """Distribution of values in each map (violins), with per-map medians
        Returns: x positions and medians of the maps"""
        n_maps = values.shape[0]
        x = np.arange(1, n_maps + 1, dtype=float)
        medians = summary.per_map_stats(values)['median']
        data = data_utils.filter_nans(values.tolist())
        positions = [i + 1 for i, v in enumerate(data) if len(v)]
        if positions:
            vp = axes.violinplot([data[p - 1] for p in positions], positions=positions, widths=.9,
                                 showmeans=False, showmedians=False, showextrema=False)
            for position, body in zip(positions, vp['bodies']):
                body.set_facecolor('navy' if included[position - 1] else 'lightgrey')
                body.set_edgecolor('#473535')
                body.set_alpha(.5)
        axes.scatter(x[included], medians[included], s=25, c='orange', zorder=3, label='map median')
        if (~included).any():
            axes.scatter(x[~included], np.nan_to_num(medians[~included], nan=0), s=40, c='grey', marker='x',
                         zorder=3, label='excluded map')
        axes.set_xlabel('SWE map')
        return x, medians

    @staticmethod
    def _annotate_exclusions(axes, x, medians, included, reasons):
        """Write the reason for exclusion above excluded maps; consecutive maps excluded for the same reason
        get one label (exact values are in the per-map table)"""
        groups, current = [], None
        for i, (ok, reason) in enumerate(zip(included, reasons)):
            category = summary.reason_category(str(reason)) if not ok and reason else None
            if category and current and current['category'] == category and current['last'] == i - 1:
                current['last'] = i
                continue
            current = {'category': category, 'first': i, 'last': i} if category else None
            if current:
                groups.append(current)
        for g in groups:
            idx = np.arange(g['first'], g['last'] + 1)
            y = np.nan_to_num(medians[idx], nan=0)
            axes.annotate(g['category'].replace('; ', '\n'), xy=(x[idx].mean(), y.max()), xytext=(0, 9),
                          textcoords='offset points', ha='center', va='bottom', fontsize='x-small', color='dimgrey')

    def clear_figure(self):
        """Remove plot from preview (keeps figure and toolbar usable for the next analysis)"""
        self.figure.clear()
        self.figure_canvas.draw_idle()

    def display_results(self):
        """Display summary and per-map results in a popup window with two tables"""
        # adapted from https://stackoverflow.com/a/71827719/13147488
        results = self.output.results
        if not results:
            return
        window = tk.Toplevel(self)
        window.title(results['file'][0])
        root_x, root_y = self.winfo_rootx(), self.winfo_rooty()
        # place table next to the figure, but keep it on screen
        x = min(root_x + int(self.winfo_width()), max(0, self.winfo_screenwidth() - 700))
        window.geometry(f'+{x}+{root_y}')
        notebook = ttk.Notebook(window)
        notebook.pack(fill=tk.BOTH, expand=True)
        rows, columns = main_result_names(results)
        for name, df in (('Summary', display_frame(summary.summary_table(results))),
                         ('Per map', display_frame(summary.per_map_table(results)))):
            frame = ttk.Frame(notebook)
            notebook.add(frame, text=name)
            table = pandastable.Table(frame, dataframe=df)
            table.show()
            try:  # highlight main result (rows of the summary, median column of the per-map table)
                if name == 'Summary':
                    table.setRowColors(rows=[i for i, p in enumerate(df['parameter']) if p in rows],
                                       clr='#' + HIGHLIGHT, cols='all')
                else:
                    for col in [df.columns.get_loc(c) for c in columns if c in df.columns]:
                        table.setRowColors(rows=list(range(len(df))), clr='#' + HIGHLIGHT, cols=[col])
                table.redraw()
            except Exception:  # cosmetic only (pandastable API varies between versions)
                pass

    def show_value_map(self):
        """Display values of the analysed ROI as maps, one per SWE map"""
        results = self.output.results
        if not results:
            return
        swe_var = self.plot_swe_var.get()
        built = summary.value_maps(results, swe_var)
        if built is None:
            showinfo(title='Value map', message='Not available for results cached by an earlier version '
                                                'of swepy. Analyse the file again.')
            return
        maps, x0, y0 = built
        stats = results['stats']
        frames = stats.get('dicom_frame', np.arange(1, len(maps) + 1))
        included = stats.get('included', np.ones(len(maps), dtype=bool))
        info = [f'DICOM frame {f}' + ('' if ok else '  (excluded)') for f, ok in zip(frames, included)]
        ValueMapWindow(self, maps, x0, y0, f'{summary.LABELS[swe_var]} ({summary.UNITS[swe_var]})',
                       f"{results['file'][0]}: ROI values", map_info=info)
