import tkinter
from pathlib import Path

import detecta
import numpy as np
import scipy.io as sio
from pydicom import dcmread
from pydicom.pixel_data_handlers.util import convert_color_space
from skimage.draw import polygon

from src.src_utils import get_project_root
from swepy.app import app_utils
from swepy.processing import data_utils


class DcmData:
    """Containing data from DICOM file and analysis methods"""

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
        self.roi_shape = None
        self.top_fov_coords = None
        self.bmode_fhz = None
        self.swe_fhz = None
        self.max_scale = None
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
        rois = self.ds.SequenceOfUltrasoundRegions._list
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
        self.top_fov_coords = self.get_roi_coord(self.top_fov)
        self.bmode_fhz = float(self.ds.RecommendedDisplayFrameRate)
        img_array_raw = self.ds.pixel_array
        if (0x0008, 0x2111) in self.ds and 'Lossy' in self.ds[
            0x0008, 0x2111].value:  # check if there was lossy compression
            self.img_array = convert_color_space(img_array_raw, 'YBR_FULL_422', 'RGB', per_frame=True)
        else:
            self.img_array = img_array_raw

    def detect_unique_swe(self):
        """Retrieve indices of frames with unique SWE ROI"""
        all_rois = self.get_rois(self.img_array)
        mean_colour = all_rois.mean(axis=(1, 2))
        colour_shifts = np.diff(mean_colour)
        indices = detecta.detect_peaks(x=abs(colour_shifts),
                                       # mph=np.std(colour_shifts) * 0.1,
                                       edge='both',
                                       show=False)
        # indices = np.where(abs(colour_shifts) > 0.04)[0] + 1  # used 0.024 in files from Aixplorer
        return indices

    def resample(self, swe_fhz=1.0):
        """resample scan sequence to only retain 1st scans with unique SWE data"""
        unique_swes = self.detect_unique_swe()
        if self.bmode_fhz % swe_fhz == 0:
            frame_step = int(self.bmode_fhz // swe_fhz)
        else:
            frame_step = int(self.bmode_fhz // swe_fhz + 1)

        # NB: 2nd frame comes at indices between 1 and 5
        first_updated_frame = unique_swes[0] if unique_swes[0] < frame_step else frame_step + 1
        swe_indices = np.arange(start=first_updated_frame, stop=self.img_array.shape[0],
                                step=frame_step)  # only works for sequences!
        # swe_indices = np.insert(swe_indices, 0, 0)
        self.swe_array = self.img_array[swe_indices, :, :]
        return self.swe_array

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

    def get_external_cmap(self):
        """"Retrieve colour map from external file"""
        cmap_path = get_project_root() / 'src/colormap.mat'
        cmap = sio.loadmat(str(cmap_path))
        cmap_arr = cmap['map']
        scaled_cmap = (cmap_arr * 255).astype(int)
        scaled_cmap = np.flip(scaled_cmap, 0)
        return scaled_cmap

    def set_colour_scale(self, cmap_loc):
        """
        Thin colour map to one pixel width and set matching scale based on max. scale value
        Returns: colour profile and corresponding "real values" of velocity or modulus
        """
        if cmap_loc == 'local_cmap':
            colour_bar = {'x0': 693, 'y0': 70, 'x1': 701, 'y1': 180}  # retrieved manually from IJ
            scale_arr = self.img_array[0][colour_bar['y0']:colour_bar['y1'],
                        colour_bar['x0']:colour_bar['x1'],
                        :]
            # 2D array for single pxl colour scale, with width 3 (r, g, b)
            self.colour_profile = scale_arr.mean(axis=1, dtype=int)
        elif cmap_loc == 'external_cmap':
            self.colour_profile = self.get_external_cmap()  # reference to a standard colour map (Elastogui)
        # 1D array of values matching colour profile (velocity or modulus)
        self.real_values = np.linspace(self.max_scale, 0, self.colour_profile.shape[0])

    def analyse_roi(self, cmap_loc):
        """Calculate stat parameter of interest for ROIs of each frame"""
        self.rois = self.get_rois(self.swe_array)
        self.set_colour_scale(cmap_loc)
        filter_mask = self.void_filter()
        indices = data_utils.closest_rgb(self.rois, self.colour_profile)
        self.mapped_values = self.real_values[indices]
        self.filtered_values = np.where(filter_mask, self.mapped_values, np.nan)

        saturated_pxls = self.filtered_values > self.max_scale * self.sat_thresh_var.get() / 100
        self.saturated_percent = self.calc_pixel_percent(saturated_pxls)

        voided_pxls = np.isnan(self.filtered_values)
        self.void_percent = self.calc_pixel_percent(voided_pxls)
        if np.all(self.void_percent == 100):
            app_utils.warn_no_swe_data()
            exit()
        else:
            self.gen_results()

    def gen_results(self):
        """Generate 3 sets of results for velocity, shear and Young's modulus"""
        target_vars = ['velocity', 'shear_m', 'youngs_m']
        d = {'file': [self.path.stem, self.path.parent],
             'roi_coords': self.roi_coords,
             'roi_shape': self.roi_shape,
             'raw': {},
             'stats': {}}
        d['stats']['%_void'] = self.void_percent
        d['stats'][f'%_saturated (> {self.sat_thresh_var.get()}% maxscale)'] = self.saturated_percent
        for target_var in target_vars:
            if target_var == self.analysis_swe_var:
                d['raw'][target_var] = self.filtered_values
            else:
                d['raw'][target_var] = data_utils.convert_swe(self.filtered_values,
                                                              self.analysis_swe_var,
                                                              target_var)
            filtered = d['raw'][target_var]
            d['stats']['_'.join((target_var, 'median'))] = np.nanmedian(filtered, axis=1)
            d['stats']['_'.join((target_var, 'mean'))] = np.nanmean(filtered, axis=1)
            d['stats']['_'.join((target_var, 'SD'))] = np.nanstd(filtered, axis=1)
        self.results = d
        self.mean = np.nanmean(self.filtered_values)
        self.median = np.nanmedian(self.filtered_values)


if __name__ == '__main__':
    import pandas as pd
    import seaborn as sns
    import matplotlib.pyplot as plt

    filepath = Path('../../test_files/C0000001_LOSSY.dcm')
    data = DcmData(filepath)

    data.load_dicom()
    data.resample(1)
    data.max_scale = 20
    # data.resample(1.1)
    # data.max_scale = 1200
    data.set_colour_scale('local_cmap')
    plt.imshow(data.swe_array[0, :, :, :])

    # analyse_roi()
    data.rois = data.get_rois(data.swe_array)
    data.set_colour_scale('local_cmap')
    filter_mask = data.void_filter()
    indices = data_utils.closest_rgb(data.rois, data.colour_profile)
    data.mapped_values = data.real_values[indices]

    # inspect mapped values
    df = pd.DataFrame(data.mapped_values.T)
    df_long = pd.melt(df, var_name="frame", value_name="modulus")
    fig1, (ax1, ax2) = plt.subplots(nrows=2)
    g1 = sns.stripplot(x="frame", y="modulus", data=df_long,
                       linewidth=1, ax=ax1, size=1)
    g2 = sns.violinplot(x="frame", y="modulus", data=df_long,
                        linewidth=1, ax=ax2)
    plt.show()

    # plot modulus stats for each frame
    x_start, y_start = data.roi_coords[0][0] + 1, data.roi_coords[0][1] + 1
    x_stop, y_stop = data.roi_coords[1][0] - 1, data.roi_coords[1][1] - 1  # adjusted to avoid ROI frame
    rois = data.swe_array[:, y_start:y_stop, x_start:x_stop, :]
    roi0 = rois[0]
    rois_indices = data_utils.closest_rgb(roi0, data.colour_profile)
    roi0_values = data.real_values[rois_indices]

    # plot zoomed and rescaled ROI
    # extent = [x_start, x_stop, y_start, y_stop]
    # fig2 = plt.figure()
    # ax = fig2.add_subplot(111)
    # im = ax.imshow(roi0_values, extent=extent, origin='lower', interpolation='None', cmap='viridis')
    # fig2.colorbar(im)
