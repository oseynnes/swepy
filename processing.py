import numpy as np
from pydicom import dcmread
from pydicom.pixel_data_handlers.util import convert_color_space

from pathlib import Path


class Data:
    """Containing data from dicom file and analysis methods"""
    def __init__(self, path):
        super().__init__()

        color_bar = {'x0': 693, 'y0': 71, 'x1': 700, 'y1': 179}  # retrieved manually from IJ
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

    def remove_voids(self):  # TODO: filter function
        # find voids (RGB values?)
        # apply median filter, replacing each pixel with the median of the neighboring pixel values
        # radius=5?
        pass
