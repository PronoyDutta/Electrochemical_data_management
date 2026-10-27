import os
import re
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import matplotlib.cm as cm
from matplotlib.ticker import MaxNLocator, AutoMinorLocator
from matplotlib.font_manager import FontProperties
from matplotlib.lines import Line2D

# Default publication figure style constants
STABILITY_FIGSIZE = (4.5, 3.2)
STABILITY_AXIS_LABEL_FONTSIZE = 13
STABILITY_TICK_LABEL_FONTSIZE = 11
STABILITY_LEGEND_FONTSIZE = 10


def file_sort_key(s: str):
    """
    Sort file paths and names in chronological order.
    Correctly recognizes Neware split file numbering where the base file
    (e.g. `..._block1_0mA.csv`) represents chunk 0, followed by `..._1_block1_0mA.csv` (chunk 1),
    `..._2_block1_0mA.csv` (chunk 2), etc.
    """
    s_str = str(s)
    m = re.search(r"_(?:(\d+)_)?block(\d+)", s_str)
    if m:
        chunk = int(m.group(1)) if m.group(1) is not None else 0
        block = int(m.group(2))
        prefix = s_str[:m.start()]
        p_parts = [int(text) if text.isdigit() else text.lower() for text in re.split(r"(\d+)", prefix)]
        return (p_parts, block, chunk)
    return ([int(text) if text.isdigit() else text.lower() for text in re.split(r"(\d+)", s_str)], 0, 0)


def combine_and_segment_cycles(file_dict: dict, mass_g: float = 1.0, ce_mode: str = "dis_over_chg") -> pd.DataFrame:
    """
    Combines multiple sequential dataframes (e.g. Neware split blocks or BioLogic files)
    into a continuous time series and extracts cycle metrics:
    - Cycle Number
    - Discharge Capacity (mAh) & Specific Discharge Capacity (mAh/g)
    - Charge Capacity (mAh) & Specific Charge Capacity (mAh/g)
    - Coulombic Efficiency (%)

    Handles mid-cycle Neware split boundaries seamlessly without capacity artifacts.
    """
    if not file_dict:
        return pd.DataFrame(columns=["cycle", "discharge_mAh", "charge_mAh", "spec_discharge", "spec_charge", "ce"])

    sorted_keys = sorted(file_dict.keys(), key=file_sort_key)
    dfs = []
    for idx, k in enumerate(sorted_keys):
        df_k = file_dict[k].copy()
        # Ensure numeric types
        for col in ["current_mA", "capacity_mAh", "voltage_V", "time_s"]:
            if col in df_k.columns:
                df_k[col] = pd.to_numeric(df_k[col], errors="coerce").fillna(0.0)
        df_k["_file_idx"] = idx
        dfs.append(df_k)

    full_df = pd.concat(dfs, ignore_index=True)

    if "current_mA" not in full_df.columns or "capacity_mAh" not in full_df.columns:
        raise ValueError("Dataframe must contain 'current_mA' and 'capacity_mAh' columns.")

    current_ma = full_df["current_mA"].to_numpy()
    current_sign = np.where(np.abs(current_ma) < 1e-4, 0, np.where(current_ma > 0, 1, -1))

    n = len(current_sign)
    cycle_nums = np.zeros(n, dtype=np.int32)
    half_cycles = np.zeros(n, dtype=np.int8)

    cycle = 0
    half = 0
    prev_nonzero = 0

    # Sequential state machine across concatenated data points
    for i in range(n):
        s = current_sign[i]
        if s == 0:
            half_cycles[i] = half
            cycle_nums[i] = cycle
            continue

        if prev_nonzero == 0:
            cycle = 1
            half = 1
        elif prev_nonzero != s:
            if half == 1:
                half = 2
            else:
                half = 1
                cycle += 1

        half_cycles[i] = half
        cycle_nums[i] = cycle
        prev_nonzero = s

    full_df["cycle_number"] = cycle_nums
    full_df["half_cycle"] = half_cycles

    # Calculate capacities per cycle
    records = []
    mass_norm = max(float(mass_g), 1e-9)

    for cyc, grp in full_df[full_df["cycle_number"] > 0].groupby("cycle_number"):
        # Discharge step has current < 0; Charge step has current > 0
        dis_sub = grp[grp["current_mA"] < -1e-4]
        chg_sub = grp[grp["current_mA"] > 1e-4]

        def _calc_step_cap(sub):
            if len(sub) == 0:
                return 0.0
            tot = 0.0
            for _, chunk in sub.groupby("_file_idx"):
                c = chunk["capacity_mAh"].to_numpy()
                # BioLogic carry-over check
                if len(c) >= 2 and np.abs(c[1]) < 0.25 * np.abs(c[0]) and np.abs(c[0] - c[1]) > 1e-4:
                    c = c[1:]
                if len(c) > 0:
                    tot += abs(float(c[-1]) - float(c[0]))
            return tot

        q_dis = _calc_step_cap(dis_sub)
        q_chg = _calc_step_cap(chg_sub)

        # In cases where current is positive for discharge (e.g. half-cells or reverse conventions),
        # fallback to half_cycle 1 and 2 if current sign separation yielded zero
        if q_dis == 0.0 and q_chg == 0.0:
            h1_sub = grp[grp["half_cycle"] == 1]
            h2_sub = grp[grp["half_cycle"] == 2]
            q_dis = _calc_step_cap(h1_sub)
            q_chg = _calc_step_cap(h2_sub)

        spec_dis = q_dis / mass_norm
        spec_chg = q_chg / mass_norm

        if ce_mode == "chg_over_dis":
            ce = (q_chg / q_dis * 100.0) if q_dis > 1e-6 else np.nan
        else:
            # Default standard for Li-S: discharge / charge
            ce = (q_dis / q_chg * 100.0) if q_chg > 1e-6 else np.nan

        # Ignore empty/dummy cycles where no capacity was observed
        if q_dis > 0 or q_chg > 0:
            records.append({
                "cycle": int(cyc),
                "discharge_mAh": q_dis,
                "charge_mAh": q_chg,
                "spec_discharge": spec_dis,
                "spec_charge": spec_chg,
                "ce": ce
            })

    return pd.DataFrame(records)


