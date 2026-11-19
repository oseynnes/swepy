"""Per-map statistics, quality filtering and summaries of SWE results.

Rationale (see README, "Measuring reliably"):
    - SWE maps are often heterogeneous (stiff aponeuroses, fascia, depth effects) and pixel values are
      skewed, so each map is summarised by its median rather than its mean.
    - Maps are kept or excluded with explicit quality criteria (void and saturated pixels, settling time).
    - A recording is summarised by the mean of its per-map medians; variation between maps is reported.
    - Several recordings of the same condition can be combined, to assess between-acquisition reliability.
"""
import warnings

import numpy as np
import pandas as pd

from swepy_core.processing import data_utils

SWE_VARS = ('velocity', 'shear_m', 'youngs_m')
UNITS = {'velocity': 'm/s', 'shear_m': 'kPa', 'youngs_m': 'kPa'}
LABELS = {'velocity': 'Wave velocity', 'shear_m': 'Shear modulus', 'youngs_m': "Young's modulus"}

# default quality filters: settings keys (upper case) and default values
DEFAULT_QUALITY = {'max_void_pct': 20.0,       # maps with more void pixels (no SWE signal) are excluded
                   'max_saturated_pct': 5.0,   # maps with more saturated pixels are excluded
                   'ignore_first_s': 0.0}      # maps recorded during the first seconds (probe settling)
MAIN_STAT = 'mean_of_map_medians'  # main result: mean of the medians of included maps
MIN_COLOUR_LEVELS = 10  # below this median colour level, the colour scale is too coarse for the tissue
N_STABLE_MAPS = 5


def measured_var(results):
    """Return the variable measured from the colour scale (as chosen in the GUI)"""
    swe_var = results.get('meta', {}).get('analysis_variable')
    return swe_var if swe_var in SWE_VARS else None


def ordered_vars(first=None):
    """SWE variables, starting with the given one (e.g. the measured variable)"""
    if first not in SWE_VARS:
        return SWE_VARS
    return (first,) + tuple(var for var in SWE_VARS if var != first)


def get_quality_settings():
    """Return quality filter thresholds from user settings, or defaults"""
    quality = dict(DEFAULT_QUALITY)
    for key in quality:
        value = data_utils.get_settings(key.upper())
        if value not in ([], None, ''):
            try:
                quality[key] = float(value[0] if isinstance(value, list) else value)
            except (TypeError, ValueError):
                pass
    return quality


def per_map_stats(values):
    """Median, inter-quartile range, mean and SD of each map, ignoring void (NaN) pixels
    Args:
        values: 2D array (maps, pixels)
    Returns: dict of 1D arrays
    """
    with warnings.catch_warnings():
        warnings.simplefilter('ignore', category=RuntimeWarning)  # all-void maps give NaN
        p25, median, p75 = np.nanpercentile(values, [25, 50, 75], axis=1)
        return {'median': median,
                'IQR': p75 - p25,
                'mean': np.nanmean(values, axis=1),
                'SD': np.nanstd(values, axis=1),
                'q25_median_q75': (p25, median, p75)}


def exclusion_reasons(void_pct, saturated_pct, time_s, quality):
    """Reason(s) for excluding each map ('' for maps passing the quality filters)"""
    reasons = []
    for void, sat, t in zip(*(np.asarray(a, dtype=float) for a in (void_pct, saturated_pct, time_s))):
        r = []
        if void >= 100:
            r.append('no SWE data')
        elif void > quality['max_void_pct']:
            r.append(f"void {void:.0f}% > {quality['max_void_pct']:g}%")
        if sat > quality['max_saturated_pct']:
            r.append(f"saturated {sat:.0f}% > {quality['max_saturated_pct']:g}%")
        if t < quality['ignore_first_s']:
            r.append(f"before {quality['ignore_first_s']:g} s")
        reasons.append('; '.join(r))
    return np.array(reasons, dtype=object)


def reason_category(reason):
    """Reason without the map's own values (e.g. 'void > 20%'), to count maps per reason"""
    import re
    return re.sub(r'(void|saturated) \d+% ', r'\1 ', reason)


