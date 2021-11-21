from tkinter import filedialog as fd

from PIL import ImageTk, Image
from pydicom import dcmread
from pydicom.pixel_data_handlers.util import convert_color_space
import numpy as np


class Data:
    def __init__(self):
        super().__init__()
        self.path = None
        self.img_name = None
        self.ds = None
        self.img_array = None
        self.roi_coords = None

    def select_file(self):
        filetypes = (('dicom files', '*.dcm'), ('All files', '*.*'))
        self.path = fd.askopenfilename(initialdir='/', title="Select dicom file", filetypes=filetypes)

    def load_dicom(self):
        self.select_file()
        self.img_name = self.path.split('/')[-1]  # TODO: check that this works on Windows
        self.ds = dcmread(self.path)
        img_array_raw = self.ds.pixel_array
        self.img_array = convert_color_space(img_array_raw, 'YBR_FULL_422', 'RGB', per_frame=True)

    def resample(self, swe_fhz=1.0):  # TODO: select unique SWE frames (NB: 2nd frame comes at index 3 or 4)
        pass

    def remove_voids(self):  # TODO: filter function
        # find voids (RGB values?)
        # apply median filter, replacing each pixel with the median of the neighboring pixel values
        # radius=5?
        pass