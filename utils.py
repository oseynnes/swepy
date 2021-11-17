import tkinter.messagebox
from tkinter.messagebox import showinfo, showerror


def warn_no_video():
    showinfo(title='No video', message='Please load a Dicom file first')


def warn_no_number():
    showerror(title='Wrong input', message='Please enter a number')



def set_win_geometry(container, width, height):
    screen_width = container.winfo_screenwidth()
    screen_height = container.winfo_screenheight()
    center_x = int(screen_width / 2 - width / 2)
    center_y = int(screen_height / 3 - height / 3)
    container.geometry(f'{width}x{height}+{center_x}+{center_y}')