def quality_mask(void_pct, saturated_pct, time_s, quality):
    """Return boolean array of maps passing the quality filters"""
    void_pct, saturated_pct, time_s = (np.asarray(a, dtype=float) for a in (void_pct, saturated_pct, time_s))
    return ((void_pct <= quality['max_void_pct'])
            & (void_pct < 100)
            & (saturated_pct <= quality['max_saturated_pct'])
            & (time_s >= quality['ignore_first_s']))


def most_stable_maps(medians, included, n=N_STABLE_MAPS):
    """Flag the n consecutive included maps whose medians vary least (stability check)
    Returns: boolean array (same length as medians), all False if fewer than 2 maps are included
    """
    mask = np.zeros(len(medians), dtype=bool)
    kept = np.flatnonzero(included & ~np.isnan(medians))
    if len(kept) < 2:
        return mask
    _, sub_mask = data_utils.mean_lowest_stdev_subarray(np.asarray(medians)[kept], return_mask=True, n=n)
    mask[kept[sub_mask]] = True
    return mask


def apply_quality(results, quality=None):
    """(Re)apply quality filters to analysis results, in place (no re-analysis needed)

    Updates the 'included' and stability flags of each map, the scale check and the filter settings.
    Args:
        results (dict): analysis results
        quality (dict): thresholds (see DEFAULT_QUALITY); user settings if None
    Returns: results
    """
    quality = quality or get_quality_settings()
    stats = results['stats']
    n_maps = len(stats['%_void'])
    reasons = exclusion_reasons(stats['%_void'], _saturated(stats), stats.get('time_s', np.zeros(n_maps)), quality)
    included = reasons == ''
    stats['included'] = included
    stats['exclusion_reason'] = reasons
    meta = results.setdefault('meta', {})
    swe_var = meta.get('analysis_variable')
    if swe_var and f'{swe_var}_median' in stats:
        stats[f'in_{N_STABLE_MAPS}_most_stable_maps'] = most_stable_maps(np.asarray(stats[f'{swe_var}_median']),
                                                                         included)
    if 'median_colour_level' in stats:
        levels = np.asarray(stats['median_colour_level'], dtype=float)[included]
        levels = levels[~np.isnan(levels)]
        level = float(np.median(levels)) if len(levels) else np.nan
        meta['median_colour_level'] = level
        meta['scale_warning'] = bool(level < MIN_COLOUR_LEVELS)
    meta['filter_max_void_%'] = quality['max_void_pct']
    meta['filter_max_saturated_%'] = quality['max_saturated_pct']
    meta['filter_ignore_first_s'] = quality['ignore_first_s']
    return results


def _saturated(stats):
    """Return saturated pixel percentages from stats (column name includes the threshold)"""
    for key, value in stats.items():
        if key.startswith('%_saturated'):
            return np.asarray(value)
    return np.zeros(len(stats['%_void']))


