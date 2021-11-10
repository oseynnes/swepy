import tkinter as tk
from tkinter import ttk, filedialog as fd
from tkinter.messagebox import showinfo

from PIL import ImageTk, Image
from pydicom import dcmread
from pydicom.pixel_data_handlers.util import convert_color_space
import numpy as np


class SwePy(tk.Tk):
    def __init__(self):
        super().__init__()
        self.path = None
        self.ds = None
        self.img_array = None
        self.img = None
        self.frame = 0
        self.x = self.y = 0
        self.roi_coords = np.empty([4, ])

        self.title('SWE image viewer')
        window_width = 1000
        window_height = 650
        # get the screen dimension
        screen_width = self.winfo_screenwidth()
        screen_height = self.winfo_screenheight()
        # find the center point
        center_x = int(screen_width / 2 - window_width / 2)
        center_y = int(screen_height / 3 - window_height / 3)
        # set the position of the window to the center of the screen
        self.geometry(f'{window_width}x{window_height}+{center_x}+{center_y}')
        # set-up window grid
        self.columnconfigure(0, weight=1)
        self.columnconfigure(1, weight=4)

        # menu left
        self.menu_left = ttk.Frame(self)
        self.menu_left.grid(row=1, column=0, rowspan=2, sticky=tk.NSEW)
        # left menu widgets
        self.btn_open = ttk.Button(self.menu_left, text="Open dicom file", command=self.get_dicom).pack(fill='x')
        self.btn_fhz = ttk.Button(self.menu_left, text="Enter SWE Freq.").pack(fill='x')  # later to call entry box
        self.btn_analyse = ttk.Button(self.menu_left, text="Analyse").pack(fill='x')

        # image frame and canvas
        self.img_frame = ttk.Frame(self)
        self.canvas = tk.Canvas(self.img_frame, width=720, height=540, bg='black', cursor="cross")
        self.canvas.grid(row=1, column=1, rowspan=3, sticky=tk.NSEW, padx=5, pady=5)
        self.img_frame.grid(row=1, column=1, rowspan=3, sticky=tk.NSEW, padx=5, pady=5)

        # image name
        self.img_name_frame = ttk.Frame(self)
        self.img_name_frame.grid(row=0, column=1, sticky=tk.EW)
        self.img_name = tk.Label(self.img_name_frame, text="some name")
        self.img_name.pack()

        # draw region of interest
        self.canvas.bind("<Button-1>", self.on_button_press)
        self.canvas.bind("<B1-Motion>", self.on_move_press)
        self.canvas.bind("<ButtonRelease-1>", self.on_button_release)
        self.rect = None
        self.start_x = None
        self.start_y = None

        # controls
        self.controls_frame = ttk.Frame(self)
        self.controls_frame.grid(row=4, column=1, sticky=tk.EW)
        self.play_btn = ttk.Button(self.controls_frame, text="Play")
        self.play_btn['command'] = self.play_video
        self.play_btn.pack()

    def select_file(self):
        filetypes = (('dicom files', '*.dcm'), ('All files', '*.*'))
        self.path = fd.askopenfilename(initialdir='/', title="Select dicom file", filetypes=filetypes)

    def get_dicom(self):
        self.select_file()
        self.ds = dcmread(self.path)
        img_array_raw = self.ds.pixel_array
        self.img_array = convert_color_space(img_array_raw, 'YBR_FULL_422', 'RGB', per_frame=True)
        self.set_image()

    def set_image(self):
        print(f'{self.frame} / {self.ds.NumberOfFrames}')
        self.img = ImageTk.PhotoImage(image=Image.fromarray(self.img_array[self.frame]))  # make it "usable" in tkinter
        self.canvas.create_image(0, 0, anchor=tk.NW, image=self.img)  # set image obj on the canvas at position (0, 0)

    def play_video(self):
        if self.ds:
            while self.frame < self.ds.NumberOfFrames:
                self.set_image()
                self.frame += 1
                self.after(50, self.play_video)  # 50ms
        else:
            showinfo(title='No video', message='Please load a Dicom file first')
            return


    def on_button_press(self, event):
        # save mouse drag start position
        self.start_x = self.canvas.canvasx(event.x)
        self.start_y = self.canvas.canvasy(event.y)
        # create rectangle if not yet exist
        if not self.rect:
            self.rect = self.canvas.create_rectangle(self.x, self.y, 1, 1, outline='red')

    def on_move_press(self, event):
        cur_x, cur_y = (event.x, event.y)
        # expand rectangle as you drag the mouse
        self.canvas.coords(self.rect, self.start_x, self.start_y, cur_x, cur_y)

    def on_button_release(self):
        self.roi_coords = np.array(self.canvas.coords(self.rect))
        print(self.roi_coords.shape)


if __name__ == '__main__':
    app = SwePy()
    app.mainloop()
