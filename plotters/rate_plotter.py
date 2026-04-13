import matplotlib.pyplot as plt
import numpy as np
from matplotlib.ticker import MaxNLocator  # ensures integer ticks on x-axis
from matplotlib.font_manager import FontProperties  # for computing +1 pt font sizes

def plot_rate_performance(
    all_groups,
    theoretical_capacity,
    cycle_start,
    cycle_end,
    grid: bool = True,
    color_scheme: str = "nipy_spectral",
    custom_colors=None,
    legend_loc: str = "upper right",
    legend_xy: tuple | None = None,
    legend_draggable: bool = False,
    c_rate_label_mode: str = "overall",  # "none" | "overall" (default) | "on_top"
    xlim: tuple | None = None,
    ylim: tuple | None = None,
):
    fig, ax = plt.subplots(figsize=(4, 3))
    cmap = plt.cm.get_cmap(color_scheme) if color_scheme != "default" else None
    colors = []
    for i in range(len(all_groups)):
        key = all_groups[i]["label"]
        if custom_colors and key in custom_colors:
            colors.append(custom_colors[key])
        elif cmap:
            colors.append(cmap(i / max(1, len(all_groups)-1)))
        else:
            colors.append(None)

    # Collect annotations to render after all lines are plotted (needed for 'on_top' mode)
    collected_annotations = []  # list of dicts: {x, y, text, color}
    # Track data y-range to allow automatic headroom for annotations/legend
    data_y_min, data_y_max = None, None

    for idx, group in enumerate(all_groups):
        group_label = group["label"]
        data_dict = group["data"]
        mass_dict = group["masses"]
        color = colors[idx]

        x_vals = []
        y_vals = []
        annotations = []

        cycle_offset = 0

        for label, df in data_dict.items():
            df = df.copy()
            df = df[(df["cycle_number"] >= cycle_start) & (df["cycle_number"] <= cycle_end)]
            df = df[df["half_cycle"] == 1]  # only discharge

            if df.empty:
                continue

            mass_g = float(mass_dict.get(label, 1.0)) / 1000  # mg to g

            try:
                current = abs(df["current_mA"].iloc[0])
            except:
                current = 1.0

            c_rate = current / (theoretical_capacity * mass_g)

            grouped = df.groupby("cycle_number")
            group_x = []
            group_y = []

            for cyc, g in grouped:
                cap_mAh = abs(g["capacity_mAh"].iloc[-1])
                spec_cap = cap_mAh / mass_g
                group_x.append(cycle_offset + cyc)
                group_y.append(spec_cap)

            if group_x:
                mid_x = np.mean(group_x)
                mid_y = np.max(group_y)
                # Show C-rate with a single decimal place consistently (e.g., 1.0C)
                annotations.append((mid_x, mid_y + 10, f"{c_rate:.1f}C"))

            x_vals.extend(group_x)
            y_vals.extend(group_y)

            if group_x:
                cycle_offset = x_vals[-1]

        ax.plot(x_vals, y_vals, 'o-', label=group_label, color=color)
        # Defer annotation drawing until after plotting (to support 'on_top' mode)
        for x, y, label in annotations:
            collected_annotations.append({"x": x, "y": y, "text": label, "color": color})

        # Update global data y-limits
        if y_vals:
            gmin, gmax = float(np.min(y_vals)), float(np.max(y_vals))
            data_y_min = gmin if data_y_min is None else min(data_y_min, gmin)
            data_y_max = gmax if data_y_max is None else max(data_y_max, gmax)

    # Axis labels
    ax.set_xlabel("Cycle Number")
    ax.set_ylabel("Specific Capacity (mAh g$^{-1}$)")
    ax.set_title("Rate Performance")
    ax.grid(grid)
    # Force integer tick labels on the x-axis (cycle numbers are discrete integers)
    ax.xaxis.set_major_locator(MaxNLocator(integer=True))
    # Apply user-defined X range if provided
    if xlim is not None and len(xlim) == 2:
        try:
            ax.set_xlim(float(xlim[0]), float(xlim[1]))
        except Exception:
            pass

    # Determine headroom to avoid legend/labels overlapping data
    mode = (c_rate_label_mode or "overall").lower().replace(" ", "_")
    if mode not in {"none", "overall", "on_top"}:
        mode = "overall"

    # Base margins or manual Y range
    if ylim is not None and len(ylim) == 2:
        try:
            ax.set_ylim(float(ylim[0]), float(ylim[1]))
        except Exception:
            pass
    else:
        if data_y_min is not None and data_y_max is not None:
            base_range = max(1.0, data_y_max - data_y_min)
            top_headroom = 0.0
            bottom_headroom = 0.0
            # If annotations are shown near data, leave extra space above
            if mode == "overall" and collected_annotations:
                top_headroom = max(top_headroom, 0.18 * base_range)
            # Legend position influence (top/bottom)
            legend_is_upper = False
            legend_is_lower = False
            if legend_xy is None:
                if isinstance(legend_loc, str):
                    if legend_loc.startswith("upper"):
                        legend_is_upper = True
                    elif legend_loc.startswith("lower"):
                        legend_is_lower = True
            else:
                try:
                    # y in axes fraction coordinates
                    ly = float(legend_xy[1])
                    legend_is_upper = ly >= 0.6
                    legend_is_lower = ly <= 0.4
                except Exception:
                    legend_is_upper = False
                    legend_is_lower = False
            if legend_is_upper:
                top_headroom = max(top_headroom, 0.18 * base_range)
            if legend_is_lower:
                bottom_headroom = max(bottom_headroom, 0.12 * base_range)

            # Ensure minimal small margins even if no annotations/legend headroom applies
            if top_headroom <= 0.0:
                top_headroom = 0.05 * base_range
            if bottom_headroom <= 0.0:
                bottom_headroom = 0.05 * base_range

            ymin = data_y_min - bottom_headroom
            ymax = data_y_max + top_headroom
            ax.set_ylim(ymin, ymax)

    # Draw C-rate annotations based on selected mode, after y-limits are finalized
    if mode != "none":
        if mode == "overall":
            # Place near the plotted points (existing behavior)
            for item in collected_annotations:
                ax.text(item["x"], item["y"], item["text"], ha="center", fontsize=9, color=item["color"])
        elif mode == "on_top":
            # Place in a line just below the top axis limit
            y0, y1 = ax.get_ylim()
            ypad = 0.03 * (y1 - y0) if y1 > y0 else 1.0
            y_top_line = y1 - ypad
            for item in collected_annotations:
                ax.text(item["x"], y_top_line, item["text"], ha="center", va="top", fontsize=9, color=item["color"])

    # Increase axis label and tick label fontsize by +1 pt (keep C-rate font size as-is)
    try:
        label_size_base = FontProperties(size=plt.rcParams.get('axes.labelsize', plt.rcParams.get('font.size', 10.0))).get_size_in_points()
        tick_size_base = FontProperties(size=plt.rcParams.get('xtick.labelsize', plt.rcParams.get('font.size', 10.0))).get_size_in_points()
        ax.set_xlabel(ax.get_xlabel(), fontsize=label_size_base + 1)
        ax.set_ylabel(ax.get_ylabel(), fontsize=label_size_base + 1)
        ax.tick_params(axis='both', labelsize=tick_size_base + 1)
    except Exception:
        # Fallback: apply a conservative +1 without querying existing sizes
        ax.tick_params(axis='both', labelsize=11)
    if legend_xy is not None:
        leg = ax.legend(frameon=False, loc="center", bbox_to_anchor=legend_xy, bbox_transform=ax.transAxes)
    else:
        leg = ax.legend(frameon=False, loc=legend_loc)
        # If labels are on top and legend is in an upper corner, place the legend just above the axes to avoid overlap
        if mode == "on_top" and isinstance(legend_loc, str) and legend_loc.startswith("upper"):
            try:
                leg.remove()
            except Exception:
                pass
            leg = ax.legend(frameon=False, loc="lower center", bbox_to_anchor=(0.5, 1.02), bbox_transform=ax.transAxes)
    if legend_draggable and leg is not None:
        try:
            leg.set_draggable(True)
        except Exception:
            pass
    return fig, ax