def extract_stability_dataframe(all_groups, ce_mode: str = "dis_over_chg") -> pd.DataFrame:
    """
    Extracts an aggregated multi-sample DataFrame ready for export or clipboard.
    Columns are formatted as: {sample}_Cycle, {sample}_Specific_Discharge_Capacity_mAh_g, {sample}_CE_pct, etc.
    """
    combined_dict = {}
    for group in all_groups:
        label = group.get("label", "Sample")
        data_dict = group.get("data", {})
        mass_dict = group.get("masses", {})
        first_mass = list(mass_dict.values())[0] if mass_dict else 1.0
        mass_g = float(first_mass) / 1000.0

        res_df = combine_and_segment_cycles(data_dict, mass_g=mass_g, ce_mode=ce_mode)
        if not res_df.empty:
            prefix = re.sub(r"[^\w\-_]", "_", label)
            combined_dict[f"{prefix}_Cycle"] = pd.Series(res_df["cycle"].to_numpy())
            combined_dict[f"{prefix}_Specific_Discharge_Capacity_mAh_g"] = pd.Series(res_df["spec_discharge"].to_numpy())
            combined_dict[f"{prefix}_Specific_Charge_Capacity_mAh_g"] = pd.Series(res_df["spec_charge"].to_numpy())
            combined_dict[f"{prefix}_Coulombic_Efficiency_pct"] = pd.Series(res_df["ce"].to_numpy())

    return pd.DataFrame(combined_dict)


