import tkinter

import numpy as np
from pydicom import dcmread
from skimage.draw import polygon

import swepy_core
from swepy_core.processing import data_utils, summary

COLOUR_DECODING = {'interpolated': 'interpolated along colour bar',   # default
                   'nearest': 'nearest colour bar row'}


def get_colour_decoding():
    """Colour decoding method chosen in Edit > Settings ('interpolated' by default)"""
    value = data_utils.get_settings('COLOUR_DECODING')
    return value[0] if value and value[0] in COLOUR_DECODING else 'interpolated'


class NoSWEDataError(Exception):
    """Raised when the ROI contains no elastography (coloured) pixels in any frame"""


class DcmData:
    """Containing data from DICOM file and analysis methods"""
#TODO: change colour analysis from RGB to HSB
    def __init__(self, path):
        super().__init__()

        self.path = path
        self.img_name = None
        self.ds = None
        self.img_array = None
        self.top_fov = None  # top field of view
        self.swe = None  # SWE box
        self.bot_fov = None  # bottom field of view
        self.swe_array = None
        self.swe_indices = None  # indices of the DICOM frames retained (one per SWE map)
        self.resampling = None  # how SWE maps were detected (for traceability)
        self.roi_coords = None
        self.roi_shape = None
        self.top_fov_coords = None
        self.fov_y_offset = None  # vertical distance between top and bottom fields of view
        self.bmode_fhz = None
        self.frame_time_ms = None
        self.pixel_xy = None  # (x, y) image coordinates of ROI pixels
        self.colour_indices = None  # position of each ROI pixel along the colour bar (0 = top, float)
        self.colour_decoding = None
        self.roi_mode = None  # 'rectangle', 'polygon', 'apo_auto' or 'apo_manual'
        self.reference_coords = None  # optional reference ROI (e.g. muscle next to an aponeurosis)
        self.reference_values = None
        self.apo_info = {}  # aponeurosis line descriptors (see processing.aponeurosis.geometry)
        self._bmode_box = None
        self.swe_fhz = None
        self.max_scale = None
        if tkinter._default_root is not None:
            self.sat_thresh_var = tkinter.IntVar()
            self.set_saturated_threshold()
        self.analysis_swe_var = None
        self.results = None

        self.void_threshold = 150  # value used in Elastogui

    def set_saturated_threshold(self):
        """Try and read the percentage of the max scale to use as a threshold
        above which pixels are considered saturated"""
        sat_thresh = data_utils.get_settings('SAT_THRESH')
        if sat_thresh:
            self.sat_thresh_var.set(sat_thresh[0])
        else:
            self.sat_thresh_var.set(98)  # set default value to 98%

    def get_img_name(self):
        if self.path:
            self.img_name = self.path.name

    def define_rois(self):
        rois = list(self.ds.SequenceOfUltrasoundRegions)
        if len(rois) < 3:
            raise IndexError('The current image may not contain SWE data.')
        self.top_fov = rois[0]  # top field of view
        self.swe = rois[1]  # SWE box
        self.bot_fov = rois[2]  # bottom field of view

    @staticmethod
    def get_roi_coord(dataset_obj, offset=5):
        """return upper right and lower left coordinates of rectangle region of interest"""
        start_x = dataset_obj.RegionLocationMinX0 + offset  # do avoid ROI border
        start_y = dataset_obj.RegionLocationMinY0 + offset
        stop_x = dataset_obj.RegionLocationMaxX1 - offset
        stop_y = dataset_obj.RegionLocationMaxY1 - offset
        coords = [(start_x, start_y), (stop_x, stop_y)]
        return coords

    def load_dicom(self):
        """Retrieve DICOM image and key metadata"""
        self.get_img_name()
        self.ds = dcmread(self.path)
        self.define_rois()
        self.roi_coords = self.get_roi_coord(self.swe)
        self.top_fov_coords = self.get_roi_coord(self.top_fov, offset=0)
        self.fov_y_offset = self.bot_fov.RegionLocationMinY0 - self.top_fov.RegionLocationMinY0
        # FrameTime (ms) gives the actual frame interval of the stored loop. On Mach30 exports
        # (FrameTime 50 ms) it matches observed SWE refresh periods, while RecommendedDisplayFrameRate
        # (19 Hz) does not.
        if self.ds.get('FrameTime'):
            self.bmode_fhz = 1000 / float(self.ds.FrameTime)
        else:
            self.bmode_fhz = float(self.ds.RecommendedDisplayFrameRate)
        self.frame_time_ms = 1000 / self.bmode_fhz
        img_array_raw = self.ds.pixel_array
        # if (0x0008, 0x2111) in self.ds and 'Lossy' in self.ds[
        #     0x0008, 0x2111].value:  # check if there was lossy compression
        #     self.img_array = convert_color_space(img_array_raw, 'YBR_FULL_422', 'RGB', per_frame=True)
        # else:
        #     self.img_array = img_array_raw
        self.img_array = img_array_raw  # disabled above code 20250117 as it no longer seemed required

    def swe_box_changes(self):
        """Mean absolute pixel change between consecutive frames, within the SWE box"""
        (x0, y0), (x1, y1) = self.get_roi_coord(self.swe)
        box = self.img_array[:, y0:y1, x0:x1, :].astype(np.int16)
        return np.abs(np.diff(box, axis=0)).mean(axis=(1, 2, 3))

    def resample(self, swe_fhz=1.0):
        """Resample scan sequence to retain one frame per SWE map (the middle frame of each map)

        SWE map refreshes are detected from the images. The SWE frequency entered by the user is only
        used as a starting estimate, since actual refresh rates differ slightly from nominal ones.
        """
        n_frames = self.img_array.shape[0]
        nominal_period = self.bmode_fhz / swe_fhz
        timing = data_utils.find_refresh_timing(self.swe_box_changes(), nominal_period)
        if timing:
            period, first_refresh = timing
            method = 'detected'
        else:  # no visible refresh (e.g. static map): fall back to nominal frequency
            period, first_refresh = int(np.ceil(nominal_period)), 1
            method = 'nominal'
            print(f'{self.img_name}: SWE refreshes not detected, using nominal period of {period} frames')
        self.swe_indices = data_utils.select_swe_frames(n_frames, period, first_refresh)
        self.resampling = {'method': method,
                           'period_frames': period,
                           'nominal_period_frames': round(nominal_period, 2),
                           'frame_rate': round(self.bmode_fhz, 2)}
        self.swe_array = self.img_array[self.swe_indices, :, :]
        return self.swe_array

    def bmode_box(self):
        """Time-averaged B-mode image of the SWE box region, from the field of view without colour overlay
        Returns: (image (height, width), x0, y0) with x0, y0 the box origin in the top field of view
        """
        if self._bmode_box is None:
            (x0, y0), (x1, y1) = self.get_roi_coord(self.swe, offset=0)
            yb = y0 + self.fov_y_offset
            region = self.img_array[:, yb:yb + (y1 - y0), x0:x1, :]
            self._bmode_box = (region.astype(np.float32).mean(axis=(0, 3)), x0, y0)
        return self._bmode_box

    def get_rois(self, img_arr):
        """Index sub-array of image frames at SWE ROI coordinates"""
        if len(self.roi_coords) > 2:
            self.roi_shape = 'polygon'
            coords = self.roi_coords
        else:
            self.roi_shape = 'rectangle'
            coords = data_utils.rect_polygonise(self.roi_coords)
        coords_arr = np.asarray(coords)
        rr, cc = polygon(coords_arr[:, 0], coords_arr[:, 1])
        self.pixel_xy = (rr.astype(np.int16), cc.astype(np.int16))
        return img_arr[:, cc, rr, :]

    def calc_pixel_percent(self, target):
        dims = self.filtered_values.shape
        total_count = np.full(dims[0], dims[1])
        count = np.count_nonzero(target, axis=1)
        pixel_percent = (count / total_count) * 100
        return pixel_percent

    def void_filter(self):
        """Create mask of void pixels in image array
        Args:
            img_roi: 3D image array with RGB channels in 3rd dimension
            threshold (int): user defined threshold of cumulative difference between channels
        Returns: mask of void pixels
        """
        return self.colour_mask(self.rois)

    def colour_mask(self, arr):
        """Return mask of coloured (non-void) pixels of an RGB image array (..., 3)"""
        # assign threshold to max value (3*255) if it is None
        threshold = self.void_threshold if isinstance(self.void_threshold, int) else 765
        # NB: important to convert channel values to float before calculations
        r = arr[..., 0].astype(np.float32)
        g = arr[..., 1].astype(np.float32)
        b = arr[..., 2].astype(np.float32)
        rg_diff = np.abs(np.subtract(r, g))
        rb_diff = np.abs(np.subtract(r, b))
        gb_diff = np.abs(np.subtract(g, b))
        cumulated_diff = rg_diff + rb_diff + gb_diff
        void_mask = cumulated_diff > threshold
        return void_mask

    def set_colour_scale(self):
        """
        Thin colour bar of the image to one pixel width and set matching scale based on max. scale value
        Returns: colour profile and corresponding "real values" of velocity or modulus
        """
        # retrieved manually from IJ. NB: only the central columns of the bar (x 695-698) are used,
        # because its edge columns are blurred with the black background
        colour_bar = {'x0': 695, 'y0': 70, 'x1': 699, 'y1': 180}
        scale_arr = self.img_array[0][colour_bar['y0']:colour_bar['y1'],
                    colour_bar['x0']:colour_bar['x1'],
                    :]
        # 2D array for single pxl colour scale, with width 3 (r, g, b)
        self.colour_profile = scale_arr.mean(axis=1)
        self.colour_decoding = get_colour_decoding()
        # 1D array of values matching colour profile (velocity or modulus).
        # NB: the colour bar is linear in modulus, even when the scale is displayed in m/s
        # (e.g. ticks at 8.9, 13, 15, 18 m/s for a 20 m/s scale = 240, 480, 720, 960 kPa)
        n_colours = self.colour_profile.shape[0]
        if self.analysis_swe_var == 'velocity':
            max_modulus = data_utils.convert_swe(self.max_scale, 'velocity', 'youngs_m')
            moduli = np.linspace(max_modulus, 0, n_colours)
            self.real_values = data_utils.convert_swe(moduli, 'youngs_m', 'velocity')
        else:
            self.real_values = np.linspace(self.max_scale, 0, n_colours)

    def colour_to_positions(self, rgb):
        """Position of each colour along the colour bar (0 = top row), with the chosen decoding method:
        'interpolated' (between bar rows, default) or 'nearest' (nearest bar row, raw colour bar)"""
        if self.colour_decoding == 'nearest':
            return data_utils.closest_rgb(rgb, self.colour_profile).astype(float)
        return data_utils.colour_positions(rgb, self.colour_profile)

    def positions_to_values(self, positions):
        """Convert positions along the colour bar (0 = top row) to values of the analysed variable
        NB: the colour bar is linear in modulus, even when the scale is displayed in m/s
        """
        fraction = 1 - np.asarray(positions, dtype=float) / (self.colour_profile.shape[0] - 1)  # 1 = max scale
        if self.analysis_swe_var == 'velocity':
            max_modulus = data_utils.convert_swe(self.max_scale, 'velocity', 'youngs_m')
            return data_utils.convert_swe(fraction * max_modulus, 'youngs_m', 'velocity')
        return fraction * self.max_scale

    def decode_box(self, offset=3):
        """Decode values over the whole SWE box of each SWE map (for display, e.g. to place the ROI)
        Returns: (maps (n, height, width) with NaN for void pixels, x0, y0 of the box in the image)
        """
        (x0, y0), (x1, y1) = self.get_roi_coord(self.swe, offset=offset)  # offset avoids box outline
        box = self.swe_array[:, y0:y1, x0:x1, :]
        self.set_colour_scale()
        values = self.positions_to_values(self.colour_to_positions(box))
        values[~self.colour_mask(box)] = np.nan
        return values, x0, y0

    def decode_polygon(self, coords):
        """Values in a polygon for each SWE map (NaN for void pixels), without changing the main ROI"""
        coords_arr = np.asarray(coords)
        rr, cc = polygon(coords_arr[:, 0], coords_arr[:, 1])
        rgb = self.swe_array[:, cc, rr, :]
        values = self.positions_to_values(self.colour_to_positions(rgb))
        return np.where(self.colour_mask(rgb), values, np.nan)

    def analyse_roi(self):
        """Calculate stat parameter of interest for ROIs of each frame"""
        self.rois = self.get_rois(self.swe_array)
        self.set_colour_scale()
        filter_mask = self.void_filter()
        # position of each pixel's colour along the colour bar (interpolated between rows by default)
        self.colour_indices = self.colour_to_positions(self.rois)
        self.mapped_values = self.positions_to_values(self.colour_indices)
        self.filtered_values = np.where(filter_mask, self.mapped_values, np.nan)

        saturated_pxls = self.filtered_values > self.max_scale * self.sat_thresh_var.get() / 100
        self.saturated_percent = self.calc_pixel_percent(saturated_pxls)

        voided_pxls = np.isnan(self.filtered_values)
        self.void_percent = self.calc_pixel_percent(voided_pxls)
        if np.all(self.void_percent == 100):
            raise NoSWEDataError('No elastography data in the selected ROI')
        self.reference_values = (self.decode_polygon(self.reference_coords)
                                 if self.reference_coords and len(self.reference_coords) > 2 else None)
        self.gen_results()

    def gen_results(self):
        """Generate per-map statistics (velocity, shear and Young's modulus), quality flags and metadata"""
        n_maps = self.filtered_values.shape[0]
        frame_idx = self.swe_indices if self.swe_indices is not None else np.arange(n_maps)
        sat_thresh = self.sat_thresh_var.get()

        d = {'file': [self.path.stem, self.path.parent],
             'roi_coords': self.roi_coords,
             'roi_shape': self.roi_shape,
             'resampling': self.resampling,
             'pixel_xy': self.pixel_xy,
             'raw': {},
             'stats': {},
             'meta': {}}
        stats = d['stats']
        stats['dicom_frame'] = frame_idx + 1  # 1-based, as the frame counter on screen
        stats['time_s'] = np.round(frame_idx * self.frame_time_ms / 1000, 3)
        stats['included'] = np.ones(n_maps, dtype=bool)  # set by quality filters below
        stats['exclusion_reason'] = np.full(n_maps, '', dtype=object)
        stats['%_void'] = self.void_percent
        stats[f'%_saturated (> {sat_thresh}% maxscale)'] = self.saturated_percent
        for target_var in summary.SWE_VARS:
            if target_var == self.analysis_swe_var:
                d['raw'][target_var] = self.filtered_values
            else:
                d['raw'][target_var] = data_utils.convert_swe(self.filtered_values,
                                                              self.analysis_swe_var,
                                                              target_var)
            for stat, values in summary.per_map_stats(d['raw'][target_var]).items():
                if stat == 'q25_median_q75':
                    continue
                stats[f'{target_var}_{stat}'] = values
        # colour level of pixels above the bottom of the colour bar: indicates measurement resolution
        n_levels = self.colour_profile.shape[0] - 1
        levels = np.where(np.isnan(self.filtered_values), np.nan, n_levels - self.colour_indices)
        stats['median_colour_level'] = summary.per_map_stats(levels)['median']
        if self.reference_values is not None:  # reference ROI (e.g. adjacent muscle), in the measured variable
            stats['reference_median'] = summary.per_map_stats(self.reference_values)['median']

        resampling = self.resampling or {}
        d['meta'] = {'analysis_variable': self.analysis_swe_var,
                     'max_scale': self.max_scale,
                     'colour_decoding': COLOUR_DECODING[self.colour_decoding],
                     'colour_levels_in_scale': n_levels,
                     'median_colour_level': np.nan,  # set by quality filters
                     'scale_warning': False,
                     'roi_shape': self.roi_shape,
                     'roi_mode': self.roi_mode or self.roi_shape,
                     'roi_pixels': int(self.filtered_values.shape[1]),
                     'reference_pixels': (int(self.reference_values.shape[1])
                                          if self.reference_values is not None else 0),
                     'frame_time_ms': round(self.frame_time_ms, 3),
                     'swe_refresh_period_frames': resampling.get('period_frames'),
                     'swe_refresh_detection': resampling.get('method'),
                     'saturation_threshold_%_of_max_scale': sat_thresh,
                     'swepy_version': swepy_core.__version__}
        d['meta'].update({f'apo_{k}': v for k, v in self.apo_info.items()})
        summary.apply_quality(d)
        self.results = d
