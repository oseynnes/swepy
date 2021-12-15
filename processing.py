import numpy as np
from pydicom import dcmread
from pydicom.pixel_data_handlers.util import convert_color_space
import numpy as np
import pandas as pd
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
        coords = {'x0': dataset_obj.RegionLocationMinX0,
                  'y0': dataset_obj.RegionLocationMinY0,
                  'x1': dataset_obj.RegionLocationMaxX1,
                  'y1': dataset_obj.RegionLocationMaxY1}
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
        return self.swe_array

    def get_rois(self):
        """Index sub-array of unique SWE frames at SWE ROI coordinates"""
        self.rois = self.swe_array[:,
                                   self.roi_coords['y0']:self.roi_coords['y1'],
                                   self.roi_coords['x0']:self.roi_coords['x1'],
                                   :]
        return self.rois

    def remove_voids(self):  # TODO: filter function
        # find voids (RGB values?)
        # apply median filter, replacing each pixel with the median of the neighboring pixel values
        # radius=5?
        pass

    def get_colour_scale(self):
        """Thin colour bar to one pixel width and set matching scale based on max. scale value"""
        colour_bar = {'x0': 693, 'y0': 71, 'x1': 700,
                      'y1': 179}  # retrieved manually from IJ
        scale_arr = self.img_array[0][colour_bar['y0']:colour_bar['y1'],
                    colour_bar['x0']:colour_bar['x1'],
                    :]
        # 2D array for single pxl colour scale, with width 3 (r, g, b)
        self.colour_profile = scale_arr.mean(axis=1, dtype=int)
        # 1D array of values matching colour profile (velocity or modulus)
        self.real_values = np.linspace(self.max_scale, 0, self.colour_profile.shape[0])

    def get_data_values(self, rois):
        """Calculate stat parameter of interest for ROIs of each frame"""
        self.get_colour_scale()
        indices = utils.closest_rgb(rois, self.colour_profile)
        self.mapped_values = self.real_values[indices]

        self.create_output_df()

        self.mean = self.mapped_values.mean()
        self.median = np.median(self.mapped_values)
        # print(f'Mean modulus matched RGBs (KPa):    {dict(zip(np.arange(indices.shape[0]), mean))}')
        # print(f'Median modulus matched RGBs(KPa):   {dict(zip(np.arange(indices.shape[0]), median))}')

    def create_output_df(self):
        # TODO: implement method to detect variable measured in SWE scans (assume shear_m here)
        self.source_var = 'youngs_m'
        target_vars = ['velocity', 'shear_m', 'youngs_m']
        d = {'raw': {}, 'stats': {}}
        for target_var in target_vars:
            if target_var == self.source_var:
                d['raw'][target_var] = self.mapped_values
            else:
                d['raw'][target_var] = utils.convert_swe(self.mapped_values,
                                                         self.source_var,
                                                         target_var)

            d['stats']['_'.join((target_var, 'median'))] = np.median(d['raw'][target_var], axis=(1, 2))
            d['stats']['_'.join((target_var, 'mean'))] = d['raw'][target_var].mean(axis=(1, 2))

        # data['ROI area'] = np.full((12,), utils.get_area(self.roi_coords))
        self.results = d
        self.df = pd.DataFrame.from_dict(d['stats'])