def summarise(results):
    """Summarise one analysed recording
    Args:
        results (dict): analysis results (as generated by DcmData.gen_results, or cached by older versions)
    Returns: dict of summary values (one row of the combined table). The main result (mean of map medians
        of the measured variable, in its unit) comes first; values of the measured variable come before others.
    """
    measured = measured_var(results)
    stats = results['stats']
    n_maps = len(stats['%_void'])
    included = np.asarray(stats.get('included', np.ones(n_maps, dtype=bool)), dtype=bool)
    summary = {'file': results['file'][0],
               'folder': str(results['file'][1]),
               'mean_of_map_medians': np.nan,
               'variable': '',
               'n_maps': n_maps,
               'n_maps_included': int(included.sum()),
               'n_maps_excluded': int((~included).sum()),
               'exclusion_reasons': _count_reasons(stats, included)}
    for var in ordered_vars(measured):
        maps = per_map_stats(results['raw'][var])
        medians = maps['median'][included]
        medians = medians[~np.isnan(medians)]
        if len(medians):
            mean = float(np.mean(medians))
            sd = float(np.std(medians, ddof=1)) if len(medians) > 1 else np.nan
            stable = most_stable_maps(maps['median'], included)
            summary[f'{var}_mean_of_map_medians'] = mean
            summary[f'{var}_SD_between_maps'] = sd
            summary[f'{var}_CV%_between_maps'] = 100 * sd / mean if mean else np.nan
            summary[f'{var}_median_IQR_within_maps'] = float(np.nanmedian(maps['IQR'][included]))
            summary[f'{var}_mean_of_{N_STABLE_MAPS}_most_stable_maps'] = (
                float(np.mean(maps['median'][stable])) if stable.any() else np.nan)
        else:
            for key in ('mean_of_map_medians', 'SD_between_maps', 'CV%_between_maps',
                        'median_IQR_within_maps', f'mean_of_{N_STABLE_MAPS}_most_stable_maps'):
                summary[f'{var}_{key}'] = np.nan
    if 'reference_median' in stats:  # reference ROI (measured variable), e.g. muscle next to an aponeurosis
        ref = np.asarray(stats['reference_median'], dtype=float)[included]
        ref = ref[~np.isnan(ref)]
        summary['reference_mean_of_map_medians'] = float(np.mean(ref)) if len(ref) else np.nan
    if measured:
        summary['mean_of_map_medians'] = summary[f'{measured}_{MAIN_STAT}']
        if 'reference_mean_of_map_medians' in summary:
            summary['ratio_to_reference'] = summary['mean_of_map_medians'] / summary['reference_mean_of_map_medians']
        summary['variable'] = f'{LABELS[measured]} ({UNITS[measured]})'
    first = ('file', 'folder', 'mean_of_map_medians', 'variable', 'reference_mean_of_map_medians',
             'ratio_to_reference')
    summary = {**{k: summary[k] for k in first if k in summary}, **summary}
    summary.update(results.get('meta', {}))
    return summary


def _count_reasons(stats, included):
    """Excluded maps per reason, e.g. 'void > 20%: 2 maps; before 3 s: 1 map' ('' if none)"""
    from collections import Counter
    reasons = stats.get('exclusion_reason')
    if reasons is None:
        return ''
    counts = Counter(reason_category(part) for r in np.asarray(reasons)[~included] for part in str(r).split('; ') if part)
    return '; '.join(f"{k}: {n} map{'s' if n > 1 else ''}" for k, n in counts.items())


def summary_table(results):
    """Summary of one recording as a 2-column table (parameter, value)"""
    summary = summarise(results)
    return pd.DataFrame({'parameter': list(summary), 'value': list(summary.values())})


def per_map_table(results):
    """Per-map statistics as a table (one row per SWE map), measured variable first"""
    df = pd.DataFrame.from_dict(results['stats'])
    general = [c for c in df.columns if not c.startswith(SWE_VARS)]
    by_var = [c for var in ordered_vars(measured_var(results)) for c in df.columns if c.startswith(f'{var}_')]
    return df[general + by_var]


def combine(results_list):
    """Combine summaries of several recordings (e.g. repeated acquisitions of one condition)

    Returns: table with one row per recording and, if there are several, rows with the mean,
        SD and CV% between recordings of each measured value
    """
    df = pd.DataFrame([summarise(results) for results in results_list])
    if len(df) > 1:
        value_cols = [c for c in df.columns if c.startswith(SWE_VARS)]
        if df['variable'].nunique() == 1:  # results comparable (same measured variable)
            value_cols = ['mean_of_map_medians'] + value_cols
        values = df[value_cols].apply(pd.to_numeric, errors='coerce')
        mean, sd = values.mean(), values.std(ddof=1)
        rows = pd.DataFrame([mean, sd, 100 * sd / mean])
        rows.insert(0, 'file', ['Mean between files', 'SD between files', 'CV% between files'])
        df = pd.concat([df, rows], ignore_index=True)
    return df


def value_maps(results, swe_var):
    """Rebuild 2D maps of values from analysis results (for display)
    Returns: (maps (n, height, width) with NaN outside ROI or void, x0, y0) or None if unavailable
    """
    if 'pixel_xy' not in results:
        return None
    x, y = (np.asarray(a) for a in results['pixel_xy'])
    x0, y0 = int(x.min()), int(y.min())
    values = np.asarray(results['raw'][swe_var], dtype=float)
    maps = np.full((values.shape[0], int(y.max()) - y0 + 1, int(x.max()) - x0 + 1), np.nan)
    maps[:, y - y0, x - x0] = values
    return maps, x0, y0
