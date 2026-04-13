import os
import pandas as pd
import numpy as np

# Plot style settings (edit these to quickly tune typography/size)
GCD_FIGSIZE = (4, 3)
GCD_TITLE_FONTSIZE = 13
GCD_AXIS_LABEL_FONTSIZE = 13
GCD_TICK_LABEL_FONTSIZE = 11
GCD_LEGEND_FONTSIZE = 10

def load_gcd_data(project_dir, sample_names, cycle_numbers=None):
    """
    Loads GCD data for multiple samples.
    Returns a dict of {sample_name: dataframe} and {sample_name: mass}
    """
    data = {}
    masses = {}

    for sample in sample_names:
        gcd_path = os.path.join(project_dir, sample, "GCD", "data.csv")
        meta_path = os.path.join(project_dir, sample, "GCD", "meta.json")

        if os.path.isfile(gcd_path):
            df = pd.read_csv(gcd_path)
            if cycle_numbers:
                df = df[df['cycle_number'].isin(cycle_numbers)]

            data[sample] = df

            if os.path.isfile(meta_path):
                import json
                with open(meta_path) as f:
                    meta = json.load(f)
                masses[sample] = meta.get("mass_mg", 1.0)  # fallback to 1.0 mg
            else:
                masses[sample] = 1.0  # fallback

    return data, masses

import matplotlib.pyplot as plt
import matplotlib.cm as cm

def plot_gcd_curves(
    groups,
    grid: bool = True,
    color_scheme: str = "nipy_spectral",
    custom_colors=None,
    separate_halfcycle_colors: bool = False,
    legend_loc: str = "upper right",
    legend_xy: tuple | None = None,
    legend_draggable: bool = False,
    xlim: tuple | None = None,
    ylim: tuple | None = None,
):
    # Match the rate plot figure sizing for visual consistency
    fig, ax = plt.subplots(figsize=GCD_FIGSIZE)

    # Build color keys per cycle (or per cycle+half-cycle when requested).
    color_keys = []
    for group in groups:
        for sample, df in group["data"].items():
            for cyc in df['cycle_number'].unique():
                if cyc != 0:
                    if separate_halfcycle_colors:
                        color_keys.append(f"{sample}_C{cyc}_H1_{group['label']}")
                        color_keys.append(f"{sample}_C{cyc}_H2_{group['label']}")
                    else:
                        color_keys.append(f"{sample}_C{cyc}_{group['label']}")
    color_keys = sorted(set(color_keys))
    cmap = cm.get_cmap(color_scheme, max(len(color_keys), 1)) if color_scheme != "default" else None

    color_map = {}
    # If default scheme, use Matplotlib's default color cycle explicitly
    default_cycle_colors = None
    if color_scheme == "default":
        try:
            prop_cycle = plt.rcParams.get('axes.prop_cycle', None)
            if prop_cycle is not None:
                default_cycle_colors = prop_cycle.by_key().get('color', None)
            else:
                default_cycle_colors = None
        except Exception:
            default_cycle_colors = None

    for i, key in enumerate(color_keys):
        if custom_colors is not None and key in custom_colors:
            color_map[key] = custom_colors[key]
        elif cmap is not None:
            color_map[key] = cmap(i)
        elif default_cycle_colors:
            color_map[key] = default_cycle_colors[i % len(default_cycle_colors)]
        else:
            color_map[key] = None  # fallback to matplotlib default

    # Plot all groups
    for group in groups:
        group_label = group["label"]
        for sample, df in group["data"].items():
            mass_g = float(group["masses"].get(sample, 1.0)) / 1000
            df = df.copy()
            # Only consider half_cycle 1 (discharge) and 2 (charge)
            df = df[df['half_cycle'].isin([1, 2])]
            grouped = df.groupby(['cycle_number', 'half_cycle'])

            for (cyc, half), subdf in grouped:
                if cyc == 0:
                    continue
                if separate_halfcycle_colors:
                    color_key = f"{sample}_C{cyc}_H{int(half)}_{group_label}"
                else:
                    color_key = f"{sample}_C{cyc}_{group_label}"
                color = color_map.get(color_key, None)
                label = f"{group_label}" if half == 1 else None
                if "time_s" in subdf.columns:
                    subdf = subdf.sort_values("time_s")

                q = subdf["capacity_mAh"].to_numpy(dtype=float)
                v = subdf["voltage_V"].to_numpy(dtype=float)
                if len(q) < 2:
                    continue

                # BioLogic exports can include one carry-over capacity point at half-cycle start.
                # Drop it when the second point clearly resets close to zero.
                if np.abs(q[1]) < 0.25 * np.abs(q[0]) and np.abs(q[0] - q[1]) > 1e-4:
                    q = q[1:]
                    v = v[1:]
                    if len(q) < 2:
                        continue

                # Plot capacity relative to half-cycle start to avoid artificial connectors.
                x = np.abs(q - q[0]) / mass_g

                if color is not None:
                    ax.plot(x, v, color=color, label=label)
                else:
                    ax.plot(x, v, label=label)

    ax.set_xlabel("Specific Capacity (mAh g$^{-1}$)", fontsize=GCD_AXIS_LABEL_FONTSIZE)
    ax.set_ylabel("Potential (V vs. Li/Li+)", fontsize=GCD_AXIS_LABEL_FONTSIZE)
    ax.set_title("GCD Curves", fontsize=GCD_TITLE_FONTSIZE)
    ax.tick_params(axis='both', labelsize=GCD_TICK_LABEL_FONTSIZE)
    # Apply user-defined axis ranges if provided
    try:
        if xlim is not None and len(xlim) == 2:
            ax.set_xlim(float(xlim[0]), float(xlim[1]))
        if ylim is not None and len(ylim) == 2:
            ax.set_ylim(float(ylim[0]), float(ylim[1]))
    except Exception:
        pass
    # Legend: no frame. If manual position provided, anchor to (x,y) in axes coords
    if legend_xy is not None:
        leg = ax.legend(
            frameon=False,
            loc="center",
            bbox_to_anchor=legend_xy,
            bbox_transform=ax.transAxes,
            fontsize=GCD_LEGEND_FONTSIZE,
        )
    else:
        leg = ax.legend(frameon=False, loc=legend_loc, fontsize=GCD_LEGEND_FONTSIZE)
    if legend_draggable and leg is not None:
        try:
            leg.set_draggable(True)
        except Exception:
            pass
    ax.grid(grid)
    return fig, ax


