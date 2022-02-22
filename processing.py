import numpy as np
from pydicom import dcmread
from pydicom.pixel_data_handlers.util import convert_color_space
from skimage.draw import polygon

import utils


class Data:
    """Containing data from dicom file and analysis methods"""

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
        self.roi_coords = None
        self.top_fov_coords = None
        self.bmode_fhz = None
        self.swe_fhz = None
        self.max_scale = None
        self.results = None

        self.void_threshold = 150  # value used in Elastogui

    def get_img_name(self):
        if self.path:
            self.img_name = self.path.name

    def define_rois(self):
        rois = self.ds.SequenceOfUltrasoundRegions._list
        self.top_fov = rois[0]  # top field of view
        self.swe = rois[1]  # SWE box
        self.bot_fov = rois[2]  # bottom field of view

    @staticmethod
    def get_roi_coord(dataset_obj):
        """return upper right and lower left coordinates of rectangle region of interest"""
        coords = [(dataset_obj.RegionLocationMinX0, dataset_obj.RegionLocationMinY0),
                  (dataset_obj.RegionLocationMaxX1, dataset_obj.RegionLocationMaxY1)]
        return coords

    def load_dicom(self):
        self.get_img_name()
        self.ds = dcmread(self.path)
        self.define_rois()
        self.roi_coords = self.get_roi_coord(self.swe)
        self.top_fov_coords = self.get_roi_coord(self.top_fov)
        self.bmode_fhz = float(self.ds.RecommendedDisplayFrameRate)
        img_array_raw = self.ds.pixel_array
        self.img_array = convert_color_space(img_array_raw, 'YBR_FULL_422', 'RGB', per_frame=True)

    def resample(self, swe_fhz=1.0):
        """resample scan sequence to only retain 1st scans with unique SWE data"""
        if self.bmode_fhz % swe_fhz == 0:
            frame_step = int(self.bmode_fhz // swe_fhz)
        else:
            frame_step = int(self.bmode_fhz // swe_fhz + 1)
        # NB: 2nd frame comes at index 3 or 4
        swe_indices = np.arange(start=3, stop=self.img_array.shape[0], step=frame_step)  # only works for sequences!
        swe_indices = np.insert(swe_indices, 0, 0)
        self.swe_array = self.img_array[swe_indices, :, :]
        return self.swe_array  # TODO: replace with detecting method L84 in SWE>dicom_io.py

    def get_rois(self):
        """Index sub-array of unique SWE frames at SWE ROI coordinates"""
        if len(self.roi_coords) > 2:
            coords = self.roi_coords
        else:
            coords = utils.rect_polygonise(self.roi_coords)
        coords_arr = np.asarray(coords)
        rr, cc = polygon(coords_arr[:, 0], coords_arr[:, 1])
        self.rois = self.swe_array[:, cc, rr, :]

    def void_filter(self):
        """Create mask of void pixels in image array
        Args:
            img_roi: 3D image array with RGB channels in 3rd dimension
            threshold (int): user defined threshold of cumulative difference between channels
        Returns: mask of void pixels
        """
        # assign threshold to max value (3*255) if it is None
        threshold = self.void_threshold if isinstance(self.void_threshold, int) else 765
        arr = np.copy(self.rois)
        # NB: important to convert channel values to float before calculations
        r = arr[:, :, 0].astype(np.float32)
        g = arr[:, :, 1].astype(np.float32)
        b = arr[:, :, 2].astype(np.float32)
        rg_diff = np.abs(np.subtract(r, g))
        rb_diff = np.abs(np.subtract(r, b))
        gb_diff = np.abs(np.subtract(g, b))
        cumulated_diff = rg_diff + rb_diff + gb_diff
        void_mask = cumulated_diff > threshold
        return void_mask

    def set_colour_scale(self):
        """
        Thin colour bar to one pixel width and set matching scale based on max. scale value
        Returns: colour profile and corresponding "real values" of velocity or modulus
        """
        colour_bar = {'x0': 693, 'y0': 71, 'x1': 700,
                      'y1': 179}  # retrieved manually from IJ
        scale_arr = self.img_array[0][colour_bar['y0']:colour_bar['y1'],
                    colour_bar['x0']:colour_bar['x1'],
                    :]
        # 2D array for single pxl colour scale, with width 3 (r, g, b)
        self.colour_profile = scale_arr.mean(axis=1, dtype=int)
        # 1D array of values matching colour profile (velocity or modulus)
        self.real_values = np.linspace(self.max_scale, 0, self.colour_profile.shape[0])

    def analyse_roi(self):
        """
        Calculate stat parameter of interest for ROIs of each frame
        Args:
            rois: image sub-array for region of interest
        Returns:
        """
        self.get_rois()
        self.set_colour_scale()
        filter_mask = self.void_filter()
        indices = utils.closest_rgb(self.rois, self.colour_profile)
        self.mapped_values = self.real_values[indices]
        self.filtered_values = np.where(filter_mask, self.mapped_values, np.nan)
        self.gen_results()

    def gen_results(self):
        # TODO: implement method to detect variable measured in SWE scans (assume shear_m here)
        self.source_var = 'youngs_m'
        target_vars = ['velocity', 'shear_m', 'youngs_m']
        d = {'file': [self.path.stem, self.path.parent],
             'roi_coords': self.roi_coords,
             'raw': {},
             'stats': {}}
        for target_var in target_vars:
            if target_var == self.source_var:
                d['raw'][target_var] = self.filtered_values
            else:
                d['raw'][target_var] = utils.convert_swe(self.filtered_values,
                                                         self.source_var,
                                                         target_var)
            filtered = d['raw'][target_var]
            d['stats']['_'.join((target_var, 'median'))] = np.nanmedian(filtered, axis=1)
            d['stats']['_'.join((target_var, 'mean'))] = np.nanmean(filtered, axis=1)
        self.results = d
        self.mean = np.nanmean(self.filtered_values)
        self.median = np.nanmedian(self.filtered_values)
