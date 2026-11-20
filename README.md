![](./src/logo.001.png)

# Documentation
swepy is a graphical interface to load and analyse shear wave elastography (SWE) cine loops recorded with **Hologic Supersonic** machines (DICOM files).

It converts the colours of each SWE map back to values (wave velocity, shear modulus and Young's modulus) within a region of interest (ROI),
summarises each map by its median, filters out poor-quality maps, and plots the results over time.
Results can be exported to `csv` or `xlsx` files.


## Get started

### Requirements
- Python 3.9 or later, with tkinter (included in the installers from [python.org](https://www.python.org/downloads/) and in Anaconda/Miniforge; on Linux you may need `sudo apt install python3-tk`).
- A DICOM file containing a cine loop
- A working desktop environment for the graphical interface

All package dependencies are installed automatically (they are listed in [pyproject.toml](pyproject.toml)).

### Installation
It is recommended to install swepy in its own virtual environment.

**Windows**
```bash
py -m venv swepy-env
swepy-env\Scripts\activate
pip install git+https://github.com/oseynnes/swepy.git
```

**macOS / Linux**
```bash
python3 -m venv swepy-env
source swepy-env/bin/activate
pip install git+https://github.com/oseynnes/swepy.git
```

If you do not have git, download the repository as a ZIP file from GitHub, unzip it, and run `pip install .` from inside the unzipped folder.
Developers can clone the repository and use `pip install -e .` instead.

### Start the interface
With the virtual environment activated, start the application with:

  ```bash
  swepy
  ```

  or

  ```bash
  python -m swepy_core
  ```

### Basic workflow
1. Load a DICOM file containing a cine loop with **File > Open...** (loading takes a few seconds).
   Several files can be selected: they are opened one after another, with the ROI of the first file.
2. Enter the following parameters, read on the image, then click **Set values**:
    - acquisition frequency of SWE maps (`SWE fhz`, e.g. "Pen/2.0 Hz" under "SWE" on the left of the screen).
    - maximal scale value (`max. scale`, e.g. "≥300 kPa" or "≥20.0 m/s" above the colour bar).
    - the variable of the scale (**Scale variable**): **V (m/s)** for a scale in m/s; for a scale in kPa,
      **E (kPa)** if the scanner displays Young's modulus or **μ (kPa)** if it displays shear modulus.
      The Mach30 can display either, and the image only shows "kPa": check the scanner's elasticity setting
      (and record it in your protocol). A wrong choice changes all values by a factor of 3.

   Enlarged copies of both labels are shown under the entries, to read them easily. swepy remembers the values
   entered for each label: files showing the same labels are filled in automatically, and new labels must be entered.

   <p>
   <img src="./src/sc1.png" alt="SWE frequency label on the scanner screen" width="200">
   <img src="./src/sc2.png" alt="Maximal scale label above the colour bar" width="200">
   </p>

   ![Image processing tab](./src/sc0.png)

3. Adjust the ROI on either view (**ROI shape**: rectangle or polygon). A rectangle within the SWE box is suggested; **Reset ROI** restores it.
4. Optionally, click **Value map** to check the ROI before analysing (see below).
5. Click **Analyse**.
6. View and export results from the **Results** tab.

   ![Results tab](./src/sc3.png)

### Value map
The colour-coded SWE map is hard to read by eye, especially for values at the bottom of the scale.
**Value map** shows the values decoded by swepy over the whole SWE box, one SWE map at a time (slider), with the
current ROI outlined and the median value at each depth (right panel; dashed line: all maps).
Use it to check where the ROI lies relative to heterogeneities before analysing: stiff structures such as aponeuroses
or fascia appear as bright bands or peaks in the depth profile, and areas without SWE signal are left blank.
Draw the ROI within the tissue of interest, away from them.
In the **Results** tab, **Value map** shows the analysed ROI of each map, with excluded maps labelled, to check unusual values.

<p align="center">
<img src="./src/value_map.png" alt="Value map window" width="520">
</p>

### Results and outputs
The **main result** of each recording is the **mean of the medians of the included SWE maps**, in the variable
and unit measured (the **Scale variable** chosen for the analysis). It is given first in the summary
(`mean_of_map_medians`, with the measured `variable`, such as "Shear modulus (kPa)") and highlighted in the table window and in Excel files, together with the per-map median of that
variable. The measured variable is listed before the two others, which are converted from it.

The **Results** tab plots the median of each SWE map over time, with the spread of values within each map
(interquartile range, shaded) and the mean of map medians (dashed line); in aponeurosis mode, the muscle reference
is plotted too. Maps excluded by the quality filters are shown as grey crosses, labelled with the reason for exclusion.
*Plot: Distributions* shows the distribution of values in each map instead (violin plots). **Display in table** shows the summary and per-map tables,
and **Value map** shows the analysed ROI map by map.

**Quality filters** are set in the Results tab: maximal % of void pixels (default 20 %), maximal % of saturated pixels
(default 5 %), and time to ignore at the start of the recording (default 0 s). **Apply** re-applies them to all
analysed files in the list (no new analysis needed) and to future analyses; **Defaults** restores the default values.

**Export (CSV or Excel)** writes, next to each DICOM file:
- a **summary** (Excel sheet `summary`, or `<name>_summary.csv`): one value per recording.
  It starts with the main result (`mean_of_map_medians`, in the measured `variable`), followed by the same statistic
  for each variable (`<variable>_mean_of_map_medians`).
  It also gives the variation between maps (`SD`, `CV%`), the median spread within maps (`median_IQR_within_maps`),
  the number of included and excluded maps with the reasons for exclusion (`exclusion_reasons`), the analysis
  settings, and a `scale_warning` (see below).
- a **per-map table** (Excel sheet `per_map`, or `<name>.csv`): one row per SWE map, with its DICOM frame number,
  time (s), inclusion flag and reason for exclusion (`exclusion_reason`), % void and saturated pixels,
  and median, IQR, mean and SD of each variable.

**Combine selection...** writes one table with the summaries of the files selected in the list
(e.g. repeated acquisitions of the same condition), followed by their mean, SD and CV% between files.
The mean, SD and CV% of `mean_of_map_medians` are only given if all files were measured with the same variable.

Variables: wave velocity (m/s), shear modulus μ (kPa) and Young's modulus E (kPa).

### Settings and cached results
swepy remembers your last inputs and recent files, and caches analysis results so they can be reloaded from the **Results** tab.
These are stored in a user folder, independent of where swepy is installed:
- Windows: `%APPDATA%\swepy`
- macOS: `~/Library/Application Support/swepy`
- Linux: `~/.local/share/swepy`

Set the `SWEPY_HOME` environment variable to use another folder.

### Aponeurosis mode
For thin structures such as aponeuroses, enable the aponeurosis mode in **Edit > Settings** (hidden by default),
then choose **ROI shape: Aponeurosis**. swepy locates the aponeurosis on the
B-mode image (suggested automatically, or followed from a click on it), and measures SWV in a standard band of
±1 mm around it, together with a muscle reference band 3–8 mm away. **Apo (manual)** builds the same band from
points clicked along the aponeurosis. Quality descriptors (depth, tilt, distance from the SWE box edge, visibility)
are exported with the results (`apo_` fields).

See the step-by-step guide: [docs/aponeurosis_mode.md](docs/aponeurosis_mode.md).

### How the analysis works
1. **One frame per SWE map.** SWE maps are refreshed less often than B-mode frames, so a cine loop shows each map over several frames.
   swepy detects the refreshes from the images (spikes in frame-to-frame change within the SWE box) and keeps the middle frame of each map.
   The `SWE fhz` value is used as a starting estimate, because actual refresh rates differ slightly from the nominal ones (e.g. every 13 frames for "1.6 Hz" at 20 frames/s).
   The DICOM frame number of each retained frame is exported in the `dicom_frame` column.
2. **Colour to value.** The colour bar shown in the image gives the colour scale (0 at the bottom, `max. scale` at the top).
   Each pixel's colour is placed along the bar's colour gradient, between the two closest bar colours, which gives its value.
   Scanners draw maps with many more colours than the ~110 rows of the bar (e.g. 1370 colours in an uncompressed
   Mach30 export), so this recovers values between bar rows instead of rounding them to the nearest row.
   The earlier method (nearest bar row, *Raw colour bar*) can be chosen in Edit > Settings > Colour decoding;
   the method used is recorded in each result (`colour_decoding`).
   The colour bar is linear in modulus, even when its scale is displayed in m/s, which swepy takes into account.
3. **Void pixels.** Pixels without colour (no SWE signal) are excluded.
4. **Statistics.** Each map is summarised by the median of its pixels, which is robust to the skewed distributions
   and stiff inclusions typical of muscle maps (IQR, mean and SD are also given). Velocity, shear modulus (μ = ρv², ρ = 1000 kg/m³)
   and Young's modulus (E = 3μ) are converted pixel by pixel.
5. **Quality filters** (Results tab). Maps are excluded from the summary if they contain more than 20 % void pixels
   or 5 % saturated pixels, or if they were recorded within a chosen time after the start of the recording (default 0 s,
   e.g. to let probe pressure settle). Thresholds can be changed and are stored with each result.
   Saturated pixels are those above 98 % of the max. scale (Edit > Settings).
6. **Stability check.** The 5 consecutive included maps with the least variable medians are flagged
   (`in_5_most_stable_maps`) and their mean is reported. Because this selection is based on the result itself,
   it is meant as a check, not as the main outcome.
7. **Scale check.** The median colour level of included pixels is reported (out of ~110 levels in the colour bar).
   Below 10 levels, the resolution of the measurement is limited: `scale_warning` is set and a short note is shown
   on the plot. For future recordings, a lower max. scale on the scanner gives finer resolution.

### Measuring reliably
Frames of one recording share the same probe placement, so they cannot capture the main sources of measurement error.
- **Standardise acquisition:** probe aligned with the muscle fascicles (shear wave speed depends strongly on orientation in muscle),
  minimal pressure with a thick gel layer, fixed joint angle, verified rest (e.g. EMG) when measuring passive muscle.
- **Choose the lowest max. scale that does not saturate**, so the tissue spans many colour levels.
- **Draw the ROI within the muscle**, away from aponeuroses and fascia (check with **Value map**), at a consistent depth.
- **Record several acquisitions** (e.g. 3, repositioning the probe each time), use the mean of their results,
  and assess reliability between acquisitions (e.g. ICC, SEM, CV) with **Combine selection...**.
- During contractions or other changes over time, select maps with an external criterion (e.g. stable force),
  using the `time_s` column to synchronise SWE maps with other recordings.
- For muscle, the shear modulus or the wave velocity are often preferred to Young's modulus, because E = 3μ assumes an isotropic tissue.
  Whatever the scanner displays, swepy converts values to all three variables.

### Notes and limitations
- The analysis currently works only for cine loops.
- **Resolution:** the colour bar has ~110 rows (≈2.7 kPa per row for a 300 kPa scale, 11 kPa for 1200 kPa).
  Values between rows are recovered from intermediate colours, but compression noise (lossy JPEG exports) blurs colours
  by about one row per pixel. Tissue values at the bottom of the scale (dark blues) are the least accurate:
  use the lowest scale that avoids saturation, so the tissue spans many colour levels.
- **DICOM export:** lossy JPEG exports (≈9 MB per clip) were within 1 % of uncompressed ones (≈230 MB) for the main result
  in our tests, with tissue mid-scale. Lossless exports (≈70 MB) keep exact colours, if maximal precision is needed.
- The SWE map **opacity** must be set to 100 % on the scanner (colours blended with the B-mode image cannot be decoded).
- The position of the colour bar in the image is fixed for the Mach30 screen layout. Check results on other layouts.
- The percentage of saturated pixels is relative to the whole ROI (void pixels included).
- The value map display is not available for results cached by versions older than 0.2.0 (analyse the file again).
- Version 0.2.0 changed the frame selection, the colour bar sampling and the conversion of m/s scales: results can differ from earlier versions, especially for scales in m/s and for soft tissue measured with a large scale.
- Version 0.3.0 decodes colours between colour bar rows (see "How the analysis works"): results change little for tissue mid-scale
  (< 2 % in our tests) but can change more for tissue at the bottom of the scale.
- swepy works with **DICOM files** and is optimised for Mach30 machines but should work with other machines from the Mach range.
  Scans from Aixplorer machines also seem to be compatible but have not yet been tested thoroughly.

## Acknowledgements
I am grateful to Neil Cronin (University of Jyväskylä) for his input early in the project.  
I also thank Valentin Doguet, Antoine Nordez and Aurélie Sarcher (Nantes Université) for sharing their experience and views,
based on the development or utilisation of the excellent [ElastoGUI](https://mip.univ-nantes.fr/fr/brevets-logiciels).
The latest modifications and bug fixes were assisted with AI (Claude Opus 5.5).


## Citation
swepy is a project developed at the Norwegian School of Sport Sciences.
If needed, this code can be referenced from the cff file of this repository, or as follows:
```
@software{Seynnes_swepy_2023,
author = {Seynnes, Olivier},
license = {MIT},
month = apr,
title = {{swepy}},
url = {https://github.com/oseynnes/swepy},
year = {2023}
}
```

