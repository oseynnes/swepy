import re
import tkinter as tk
from pathlib import Path
from tkinter import ttk
from tkinter.messagebox import showerror, showinfo

import numpy as np

from swepy_core.app import app_utils
from swepy_core.app.output_frames import FilesPanel, HistoryPanel, SavePanel, QualityPanel, FigPanel
from swepy_core.app.root_widgets import MenuBar
from swepy_core.app.value_map import ValueMapWindow
from swepy_core.app.view_frames import ImgPanel, TopPanel, LeftPanel, APO_SHAPES
from swepy_core.processing import aponeurosis, data_utils, screen_labels, summary
from swepy_core.processing.data import DcmData, NoSWEDataError
from swepy_core.processing.io import pickle_io


def summary_setting(key, default):
    """Numeric user setting stored as [value], or default"""
    value = data_utils.get_settings(key)
    try:
        return float(value[0]) if value else default
    except (TypeError, ValueError):
        return default


class View(ttk.Frame):
    """Tab frame displaying and controlling scan display and analysis"""

    def __init__(self, parent):
        super().__init__(parent, padding=5)

        self.columnconfigure(1, weight=1)
        self.rowconfigure(1, weight=1)

        self.block = tk.BooleanVar(self, True)

        self.ds = None
        self.img_array = None
        self.img_name = None
        self.swe_var = tk.StringVar()
        self.set_swe_var()

        self.controller = None

        self.img_panel = ImgPanel(self)
        self.canvas = self.img_panel.canvas
        self.fov_coords = None
        self.bot_fov_coords = None
        self.fov_y_offset = None
        self.pixel_mm = None
        self.depth_origin_y = None
        self.init_roi_coords = None
        self.init_roi_shape = None

        self.top = TopPanel(self)

        self.left_panel = LeftPanel(self)
        self.swe_fhz = None
        self.max_scale = None
        self.left_panel.enter_btn['command'] = self.get_usr_entry
        # entries keep the values in use: flag edits that are not set yet
        for var in (self.left_panel.usr_fhz, self.left_panel.usr_scale):
            var.trace_add('write', lambda *args: self.on_entry_edit())
        self.left_panel.reset_roi_btn['command'] = self.reset_rois
        self.left_panel.analyse_btn['command'] = self.process
        self.left_panel.value_map_btn['command'] = self.show_value_map
        self.scale_mask = self.fhz_mask = None
        self.apo_kind = self.apo_plane = None

    def set_swe_var(self):
        swe_var = data_utils.get_settings('SWE_VAR')
        if swe_var:
            self.swe_var.set(swe_var[0])
        else:
            self.swe_var.set('youngs_m')  # set default SWE variable to Young's modulus

    def set_controller(self, controller):
        self.controller = controller

    def reset_rois(self):
        """Reset original ROI selection to initial values (or to the suggested aponeurosis line)"""
        if self.img_panel.is_apo():
            self.img_panel.reset_draw()
            self.on_shape_change()
            return
        self.img_panel.roi_coords = self.init_roi_coords
        self.img_panel.shape.set(self.init_roi_shape or 'rectangle')  # default ROI: SWE box rectangle
        self.img_panel.set_rois()

    def process(self):
        """Check requirements and launch analysis"""
        if not all([self.swe_fhz, self.max_scale]):
            app_utils.warn_wrong_entry()
            return
        if self.ds:
            if self.img_panel.is_apo() and not self.img_panel.apo_result:
                showinfo(title='No aponeurosis ROI',
                         message='Click on the aponeurosis (Aponeurosis mode), or click points along it and '
                                 'double-click to finish (Apo (manual) mode).')
                return
            if self.controller.analyse():
                if self.img_panel.is_apo():
                    self.remember_apo_depth()
                self.left_panel.set_analyse_status(f'Analysed {self.img_name}: see the Results tab')
                self.block.set(False)  # only move on (e.g. to next file of a batch) if analysis worked
        else:
            app_utils.warn_no_video()
            return

    def show_value_map(self):
        """Display decoded values over the whole SWE box, with the current ROI outlined"""
        if not self.ds:
            app_utils.warn_no_video()
            return
        if not all([self.swe_fhz, self.max_scale]) or getattr(self.img_panel, 'swe_array', None) is None:
            app_utils.warn_wrong_entry()  # SWE frames and scale are needed to decode values
            return
        maps, x0, y0 = self.controller.decode_box()
        roi = self.img_panel.roi_coords
        outline = None
        if roi and len(roi) > 1:
            roi = roi if self.img_panel.isin_top_fov() else self.img_panel.mirror_coords()
            outline = data_utils.rect_polygonise(roi) if len(roi) == 2 and self.img_panel.shape.get() == 'rectangle' else roi
        swe_var = self.swe_var.get()
        frames = self.controller.data.swe_indices + 1
        ValueMapWindow(self, maps, x0, y0, f'{summary.LABELS[swe_var]} ({summary.UNITS[swe_var]})',
                       f'{self.img_name}: SWE box values', map_info=[f'DICOM frame {f}' for f in frames],
                       roi_outline=outline)

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
                screen_labels.remember(self.fhz_mask, 'fhz', value=self.swe_fhz)
            if isinstance(self.max_scale, (int, float)) and self.max_scale:
                screen_labels.remember(self.scale_mask, 'scale', value=self.max_scale, swe_var=self.swe_var.get())
                self.left_panel.set_entry_status('Values saved for these screen labels', 'grey')
            self.canvas.focus_set()
        else:
            app_utils.warn_no_video()
            return

    def on_entry_edit(self):
        """Warn when the values entered differ from the values in use (Set values not clicked yet)"""
        if self.swe_fhz is None and self.max_scale is None:
            return  # nothing set yet: status given by the screen labels
        def same(text, value):
            try:
                return value is not None and float(text) == float(value)
            except ValueError:
                return False
        if same(self.left_panel.usr_fhz.get(), self.swe_fhz) and same(self.left_panel.usr_scale.get(), self.max_scale):
            self.left_panel.set_entry_status('Values in use', 'grey')
        else:
            self.left_panel.set_entry_status('Values changed: click Set values to use them', 'firebrick')

    def update_roi_info(self):
        """Describe size and depth of the ROI (top field of view), and how to draw it"""
        if not hasattr(self, 'left_panel') or not self.ds or not self.pixel_mm:
            return
        panel = self.img_panel
        shape = panel.shape.get()
        hints = {'rectangle': 'Click two opposite corners.',
                 'polygon': 'Double-click to finish; Backspace or right-click: undo last point.',
                 'apo_auto': 'Click on the aponeurosis to follow it.',
                 'apo_manual': 'Double-click to finish; Backspace or right-click: undo last point.'}
        coords = panel.roi_coords
        geometry = None
        if coords and (len(coords) > 2 or (shape == 'rectangle' and len(coords) == 2)):
            top = coords if panel.isin_top_fov() else panel.mirror_coords()
            geometry = data_utils.roi_geometry(top, 'rectangle' if shape == 'rectangle' else 'polygon',
                                               self.pixel_mm, self.depth_origin_y)
        if geometry:
            text = (f"ROI: {geometry['width_mm']:.1f} \u00d7 {geometry['height_mm']:.1f} mm ({geometry['area_mm2']:.0f} mm\u00b2)\n"
                    f"Depth {geometry['depth_top_mm']:.1f}\u2013{geometry['depth_bottom_mm']:.1f} mm")
        else:
            text = 'ROI: none'
        self.left_panel.set_roi_info(text, hints.get(shape, ''))

    def get_swe_frames(self):
        """Set GUI to display and analyse SWE unique scans only"""
        self.img_panel.swe_array = self.controller.get_swe_array(self.swe_fhz)
        self.img_panel.swe_frames = self.controller.data.swe_indices + 1  # DICOM frame numbers (1-based)
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

    def initial_roi(self):
        """Suggested ROI (rectangle within the SWE box, given by 2 corners) in the remembered ROI shape:
        as its 4 corners for a polygon (2 points would be drawn as a line)"""
        coords = list(self.init_roi_coords or [])
        if self.img_panel.shape.get() == 'polygon' and len(coords) == 2:
            return data_utils.rect_polygonise(coords)
        return coords

    def set_img_name(self):
        self.top.img_name.config(text=self.img_name)

    def load_file(self):
        """Pass variables and scan array to ImgPanel frame, update View frame"""
        # use field of view geometry from DICOM header to tell top and bottom images apart
        (x0, y0), (x1, y1) = self.fov_coords
        self.img_panel.top_fov_coords = {'x0': x0, 'y0': y0, 'x1': x1, 'y1': y1}
        self.img_panel.fov_y_offset = self.fov_y_offset
        self.img_panel.swe_frames = None
        if self.bot_fov_coords:
            (bx0, by0), (bx1, by1) = self.bot_fov_coords
            self.img_panel.bot_fov_coords = {'x0': bx0, 'y0': by0, 'x1': bx1, 'y1': by1}
        self.img_panel.roi_coords = self.initial_roi()
        self.img_panel.current_array = self.img_array
        self.img_panel.ctrl.update_frame()
        self.img_panel.activate_slider(self.ds.NumberOfFrames)
        self.img_panel.activate_draw()
        self.update_dcm_info()
        self.set_img_name()
        self.activate_arrowkeys()
        self.apply_screen_labels()
        self.set_apo_kind()
        self.on_shape_change()

    # ----- on-screen labels: fill in entries safely -----
    def apply_screen_labels(self):
        """Fill in scale and frequency from labels seen before; clear them for new labels"""
        frame = self.img_array[len(self.img_array) // 2]
        self.scale_mask = screen_labels.scale_label(frame)
        self.fhz_mask = screen_labels.frequency_label(frame)
        self.left_panel.show_label_crops(screen_labels.label_crop(frame, 'fhz'), screen_labels.label_crop(frame, 'scale'))
        new = []
        for mask, kind, var in ((self.fhz_mask, 'fhz', self.left_panel.usr_fhz),
                                (self.scale_mask, 'scale', self.left_panel.usr_scale)):
            if mask is None:            # label not found (other scanner layout): keep previous values
                continue
            known = screen_labels.recall(mask, kind)
            if known:
                var.set(f"{known['value']:g}")
                if kind == 'scale' and known.get('swe_var'):
                    self.swe_var.set(known['swe_var'])
            else:
                var.set('')
                new.append('SWE fhz' if kind == 'fhz' else 'max. scale')
        if new:
            self.left_panel.set_entry_status(f"New on-screen label: enter {' and '.join(new)}, then Set values",
                                             'firebrick')
        elif self.scale_mask is not None:
            self.left_panel.set_entry_status('Values recognised from screen labels: click Set values', 'darkgreen')
        else:
            self.left_panel.set_entry_status('', 'grey')

    # ----- aponeurosis mode -----
    def set_apo_kind(self):
        """Guess plane and aponeurosis from file name (e.g. ..._TRANS_DF0_UP_1) and set reference side"""
        name = Path(self.img_name).stem.upper()
        kind = re.search(r'(?:^|_)(UP|LOW)(?:_|$)', name)
        plane = re.search(r'(?:^|_)(LONG|TRANS)(?:_|$)', name)
        self.apo_kind = kind.group(1) if kind else None
        self.apo_plane = plane.group(1) if plane else None
        if self.apo_kind:
            self.img_panel.apo_side.set(1 if self.apo_kind == 'UP' else -1)

    def _depth_key(self):
        folder = str(Path(self.controller.data.path).resolve().parent)
        return f'{folder}|{self.apo_plane}|{self.apo_kind}'

    def remember_apo_depth(self):
        """Save depth of the analysed aponeurosis, to suggest the line in the next file of the same session"""
        depths = data_utils.get_settings('APO_DEPTHS') or {}
        depths = depths if isinstance(depths, dict) else {}
        depths[self._depth_key()] = self.img_panel.apo_result['info']['depth_mm']
        data_utils.set_setting('APO_DEPTHS', depths)

    def previous_apo_depth(self):
        depths = data_utils.get_settings('APO_DEPTHS') or {}
        return depths.get(self._depth_key()) if isinstance(depths, dict) else None

    def on_shape_change(self):
        """Show aponeurosis tools and suggest a line when the aponeurosis mode is selected"""
        if not self.ds:
            return
        if self.img_panel.shape.get() == 'apo_auto':
            self.set_apo(self.controller.compute_apo(previous_depth_mm=self.previous_apo_depth()))
        elif self.img_panel.shape.get() == 'apo_manual':
            self.show_apo_hint()
        else:
            self.img_panel.apo_status.config(text='Aponeurosis tools: choose ROI shape "Aponeurosis" or '
                                                  '"Apo (manual)"', foreground='grey')

    def apo_from_click(self, x, y):
        self.set_apo(self.controller.compute_apo(seed=(x, y)))

    def apo_from_points(self, points):
        self.set_apo(self.controller.compute_apo(points=points))

    def update_apo(self):
        """Recompute ROIs for the current line (e.g. after changing the reference side)"""
        result = self.img_panel.apo_result
        if result:
            self.set_apo(self.controller.compute_apo(rows=result['rows'], source=result['info']['line_source']))

    def show_apo_hint(self):
        n = len(self.img_panel.apo_points)
        self.img_panel.apo_status.config(
            text=f'Manual line: click points along the aponeurosis from the left to the right edge of the SWE box, '
                 f'double-click to finish ({n} point{"s" if n != 1 else ""})', foreground='black')

    def set_apo(self, result):
        """Use aponeurosis ROIs and report the line descriptors, with warnings"""
        self.img_panel.set_apo(result)
        if not result:
            self.img_panel.apo_status.config(text='No line found: click on the aponeurosis', foreground='firebrick')
            return
        info = result['info']
        text = (f"Line ({info['line_source']}): depth {info['depth_mm']:.1f} mm, tilt {info['line_tilt_deg']:.0f}\u00b0, "
                f"edge {info['min_edge_distance_mm']:.1f} mm. Check it follows the aponeurosis; if not, click on it.")
        warnings = []
        if info['edge_warning']:
            warnings.append(f"closer than {aponeurosis.MIN_EDGE_DISTANCE_MM:g} mm to the box edge")
        previous = self.previous_apo_depth()
        if previous is not None and abs(info['depth_mm'] - previous) > 2:
            warnings.append(f"depth differs by {info['depth_mm'] - previous:+.1f} mm from the previous file")
        if info.get('bmode_line_contrast', 2) < 1.2:
            warnings.append('faint line on B-mode')
        if info['reference_coverage_%'] < 50:
            warnings.append('reference band mostly outside the box')
        if warnings:
            text += '\nWarning: ' + '; '.join(warnings) + '.'
        self.img_panel.apo_status.config(text=text, foreground='firebrick' if warnings else 'darkgreen')


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
        self.view.bot_fov_coords = self.data.bot_fov_coords
        self.view.fov_y_offset = self.data.fov_y_offset
        self.view.pixel_mm = self.data.pixel_mm
        self.view.depth_origin_y = self.data.depth_origin_y
        self.view.init_roi_coords = self.data.roi_coords
        self.view.load_file()

    def decode_box(self):
        """Decode values over the whole SWE box with current user entries"""
        self.data.max_scale = self.view.max_scale
        self.data.analysis_swe_var = self.view.swe_var.get()
        return self.data.decode_box()

    def compute_apo(self, seed=None, points=None, rows=None, source=None, previous_depth_mm=None):
        """Locate the aponeurosis and build its band ROI and muscle reference ROI
        Args:
            seed: (x, y) click on the aponeurosis (top field of view coordinates)
            points: (x, y) points clicked along the aponeurosis (manual line)
            rows: existing line (box coordinates), e.g. to change the reference side
            previous_depth_mm: depth of the aponeurosis in the previous file (suggestion)
        Returns: dict (band, reference and line in image coordinates, rows, descriptors), or None
        """
        data = self.data
        bmode, x0, y0 = data.bmode_box()
        h, w = bmode.shape
        px = float(data.swe.PhysicalDeltaX) * 10
        top = data.top_fov.RegionLocationMinY0
        if rows is None:
            if points:
                rows = aponeurosis.line_from_points([(x - x0, y - y0) for x, y in points], w, h)
                source = 'manual line'
            elif seed:
                rows = aponeurosis.track_line(bmode, px, seed[0] - x0, seed[1] - y0)
                source = 'click'
            else:
                prev_row = (previous_depth_mm / px - (y0 - top)) if previous_depth_mm is not None else None
                rows, source = aponeurosis.suggest_line(bmode, px, prev_row)
        rows = np.asarray(rows, dtype=float)
        if np.all(np.isnan(rows)):
            return None
        half_width = summary_setting('APO_HALF_WIDTH_MM', aponeurosis.BAND_HALF_WIDTH_MM)
        side = self.view.img_panel.apo_side.get()
        band, band_cov = aponeurosis.band_polygon(rows, h, w, px, 0, half_width)
        ref, ref_cov = aponeurosis.band_polygon(rows, h, w, px, aponeurosis.REF_NEAR_MM, aponeurosis.REF_FAR_MM, side)
        if len(band) < 3:
            return None
        info = {'line_source': source,
                'band_half_width_mm': half_width,
                'depth_mm': float((y0 - top + np.nanmedian(rows)) * px),
                **aponeurosis.geometry(rows, h, px, bmode),
                'band_coverage_%': 100 * band_cov,
                'reference_side': 'below' if side > 0 else 'above',
                'reference_limits_mm': f'{aponeurosis.REF_NEAR_MM:g}-{aponeurosis.REF_FAR_MM:g}',
                'reference_coverage_%': 100 * ref_cov}
        valid = np.flatnonzero(~np.isnan(rows))
        line = [(int(x0 + c), int(round(y0 + rows[c]))) for c in valid[::3]]
        return {'band': [(x0 + c, y0 + r) for c, r in band],
                'reference': [(x0 + c, y0 + r) for c, r in ref],
                'line': line, 'rows': rows, 'info': info}

    def get_swe_array(self, swe_fhz):
        """Call method to get array of SWE unique scans"""
        return self.data.resample(swe_fhz)

    def set_swe_variable(self):
        """Set chosen SWE variable for analysis and plotting"""
        self.data.analysis_swe_var = self.view.swe_var.get()
        self.output.fig_panel.plot_swe_var.set(self.view.swe_var.get())

    def analyse(self):
        """Get data and call methods for analysis and preview
        Returns: True if the analysis succeeded
        """
        self.data.swe_fhz = self.view.swe_fhz
        self.data.max_scale = self.view.max_scale
        self.set_swe_variable()
        self.view.img_panel.get_top_coords()
        self.data.roi_coords = self.view.img_panel.roi_coords
        self.data.roi_mode = self.view.img_panel.shape.get()
        apo = self.view.img_panel.apo_result if self.view.img_panel.is_apo() else None
        self.data.reference_coords = apo['reference'] if apo else None
        self.data.apo_info = dict(apo['info']) if apo else {}
        try:
            self.data.analyse_roi()
        except NoSWEDataError:
            app_utils.warn_no_swe_data()
            return False
        self.output.results = self.data.results
        self.output.fig_panel.change_plot()
        self.output.update_tv(self.data.path, self.data.results)
        data_utils.pickle_results(self.data.path, self.data.results)
        return True


class Output(ttk.Frame):
    """Tab frame displaying analysis output"""

    def __init__(self, parent):
        super().__init__(parent, padding=5)

        self.columnconfigure(0, weight=1)
        self.columnconfigure(1, weight=3)
        self.rowconfigure(0, weight=1)

        self.results = None

        self.files_panel = FilesPanel(self)
        self.tv_files = []
        self.tv_selection = set()
        self.files_panel.tv.bind('<<TreeviewSelect>>', self.update_tv_selection)

        self.previous = HistoryPanel(self)
        self.previous.load_btn['command'] = self.load_previous
        self.previous.clear_all_btn['command'] = self.clear_results

        self.save_panel = SavePanel(self)

        self.quality_panel = QualityPanel(self)

        self.fig_panel = FigPanel(self)

    def update_tv(self, path, results=None):
        """Add file name and path to list of analysed files, with warnings to check"""
        self.tv_files.append((path.name, path.resolve().parent))
        if path.name in self.files_panel.tv.get_children():
            self.files_panel.tv.delete(path.name)
        self.files_panel.insert_file(path.name, self.tv_files[-1][1], results)
        self.files_panel.tv.focus(self.files_panel.tv.get_children()[-1])
        self.files_panel.show_folder(self.tv_files[-1][1])

    def update_tv_selection(self, event):
        """Update list of selected rows in list of analysed files"""
        self.tv_selection.clear()
        for selected_item in self.files_panel.tv.selection():
            item = self.files_panel.tv.item(selected_item)
            row = item['values']
            self.tv_selection.add(tuple(row))
        rows = list(self.tv_selection)
        if not rows:  # e.g. after clearing the table
            return
        self.files_panel.show_folder(rows[0][1] if len(rows) == 1 else f'{len(rows)} files selected')
        path = data_utils.get_cached_results_path(rows[0][0])
        if not path.exists():
            return
        self.results = pickle_io.load_pickle(path)
        self.fig_panel.change_plot()

    def clear_results(self):
        """Clear table of analysed files, preview figure and cached results"""
        self.results = None
        self.tv_files.clear()
        self.tv_selection.clear()
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
        app_utils.enable_windows_dpi_awareness()  # must happen before the window is created
        super().__init__()

        self.title('SwePy')
        app_utils.configure_style(self)
        self.window_width = 1100
        self.window_height = 760
        app_utils.set_win_geometry(self, self.window_width, self.window_height)
        self.columnconfigure(0, weight=1)
        self.rowconfigure(0, weight=1)

        self.path = None

        self.mb = MenuBar(self)
        self.config(menu=self.mb)

        self.nb = ttk.Notebook(self)
        self.nb.grid(row=0, column=0, sticky=tk.NSEW)
        self.set_img_proc()
        self.output = Output(self.nb)
        self.nb.add(self.view, text='Image processing')
        self.nb.add(self.output, text='Results')

        # enlarge window if text is bigger than expected (e.g. display scaling), within screen size
        self.update_idletasks()
        app_utils.set_win_geometry(self,
                                   max(self.window_width, self.winfo_reqwidth()),
                                   max(self.window_height, self.winfo_reqheight()))

    def set_img_proc(self):
        """Instantiate classes specific to a DICOM file"""

        self.data = DcmData(self.path)
        self.view = View(self.nb)

    def reset(self, path):
        """Reset file processing
        Args:
            path: pathlib path to DICOM file
        Returns: True if the file was loaded
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
            try:
                controller.get_dicom_data()
            except Exception as error:  # e.g. not a DICOM file, or no SWE data
                self.popup.destroy()
                showerror(title='Could not load file', message=f'{path.name}:\n{error}')
                return False
            return True
        return False

    def display_loading_msg(self):
        """Display message while file is loading"""
        self.popup = tk.Toplevel(self)
        self.popup.title('Loading')
        self.popup.transient(self)
        self.popup.resizable(False, False)
        msg = ttk.Label(self.popup, text="DICOM file loading...", padding=20)
        msg.grid(row=0, column=0)
        app_utils.center_window(self.popup, self)

    def check_loading_status(self):
        """Check whether DICOM file is loaded"""
        if not self.popup.winfo_exists():  # popup already closed (e.g. loading failed)
            return
        if self.data.ds:
            self.popup.destroy()
        else:
            self.after(10, self.check_loading_status)

    def paths_handler(self):
        """Handle single/multiple path selection(s)"""
        paths = self.mb.select_files()
        if paths:
            if not self.reset(paths[0]):
                return
            self.wait_variable(self.view.block)
            if len(paths) > 1 and self.view.block.get() is False:
                cached_path = data_utils.get_cached_results_path(paths[0].name)
                cached_file1 = pickle_io.load_pickle(cached_path)
                roi_coords = cached_file1['roi_coords']
                roi_shape = cached_file1['roi_shape']
                self.view.block.set(True)
                for i, path in enumerate(paths[1:]):
                    if not self.reset(path):
                        continue
                    self.view.get_usr_entry()
                    if not self.view.img_panel.is_apo():  # aponeurosis ROIs are suggested for each file instead
                        self.view.init_roi_coords = roi_coords  # detected or user drawn roi coords (1st file)
                        self.view.init_roi_shape = roi_shape
                        self.view.reset_rois()
                        self.view.init_roi_coords = self.data.roi_coords  # detected roi coords for 'reset' button
                    self.wait_variable(self.view.block)  # until the user analyses this file
                self.nb.select(self.output)
