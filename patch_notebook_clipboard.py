import json

with open("notebook.ipynb", "r") as f:
    nb = json.load(f)

for cell in nb["cells"]:
    if cell["cell_type"] == "code":
        src = "".join(cell["source"])
        if "plot_btn = widgets.Button" in src:
            # Add definition
            replacement = """plot_btn = widgets.Button(description="Plot", button_style='success')
copy_data_btn = widgets.Button(description="Copy Data to Clipboard", button_style='info')
output = widgets.Output()
last_plot_ax = None

def extract_df_from_ax(ax):
    lines = ax.get_lines()
    df_dict = {}
    import pandas as pd
    for i, line in enumerate(lines):
        lbl = line.get_label()
        if not lbl:
            lbl = f"Curve_{i+1}"
        elif lbl.startswith('_') and lbl != "_nolegend_":
            lbl = lbl.lstrip('_')
        elif lbl == "_nolegend_":
            lbl = f"Curve_{i+1}"
        col_x, col_y = f"{lbl}_X", f"{lbl}_Y"
        suffix = 1
        while col_x in df_dict:
            col_x, col_y = f"{lbl}_{suffix}_X", f"{lbl}_{suffix}_Y"
            suffix += 1
        df_dict[col_x] = pd.Series(line.get_xdata())
        df_dict[col_y] = pd.Series(line.get_ydata())
    return pd.DataFrame(df_dict)

def on_copy_data_clicked(_):
    global last_plot_ax
    with output:
        if last_plot_ax is None:
            print("⚠️ Please plot something first.")
            return
        try:
            df = extract_df_from_ax(last_plot_ax)
            df.to_clipboard(index=False)
            print("✅ Data successfully copied to clipboard! You can now paste it into LabPlot or Origin.")
        except Exception as e:
            print(f"❌ Failed to copy to clipboard: {e}")
copy_data_btn.on_click(on_copy_data_clicked)
"""
            src = src.replace("plot_btn = widgets.Button(description=\"Plot\", button_style='success')\noutput = widgets.Output()", replacement)
            
            # Add global to on_plot_clicked
            src = src.replace("def on_plot_clicked(_):\n    with output:", "def on_plot_clicked(_):\n    global last_plot_ax\n    with output:")
            
            # Save ax
            src = src.replace("display(fig)", "last_plot_ax = ax\n            display(fig)")
            
            # Display button
            src = src.replace("display(plot_btn, output)", "display(widgets.HBox([plot_btn, copy_data_btn]), output)")
            
            cell["source"] = [line + "\n" for line in src.split("\n")]
            cell["source"][-1] = cell["source"][-1][:-1]

with open("notebook.ipynb", "w") as f:
    json.dump(nb, f, indent=1)
