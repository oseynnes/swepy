import numpy as np
from pydicom import dcmread
from pydicom.pixel_data_handlers.util import convert_color_space

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

        self.mean = self.mapped_values.mean()
        self.median = np.median(self.mapped_values)
        # TODO: make dataframe with each variable as column
        print(f'mean shape: {self.mapped_values.mean(axis=(1, 2)).shape}')
        print(f'median shape: {np.median(self.mapped_values, axis=(1, 2)).shape}')
        # print(f'Mean modulus matched RGBs (KPa):    {dict(zip(np.arange(indices.shape[0]), mean))}')
        # print(f'Median modulus matched RGBs(KPa):   {dict(zip(np.arange(indices.shape[0]), median))}')


# # Method 1: RGB stats -> match -> module ####################################
# # Get SWE RGB stats
# mean_rgb = swe_roi_arr.mean(axis=(0, 1), dtype=int)
# std_rgb = np.std(swe_roi_arr, axis=(0, 1))
# rgbs, count = np.unique(swe_roi_arr.reshape(-1, 3), axis=0, return_counts=True)
# mode_rgb_idx = int(np.where(count == np.amax(count))[0])
# mode_rgb = rgbs[mode_rgb_idx]

# index = utils.closest_rgb(mean_rgb, color_profile)
# mapped_value = real_values[index]
# print(f'Mean modulus from mean RGB:   {int(mapped_value)}KPa')
# mode_module1 = real_values[utils.closest_rgb(mode_rgb, color_profile)]
# print(f'Mode modulus from mode RGB:   {int(mode_module1)}KPa')

# # Method 2: RGB match -> stats -> module ####################################
# indices = utils.closest_rgb(swe_roi_arr, color_profile)
# mapped_values = real_values[indices]
# mean = mapped_values.mean(axis=(0, 1))
# print(f'Mean modulus matched RGBs:    {int(mean)}KPa')
