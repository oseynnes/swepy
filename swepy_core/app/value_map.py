"""Window displaying decoded SWE values as a map, with a depth profile.

Used to spot heterogeneities in the SWE box (e.g. stiff aponeuroses or fascia) before drawing the ROI,
and to inspect analysed ROIs map by map.
"""
import tkinter as tk
import warnings
from tkinter import ttk

import numpy as np
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg, NavigationToolbar2Tk
from matplotlib.figure import Figure

from swepy_core.app.app_utils import center_window, get_ui_scale


class ValueMapWindow(tk.Toplevel):
    """Display maps of decoded values, one SWE map at a time, with the median value at each depth"""

    def __init__(self, parent, maps, x0, y0, value_label, title, map_info=None, roi_outline=None):
        """
        Args:
            parent: parent widget
            maps: array (n maps, height, width) of values, NaN where there is no value
            x0, y0: image coordinates of the top left pixel of the maps
            value_label (str): name and unit of displayed values
            title (str): window title
            map_info (list of str): text describing each map (e.g. DICOM frame, excluded)
            roi_outline (list of (x, y)): ROI polygon to draw, in image coordinates
        """
        super().__init__(parent)
        self.title(title)
        self.maps = maps
        self.map_info = map_info or [''] * len(maps)
        self.value_label = value_label
        self.roi_outline = roi_outline
        height, width = maps.shape[1:]
        self.extent = (x0 - .5, x0 + width - .5, y0 + height - .5, y0 - .5)  # image pixel coordinates
        with warnings.catch_warnings():
            warnings.simplefilter('ignore', category=RuntimeWarning)
            self.vmax = float(np.nanpercentile(maps, 99)) if np.isfinite(maps).any() else 1.0
            self.median_profile = np.nanmedian(np.nanmedian(maps, axis=2), axis=0)  # all maps

        self.figure = Figure(figsize=(8, 4.5), dpi=100 * get_ui_scale(self), layout='constrained')
        self.ax_map, self.ax_profile = self.figure.subplots(1, 2, gridspec_kw={'width_ratios': [3, 1]}, sharey=True)
        self.image = None

        controls = ttk.Frame(self, padding=5)
        controls.pack(side=tk.BOTTOM, fill=tk.X)
        ttk.Label(controls, text='SWE map:').pack(side=tk.LEFT)
        self.current = tk.IntVar(value=0)
        self.slider = ttk.Scale(controls, from_=0, to=max(0, len(maps) - 1), orient=tk.HORIZONTAL,
                                command=self.on_slide)
        self.slider.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=5)
        self.info = ttk.Label(controls, width=40)
        self.info.pack(side=tk.LEFT)
        if len(maps) < 2:
            self.slider.state(['disabled'])

        self.canvas = FigureCanvasTkAgg(self.figure, self)
        NavigationToolbar2Tk(self.canvas, self)
        self.canvas.get_tk_widget().pack(side=tk.TOP, fill=tk.BOTH, expand=True)

        self.draw(0)
        center_window(self, parent.winfo_toplevel())

    def on_slide(self, value):
        index = int(round(float(value)))
        if index != self.current.get():
            self.draw(index)

    def draw(self, index):
        """Draw map number index and the depth profiles"""
        self.current.set(index)
        values = self.maps[index]
        if self.image is None:
            # NB: aspect 'auto' keeps map and depth profile aligned row by row
            self.image = self.ax_map.imshow(values, extent=self.extent, cmap='viridis', vmin=0, vmax=self.vmax,
                                            interpolation='nearest', aspect='auto')
            self.figure.colorbar(self.image, ax=self.ax_map, label=self.value_label,
                                 orientation='horizontal', shrink=.6, aspect=40)
            if self.roi_outline and len(self.roi_outline) > 1:
                xs, ys = zip(*(list(self.roi_outline) + [self.roi_outline[0]]))
                self.ax_map.plot(xs, ys, color='white', lw=1.5, ls='--', label='ROI')
                self.ax_map.legend(loc='lower right', fontsize='small')
            self.ax_map.set_xlabel('x (image pixels)')
            self.ax_map.set_ylabel('depth (image pixels)')
        else:
            self.image.set_data(values)

        rows = np.arange(values.shape[0]) + self.extent[3] + .5
        with warnings.catch_warnings():
            warnings.simplefilter('ignore', category=RuntimeWarning)
            profile = np.nanmedian(values, axis=1)
        self.ax_profile.clear()
        self.ax_profile.plot(self.median_profile, rows, color='grey', ls='--', label='all maps')
        self.ax_profile.plot(profile, rows, color='C0', label='this map')
        self.ax_profile.set_xlabel(f'median per depth\n{self.value_label}')
        self.ax_profile.set_xlim(left=0)
        self.ax_profile.legend(fontsize='small')
        self.ax_profile.tick_params(labelleft=False)
        self.ax_profile.set_ylim(self.extent[2], self.extent[3])

        self.info.config(text=f'{index + 1}/{len(self.maps)}  {self.map_info[index]}')
        self.canvas.draw_idle()
