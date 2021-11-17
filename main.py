import tkinter as tk
from tkinter import ttk

import numpy as np
from PIL import ImageTk, Image

import utils
from processing import Data


class UsrEntry(tk.Toplevel):
    def __init__(self, parent):
        super().__init__()
        self.swe_fhz = None

        utils.set_win_geometry(self, 200, 100)
        self.resizable(False, False)
        self.title('SWE frequency')

        self.usr_value = tk.StringVar()
        swe_fhz_entry = ttk.Entry(self, textvariable=self.usr_value)
        swe_fhz_entry.pack(padx=10, pady=10)
        swe_fhz_entry.focus()
        save_button = ttk.Button(self, text='Save', command=self.save_fhz)
        save_button.pack()

    def save_fhz(self):
        try:
            float(self.usr_value.get())
        except ValueError:
            utils.warn_no_number()
            self.destroy()
            return
        app.swe_fhz = self.usr_value.get()
        self.destroy()
        if 'swe_row' in app.tv.get_children():
            app.tv.delete('swe_row')
        app.tv.insert(parent='', index=tk.END, iid='swe_row', values=('SWE frequency', app.swe_fhz))


class SwePy(tk.Tk):
    def __init__(self):
        super().__init__()
        options = {'fill': 'x', 'padx': 5, 'pady': 5}
        self.data = None
        self.img = None
        self.frame = 0
        self.x = self.y = 0
        self.roi_coords = np.empty([4, ])
        self.swe_fhz = None  # TODO: find a way pass it to Data class or change structure to save variables elsewhere

        self.title('SwePy')
        window_width = 1150
        window_height = 700
        utils.set_win_geometry(self, window_width, window_height)
        self.columnconfigure(0, weight=1)
        self.columnconfigure(1, weight=4)

        # Left menu
        self.left_panel = ttk.Frame(self)
        self.left_panel.grid(row=1, column=0, rowspan=2, sticky=tk.NSEW)
        # left menu buttons
        self.btn_open = ttk.Button(self.left_panel, text="Open dicom file", command=self.load_file).pack(**options)
        self.btn_fhz = ttk.Button(self.left_panel, text="Enter SWE Freq.", command=self.call_usr_entry)
        self.btn_fhz.pack(**options)
        self.btn_analyse = ttk.Button(self.left_panel, text="Analyse").pack(**options)  # TODO: link to methods (class?)
        # Left menu info table
        columns = ('dcm_property', 'value')
        self.variables = (None,)
        self.values = (None,)
        self.tv = ttk.Treeview(self.left_panel, columns=columns, show='headings')
        self.tv.heading('dcm_property', text="DCM Property")
        self.tv.heading("value", text="Value")
        self.tv.pack(**options)

        # image frame and canvas
        self.img_frame = ttk.Frame(self)
        self.canvas = tk.Canvas(self.img_frame, width=720, height=540, bg='black', cursor="cross")
        self.canvas.grid(row=1, column=1, rowspan=3, sticky=tk.NSEW, padx=5, pady=5)
        self.img_frame.grid(row=1, column=1, rowspan=3, sticky=tk.NSEW, padx=5, pady=5)

        # image name
        self.img_name_frame = ttk.Frame(self)
        self.img_name_frame.grid(row=0, column=1, sticky=tk.EW)
        self.img_name = ttk.Label(self.img_name_frame, text=None)
        self.img_name.pack(**options)

        # draw region of interest
        self.canvas.bind("<Button-1>", self.on_button_press)
        self.canvas.bind("<B1-Motion>", self.on_move_press)
        self.canvas.bind("<ButtonRelease-1>", self.on_button_release)
        self.rect = None
        self.start_x = None
        self.start_y = None

        # controls (bottom)
        self.controls_frame = ttk.Frame(self)
        self.controls_frame.grid(row=4, column=1, sticky=tk.EW)

        self.current_value = tk.DoubleVar()
        self.slider = ttk.Scale(self.controls_frame, from_=0, to=0, variable=self.current_value)
        self.slider['state'] = 'disabled'
        self.slider['command'] = self.update_slider
        self.slider.pack(**options)

        self.pause = False  # control video pause
        self.play_btn = ttk.Button(self.controls_frame, text="Play")
        self.play_btn['command'] = self.toggle_play_pause
        self.play_btn.pack(**options)

    def call_usr_entry(self):
        # if self.data:
            usr_entry = UsrEntry(self)
            usr_entry.grab_set()
        # else:
        #     utils.warn_no_video()
        #     return

    def get_frame(self):
        self.img = ImageTk.PhotoImage(
            image=Image.fromarray(self.data.img_array[self.frame]))  # make it "usable" in tkinter
        self.canvas.create_image(0, 0, anchor=tk.NW, image=self.img)  # set image obj on the canvas at position (0, 0)

    def view_dicom(self):
        # TODO: link to a ttk.Progressbar widget (dicom loading is a few seconds)
        self.data = Data()
        self.data.load_dicom()
        self.get_frame()

    def update_slider(self, event):
        self.frame = int(self.current_value.get())
        self.get_frame()

    def toggle_play_pause(self):
        if self.pause:
            self.pause = False
            self.play_btn.config(text='Play')
            self.after_cancel(self.after_id)
        else:
            self.pause = True
            self.play_btn.config(text='Pause')
            self.play_video()

    def play_video(self):
        if self.data:
            self.current_value.set(self.frame)
            self.get_frame()
            self.frame += 1
            if self.frame < self.data.ds.NumberOfFrames:
                self.after_id = self.after(50, self.play_video)  # 50ms
            else:
                self.pause = False
                self.play_btn.config(text='Play')
                self.frame = 0
        else:
            utils.warn_no_video()
            return

    def set_img_name(self):
        self.img_name.config(text=self.data.img_name)

    def activate_slider(self):
        self.slider.config(to=self.data.ds.NumberOfFrames)  # set max number of frames
        self.slider.config(state='normal')  # activate slider
        self.values = (self.data.ds.NumberOfFrames,
                       self.data.ds.Rows,
                       self.data.ds.Columns,
                       self.data.ds.RecommendedDisplayFrameRate)  # get dcm info
        self.variables = ('No. of frames',
                          'No. of rows',
                          'No. of columns',
                          'B mode Fhz')

    def update_dcm_info(self, labels, content):
        rows = (zip(labels, content))
        for row in rows:
            self.tv.insert(parent='', index=tk.END, values=row)

    def load_file(self):
        self.view_dicom()
        self.activate_slider()
        self.update_dcm_info(self.variables, self.values)
        self.set_img_name()

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

    def on_button_release(self, event):
        self.data.roi_coords = np.array(self.canvas.coords(self.rect))


if __name__ == '__main__':
    app = SwePy()
    app.mainloop()

# TODO: - move frames and canvas to subclasses
#       - add doctrings to class(es) and functions