def plot_stability(
    all_groups: list,
    grid: bool = True,
    color_scheme: str = "default",
    custom_colors: dict | None = None,
    legend_loc: str = "lower left",
    legend_xy: tuple | None = None,
    legend_draggable: bool = False,
    show_legend: bool = True,
    xlim: tuple | None = None,
    ylim: tuple | None = None,
    ylim_ce: tuple | None = (0, 110),
    alpha: float = 1.0,
    capacity_type: str = "discharge",  # "discharge" | "charge" | "both"
    ce_mode: str = "dis_over_chg",     # "dis_over_chg" | "chg_over_dis"
    cycle_range: tuple | None = None,   # (start, end)
    show_ce: bool = True,
    ce_legend_mode: str = "single",     # "single" | "per_sample" | "none"
    markersize: float = 5.0,
    linewidth: float = 1.5,
    ce_markersize: float = 5.0,
    ce_linewidth: float = 1.0,
    figsize: tuple = STABILITY_FIGSIZE,
):
    """
    Plots electrochemical stability (cycling performance):
    - Primary Y-axis (left): Specific Capacity (mAh g^-1)
    - Secondary Y-axis (right): Coulombic Efficiency (%)
    - X-axis: Cycle Number

    Supports multiple files per sample, combining Neware split files seamlessly.
    """
    fig, ax1 = plt.subplots(figsize=figsize)
    ax2 = ax1.twinx() if show_ce else None

    # Colors assignment
    cmap = cm.get_cmap(color_scheme, max(len(all_groups), 1)) if color_scheme != "default" else None
    default_cycle_colors = None
    if color_scheme == "default":
        try:
            prop_cycle = plt.rcParams.get("axes.prop_cycle", None)
            if prop_cycle is not None:
                default_cycle_colors = prop_cycle.by_key().get("color", None)
        except Exception:
            pass

    colors = []
    for i, grp in enumerate(all_groups):
        key = grp.get("label", f"Group_{i+1}")
        if grp.get("color"):
            colors.append(grp.get("color"))
        elif custom_colors and key in custom_colors:
            colors.append(custom_colors[key])
        elif cmap is not None:
            colors.append(cmap(i))
        elif default_cycle_colors:
            colors.append(default_cycle_colors[i % len(default_cycle_colors)])
        else:
            colors.append(None)

    # Track plotted data limits
    all_x = []
    all_y_cap = []
    legend_handles = []
    ce_handles = []

    for idx, group in enumerate(all_groups):
        label = group.get("label", f"Sample {idx+1}")
        data_dict = group.get("data", {})
        mass_dict = group.get("masses", {})
        first_mass = list(mass_dict.values())[0] if mass_dict else 1.0
        mass_g = float(first_mass) / 1000.0
        color = colors[idx]

        metrics_df = combine_and_segment_cycles(data_dict, mass_g=mass_g, ce_mode=ce_mode)
        if metrics_df.empty:
            continue

        # Filter cycle range if specified
        if cycle_range is not None and len(cycle_range) == 2:
            c_start, c_end = cycle_range
            if c_start is not None:
                metrics_df = metrics_df[metrics_df["cycle"] >= int(c_start)]
            if c_end is not None:
                metrics_df = metrics_df[metrics_df["cycle"] <= int(c_end)]

        if metrics_df.empty:
            continue

        cyc_x = metrics_df["cycle"].to_numpy()
        all_x.extend(cyc_x)

        # Plot capacity curve(s) on primary axis (ax1)
        cap_mode = str(capacity_type).lower()
        if cap_mode == "both":
            dis_y = metrics_df["spec_discharge"].to_numpy()
            chg_y = metrics_df["spec_charge"].to_numpy()
            all_y_cap.extend(dis_y)
            all_y_cap.extend(chg_y)
            l_dis, = ax1.plot(
                cyc_x, dis_y, "o-", color=color, label=f"{label} (Discharge)",
                markersize=markersize, linewidth=linewidth, alpha=alpha
            )
            l_chg, = ax1.plot(
                cyc_x, chg_y, "s--", color=color, label=f"{label} (Charge)",
                markersize=markersize, linewidth=linewidth, alpha=alpha * 0.8
            )
            legend_handles.extend([l_dis, l_chg])
        elif cap_mode == "charge":
            chg_y = metrics_df["spec_charge"].to_numpy()
            all_y_cap.extend(chg_y)
            l_chg, = ax1.plot(
                cyc_x, chg_y, "s-", color=color, label=label,
                markersize=markersize, linewidth=linewidth, alpha=alpha
            )
            legend_handles.append(l_chg)
        else:
            # Default: discharge capacity
            dis_y = metrics_df["spec_discharge"].to_numpy()
            all_y_cap.extend(dis_y)
            l_dis, = ax1.plot(
                cyc_x, dis_y, "o-", color=color, label=label,
                markersize=markersize, linewidth=linewidth, alpha=alpha
            )
            legend_handles.append(l_dis)

        # Plot Coulombic Efficiency on secondary axis (ax2)
        if ax2 is not None:
            ce_y = metrics_df["ce"].to_numpy()
            l_ce, = ax2.plot(
                cyc_x, ce_y, "x--", color=color, label=f"{label} CE",
                markersize=ce_markersize, linewidth=ce_linewidth, alpha=alpha
            )
            ce_handles.append(l_ce)

    # Axis Labels & Titles
    ax1.set_xlabel("Cycle Number", fontsize=STABILITY_AXIS_LABEL_FONTSIZE)
    ax1.set_ylabel(r"Specific Capacity (mAh g$^{-1}$)", fontsize=STABILITY_AXIS_LABEL_FONTSIZE)
    if ax2 is not None:
        ax2.set_ylabel(r"Coulombic Efficiency (%)", fontsize=STABILITY_AXIS_LABEL_FONTSIZE)

    # Grid (applied to primary axis only to avoid conflict)
    ax1.grid(grid, linestyle="--", alpha=0.5)

    # Integer locators for cycle count
    ax1.xaxis.set_major_locator(MaxNLocator(integer=True))
    ax1.xaxis.set_minor_locator(AutoMinorLocator(2))
    ax1.yaxis.set_minor_locator(AutoMinorLocator(2))
    if ax2 is not None:
        ax2.yaxis.set_minor_locator(AutoMinorLocator(2))

    # Apply axis ranges
    if xlim is not None and len(xlim) == 2:
        try:
            ax1.set_xlim(float(xlim[0]), float(xlim[1]))
        except Exception:
            pass
    elif all_x:
        # Default start from 0 to max + 2
        ax1.set_xlim(0, max(all_x) + 2)

    if ylim is not None and len(ylim) == 2:
        try:
            ax1.set_ylim(float(ylim[0]), float(ylim[1]))
        except Exception:
            pass
    elif all_y_cap:
        # Default start from 0 up to 10% above max
        ymax = max(all_y_cap)
        ax1.set_ylim(0, ymax * 1.15 if ymax > 0 else 1000)

    if ax2 is not None:
        if ylim_ce is not None and len(ylim_ce) == 2:
            try:
                ax2.set_ylim(float(ylim_ce[0]), float(ylim_ce[1]))
            except Exception:
                ax2.set_ylim(0, 110)
        else:
            ax2.set_ylim(0, 110)

    # Font sizes +1 pt per repo standard
    try:
        label_size_base = FontProperties(
            size=plt.rcParams.get("axes.labelsize", plt.rcParams.get("font.size", 12.0))
        ).get_size_in_points()
        tick_size_base = FontProperties(
            size=plt.rcParams.get("xtick.labelsize", plt.rcParams.get("font.size", 11.0))
        ).get_size_in_points()
        ax1.set_xlabel(ax1.get_xlabel(), fontsize=label_size_base + 1)
        ax1.set_ylabel(ax1.get_ylabel(), fontsize=label_size_base + 1)
        ax1.tick_params(axis="both", labelsize=tick_size_base + 1)
        if ax2 is not None:
            ax2.set_ylabel(ax2.get_ylabel(), fontsize=label_size_base + 1)
            ax2.tick_params(axis="both", labelsize=tick_size_base + 1)
    except Exception:
        ax1.tick_params(axis="both", labelsize=STABILITY_TICK_LABEL_FONTSIZE)
        if ax2 is not None:
            ax2.tick_params(axis="both", labelsize=STABILITY_TICK_LABEL_FONTSIZE)

    # Legend Construction
    leg = None
    if show_legend and legend_handles:
        final_handles = list(legend_handles)
        final_labels = [h.get_label() for h in final_handles]

        if ax2 is not None and ce_handles:
            mode = (ce_legend_mode or "single").lower()
            if mode == "single":
                # Add one representative dashed-x entry for Coulombic Efficiency (matching reference figure)
                ce_color = colors[0] if colors and colors[0] else "C0"
                rep_handle = Line2D(
                    [0], [0], color=ce_color, marker="x", linestyle="--",
                    markersize=ce_markersize, linewidth=ce_linewidth, label="Coulombic Efficiency"
                )
                final_handles.append(rep_handle)
                final_labels.append("Coulombic Efficiency")
            elif mode == "per_sample":
                final_handles.extend(ce_handles)
                final_labels.extend([h.get_label() for h in ce_handles])

        if legend_xy is not None:
            leg = ax1.legend(
                final_handles, final_labels, frameon=False,
                loc="center", bbox_to_anchor=legend_xy, bbox_transform=ax1.transAxes,
                fontsize=STABILITY_LEGEND_FONTSIZE
            )
        else:
            leg = ax1.legend(
                final_handles, final_labels, frameon=False,
                loc=legend_loc, fontsize=STABILITY_LEGEND_FONTSIZE
            )

        if legend_draggable and leg is not None:
            try:
                leg.set_draggable(True)
            except Exception:
                pass

    # Attach ax2 to ax1 for easy access
    ax1.ax2 = ax2
    return fig, ax1
