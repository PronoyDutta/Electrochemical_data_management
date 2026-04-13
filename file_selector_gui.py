import os
import json
import csv
import pickle
import pandas as pd
import numpy as np
import tkinter as tk
from tkinter import filedialog, ttk, messagebox
from datetime import datetime
from loaders.biologic_loader import load_biologic_gcd_mpr
from loaders.neware_loader import load_neware_files

SETTINGS_FILE = "gui_settings.pkl"

class SampleAdderApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Add Electrochemical Sample")
        self.file_paths = []
        self.loaded_data = {}
        self.source_var = tk.StringVar(value="BioLogic")
        self.project_folder = self.load_last_project_folder()

        self.setup_source_selector()
        self.setup_file_selector()
        self.setup_metadata_fields()
        self.setup_project_folder_selector()
        self.setup_save_button()
        self.view_button = ttk.Button(self.root, text="View Saved Samples", command=self.view_saved_samples)
        self.view_button.pack(pady=5)
        # Export aggregated metadata across all samples/tests
        self.export_button = ttk.Button(self.root, text="Export All Metadata to Excel", command=self.export_all_metadata_to_excel)
        self.export_button.pack(pady=5)

    def setup_source_selector(self):
        frame = ttk.LabelFrame(self.root, text="Instrument Type")
        frame.pack(fill="x", padx=10, pady=5)
        ttk.Radiobutton(frame, text="BioLogic", variable=self.source_var, value="BioLogic").pack(side="left", padx=10)
        ttk.Radiobutton(frame, text="Neware", variable=self.source_var, value="Neware").pack(side="left", padx=10)

    def setup_file_selector(self):
        self.file_frame = ttk.LabelFrame(self.root, text="Select Raw Data Files")
        self.file_frame.pack(fill="x", padx=10, pady=5)
        ttk.Button(self.file_frame, text="Browse Files", command=self.select_files).grid(row=0, column=0, padx=5, pady=5, sticky="w")

        text_frame = ttk.Frame(self.file_frame)
        text_frame.grid(row=0, column=1, padx=5, pady=5, sticky="nsew")

        self.file_display = tk.Text(text_frame, height=5, width=60, wrap="none", state="disabled")
        self.file_display.pack(side="left", fill="both", expand=True)

        scrollbar = ttk.Scrollbar(text_frame, orient="vertical", command=self.file_display.yview)
        scrollbar.pack(side="right", fill="y")
        self.file_display.configure(yscrollcommand=scrollbar.set)
        self.file_frame.columnconfigure(1, weight=1)

    def setup_metadata_fields(self):
        frame = ttk.LabelFrame(self.root, text="Sample Metadata")
        frame.pack(fill="both", padx=10, pady=10)
        self.entries = {}

        def add_entry(label, key):
            ttk.Label(frame, text=label).grid(row=len(self.entries), column=0, sticky="w", padx=5, pady=2)
            entry = ttk.Entry(frame, width=40)
            entry.grid(row=len(self.entries), column=1, padx=5, pady=2)
            self.entries[key] = entry

        add_entry("Sample ID", "sample_id")
        add_entry("Mass (mg)", "mass_mg")
        add_entry("Sample area (sq.cm)", "area_cm2")
        add_entry("Sample thickness (um)", "thickness_um")
        add_entry("Electrolyte", "electrolyte")
        add_entry("Electrode", "electrode")

        ttk.Label(frame, text="Test Type").grid(row=len(self.entries), column=0, sticky="w", padx=5, pady=2)
        self.test_type_var = tk.StringVar(value="GCD")
        test_type_menu = ttk.Combobox(frame, textvariable=self.test_type_var, values=["GCD", "CV", "EIS", "GITT", "Rate", "OCP", "Pulsed technique"], state="readonly")
        test_type_menu.grid(row=len(self.entries), column=1, padx=5, pady=2)
        self.entries["test_type"] = self.test_type_var

        # Instead of a boolean include option, allow entering the Rate denominator N (for C/N)
        self.rate_N_label = ttk.Label(frame, text="Rate (N from C/N)")
        self.rate_N_label.grid(row=len(self.entries)+1, column=0, sticky="w", padx=5, pady=2)
        self.rate_N_var = tk.StringVar(value="")
        self.rate_N_entry = ttk.Entry(frame, textvariable=self.rate_N_var, width=12)
        self.rate_N_entry.grid(row=len(self.entries)+1, column=1, padx=5, pady=2, sticky="w")

        # Show the Rate(N) field only for GCD selection
        def _toggle_rate_field(*_):
            if self.test_type_var.get() == "GCD":
                # show
                self.rate_N_label.grid()
                self.rate_N_entry.grid()
            else:
                # hide and clear
                self.rate_N_var.set("")
                self.rate_N_label.grid_remove()
                self.rate_N_entry.grid_remove()
        _toggle_rate_field()
        test_type_menu.bind("<<ComboboxSelected>>", _toggle_rate_field)

        ttk.Label(frame, text="Notes").grid(row=len(self.entries)+2, column=0, sticky="nw", padx=5, pady=2)
        self.notes_text = tk.Text(frame, width=40, height=4)
        self.notes_text.grid(row=len(self.entries)+2, column=1, padx=5, pady=2)
        self.entries["notes"] = self.notes_text

        self.entries["date"] = datetime.today().strftime("%Y-%m-%d")

    def setup_project_folder_selector(self):
        frame = ttk.LabelFrame(self.root, text="Project Folder")
        frame.pack(fill="x", padx=10, pady=5)

        self.folder_label = ttk.Label(frame, text=self.project_folder or "No folder selected", width=80)
        self.folder_label.pack(side="left", padx=5)

        ttk.Button(frame, text="Select Folder", command=self.change_project_folder).pack(side="right", padx=5)

    def setup_save_button(self):
        self.save_button = ttk.Button(self.root, text="Save Processed Data", command=self.save_processed_data)
        self.save_button.pack(pady=10)

    def change_project_folder(self):
        folder = filedialog.askdirectory(title="Select Project Folder")
        if folder:
            self.project_folder = folder
            self.folder_label.config(text=folder)
            self.save_last_project_folder(folder)

    def load_last_project_folder(self):
        if os.path.exists(SETTINGS_FILE):
            try:
                with open(SETTINGS_FILE, "rb") as f:
                    return pickle.load(f).get("last_project_folder", "")
            except Exception:
                return ""
        return ""

    def save_last_project_folder(self, path):
        with open(SETTINGS_FILE, "wb") as f:
            pickle.dump({"last_project_folder": path}, f)

    def select_files(self):
        source = self.source_var.get()
        filetypes = [("BioLogic MPR files", "*.mpr")] if source == "BioLogic" else [("Neware Excel files", "*.xlsx")]
        files = filedialog.askopenfilenames(title=f"Select {source} files", filetypes=filetypes)
        self.file_paths = list(files)

        self.file_display.config(state="normal")
        self.file_display.delete("1.0", tk.END)
        self.file_display.insert(tk.END, "\n".join(self.file_paths) if self.file_paths else "No files selected")
        self.file_display.config(state="disabled")

        self.loaded_data = {}

        if source == "BioLogic" and self.test_type_var.get() == "GCD":
            self.loaded_data = load_biologic_gcd_mpr(self.file_paths)
            summary = ""
            for fname, result in self.loaded_data.items():
                if result["error"]:
                    summary += f"[ERROR] {fname}: {result['error']}\n"
                else:
                    meta = result["meta"]
                    summary += f"{fname}:\n  Half-cycles: {meta['num_half_cycles']}\n  Voltage Range: {meta['min_voltage']} V → {meta['max_voltage']} V\n\n"
            if summary:
                messagebox.showinfo("Loaded File Summary", summary)
        elif source == "Neware":
            messagebox.showinfo("Ready", f"{len(self.file_paths)} Neware file(s) selected. Click 'Save' to process.")

    def get_metadata(self):
        # Parse Rate N if provided (only for GCD). Store as float if valid, else None.
        rate_N_val = None
        try:
            if self.entries["test_type"].get().strip() == "GCD":
                v = (self.rate_N_var.get() or "").strip()
                if v != "":
                    rate_N_val = float(v)
        except Exception:
            rate_N_val = None

        return {
            "source": self.source_var.get(),
            "file_paths": self.file_paths,
            "sample_id": self.entries["sample_id"].get().strip(),
            "mass_mg": self.entries["mass_mg"].get().strip(),
            "area_cm2": self.entries["area_cm2"].get().strip(),
            "thickness_um": self.entries["thickness_um"].get().strip(),
            "electrolyte": self.entries["electrolyte"].get().strip(),
            "electrode": self.entries["electrode"].get().strip(),
            "test_type": self.entries["test_type"].get().strip(),
            "rate_c_over_n": rate_N_val,
            "notes": self.entries["notes"].get("1.0", "end-1c").strip(),
            "date": self.entries["date"]
        }

    def show_progress(self, total_tasks):
        progress_window = tk.Toplevel(self.root)
        progress_window.title("Saving Data...")
        ttk.Label(progress_window, text="Processing files...").pack(padx=10, pady=10)

        progress = ttk.Progressbar(progress_window, orient="horizontal", length=300, mode="determinate")
        progress.pack(padx=10, pady=(0, 10))
        progress["maximum"] = total_tasks
        return progress_window, progress

    def save_processed_data(self):
        if not self.file_paths:
            messagebox.showwarning("No Data", "No files selected.")
            return
        if not self.project_folder:
            messagebox.showwarning("No Folder", "Please select a project folder.")
            return

        sample_id = self.entries["sample_id"].get().strip()
        test_type = self.test_type_var.get().strip()
        metadata = self.get_metadata()

        sample_folder = os.path.join(self.project_folder, sample_id)
        test_folder = os.path.join(sample_folder, test_type)
        os.makedirs(test_folder, exist_ok=True)

        with open(os.path.join(test_folder, "metadata.pkl"), "wb") as f:
            pickle.dump(metadata, f)

        total_blocks = len(self.file_paths)
        progress_win, progress_bar = self.show_progress(total_blocks)
        self.root.update_idletasks()

        try:
            if self.source_var.get() == "BioLogic" and test_type == "GCD":
                for i, (fname, result) in enumerate(self.loaded_data.items()):
                    if result["error"] is None:
                        data = result["data"]
                        name = os.path.splitext(os.path.basename(fname))[0]
                        out_path = os.path.join(test_folder, f"{name}.csv")
                        if isinstance(data, dict):
                            columns = ["cycle_number", "half_cycle", "time_s", "current_mA", "voltage_V", "capacity_mAh"]
                            with open(out_path, "w", newline="") as f:
                                writer = csv.writer(f)
                                writer.writerow(columns)
                                for row in zip(*(data[c] for c in columns)):
                                    writer.writerow(row)
                        else:
                            data.to_csv(out_path, index=False)
                    progress_bar["value"] = i + 1
                    self.root.update_idletasks()

            elif self.source_var.get() == "Neware" and test_type in ["GCD", "Rate"]:
                summary = ""
                for i, f in enumerate(self.file_paths):
                    results = load_neware_files(f, test_folder)
                    for fname, meta in results.items():
                        df = pd.read_csv(os.path.join(test_folder, fname))
                        self.loaded_data[fname] = {"data": df, "meta": meta, "error": None}
                        summary += f"{fname}: {meta['cycles']} cycles, {meta['points']} points at {meta['current_mA']} mA\n"
                    progress_bar["value"] = i + 1
                    self.root.update_idletasks()
                if summary:
                    messagebox.showinfo("Processed Neware Data", summary)

            progress_win.destroy()
            messagebox.showinfo("Success", f"Data saved to {test_folder}")

        except Exception as e:
            progress_win.destroy()
            messagebox.showerror("Error", f"Failed to save data:\n{str(e)}")

    def export_all_metadata_to_excel(self):
        """Collect metadata from every sample/test in the selected project folder
        and write/update a single Excel workbook (project_metadata.xlsx).
        Rows are keyed by (sample_id, test_type); existing rows are updated, new rows appended.
        Fallback to CSV if openpyxl (Excel writer) is unavailable.
        """
        project = self.project_folder
        if not project or not os.path.isdir(project):
            messagebox.showwarning("No Project", "Please select a valid project folder before exporting.")
            return

        def _normalise_value(value):
            """Convert metadata values into DataFrame-friendly representations."""
            if value is None:
                return ""
            if isinstance(value, np.ndarray):
                return _normalise_value(value.tolist())
            if isinstance(value, (list, tuple, set)):
                flattened = [_normalise_value(v) for v in value]
                return json.dumps(flattened)
            if isinstance(value, dict):
                return json.dumps({str(k): _normalise_value(v) for k, v in value.items()})
            if isinstance(value, (datetime, pd.Timestamp)):
                return str(value)
            try:
                if pd.isna(value):
                    return ""
            except Exception:
                pass
            return str(value)

        # Only extract these specific columns from metadata - ignore everything else
        wanted_keys = [
            "sample_id",
            "test_type",
            "source",
            "mass_mg",
            "area_cm2",
            "thickness_um",
            "electrolyte",
            "electrode",
            "rate_c_over_n",
            "notes",
            "date",
        ]

        def safe_str(val):
            """Convert any value to string safely"""
            if val is None or val == "":
                return ""
            if isinstance(val, (list, tuple, np.ndarray)):
                return ", ".join(str(x) for x in val)
            try:
                return str(val)
            except Exception:
                return ""

        rows = []
        try:
            for sample in sorted(os.listdir(project)):
                sample_dir = os.path.join(project, sample)
                if not os.path.isdir(sample_dir):
                    continue
                for test in sorted(os.listdir(sample_dir)):
                    test_dir = os.path.join(sample_dir, test)
                    if not os.path.isdir(test_dir):
                        continue
                    meta_path = os.path.join(test_dir, "metadata.pkl")
                    if not os.path.isfile(meta_path):
                        continue
                    
                    try:
                        with open(meta_path, "rb") as f:
                            meta = pickle.load(f)
                    except Exception:
                        continue
                    
                    if not isinstance(meta, dict):
                        continue

                    # Extract only the fields we need (matching get_metadata structure)
                    row = {
                        "sample_id": safe_str(meta.get("sample_id", sample)),
                        "test_type": safe_str(meta.get("test_type", test)),
                        "source": safe_str(meta.get("source", "")),
                        "mass_mg": safe_str(meta.get("mass_mg", "")),
                        "area_cm2": safe_str(meta.get("area_cm2", "")),
                        "thickness_um": safe_str(meta.get("thickness_um", "")),
                        "electrolyte": safe_str(meta.get("electrolyte", "")),
                        "electrode": safe_str(meta.get("electrode", "")),
                        "rate_c_over_n": safe_str(meta.get("rate_c_over_n", "")),
                        "notes": safe_str(meta.get("notes", "")),
                        "date": safe_str(meta.get("date", "")),
                        "sample_folder": sample_dir,
                        "test_folder": test_dir,
                    }
                    rows.append(row)
        except Exception as e:
            messagebox.showerror("Error", f"Failed while scanning folders:\n{e}")
            return
        if not rows:
            messagebox.showinfo("No Metadata", "No metadata.pkl files found in the project folder.")
            return
        # Write directly to CSV first (avoids DataFrame creation issues)
        import csv
        csv_path = os.path.join(project, "project_metadata.csv")
        excel_path = os.path.join(project, "project_metadata.xlsx")
        
        final_columns = wanted_keys + ["sample_folder", "test_folder"]
        key_cols = ["sample_id", "test_type"]
        
        # Read existing rows if CSV exists
        existing_rows = {}
        if os.path.isfile(csv_path):
            try:
                with open(csv_path, 'r', encoding='utf-8') as f:
                    reader = csv.DictReader(f)
                    for row in reader:
                        key = (row.get("sample_id", ""), row.get("test_type", ""))
                        existing_rows[key] = row
            except Exception:
                pass
        
        # Update with new rows
        for row in rows:
            key = (row.get("sample_id", ""), row.get("test_type", ""))
            existing_rows[key] = row
        
        # Write CSV
        try:
            with open(csv_path, 'w', encoding='utf-8', newline='') as f:
                writer = csv.DictWriter(f, fieldnames=final_columns, extrasaction='ignore')
                writer.writeheader()
                writer.writerows(existing_rows.values())
        except Exception as e:
            messagebox.showerror("Export Failed", f"Could not write CSV: {e}")
            return
        
        # Try to convert to Excel
        try:
            df = pd.read_csv(csv_path, dtype=str)
            df.to_excel(excel_path, index=False)
            messagebox.showinfo("Export Complete", f"Metadata written/updated: {excel_path}")
        except Exception as e:
            messagebox.showinfo("Export Complete", f"CSV written: {csv_path}\n(Excel conversion failed: {e})")

    def view_saved_samples(self):
        project_dir = filedialog.askdirectory(title="Select Project Folder")
        if not project_dir:
            return
        samples = [d for d in os.listdir(project_dir) if os.path.isdir(os.path.join(project_dir, d))]
        if not samples:
            messagebox.showwarning("No Samples", "No sample folders found in project.")
            return
        self.show_sample_folder_selector_popup(project_dir, samples)

    def show_sample_folder_selector_popup(self, project_dir, samples):
        popup = tk.Toplevel(self.root)
        popup.title("Browse Saved Samples")

        ttk.Label(popup, text="Sample ID:").grid(row=0, column=0, sticky="w", padx=5, pady=5)
        sample_var = tk.StringVar(value=samples[0])
        sample_menu = ttk.Combobox(popup, textvariable=sample_var, values=samples, state="readonly")
        sample_menu.grid(row=0, column=1, padx=5, pady=5)

        ttk.Label(popup, text="Test Type:").grid(row=1, column=0, sticky="w", padx=5, pady=5)
        test_var = tk.StringVar()
        test_menu = ttk.Combobox(popup, textvariable=test_var, state="readonly")
        test_menu.grid(row=1, column=1, padx=5, pady=5)

        text_display = tk.Text(popup, width=80, height=20, state="disabled")
        text_display.grid(row=2, column=0, columnspan=3, padx=5, pady=5, sticky="nsew")
        v_scroll = ttk.Scrollbar(popup, orient="vertical", command=text_display.yview)
        v_scroll.grid(row=2, column=3, sticky="ns")
        text_display.config(yscrollcommand=v_scroll.set)

        def on_sample_change(event=None):
            sid = sample_var.get()
            sample_path = os.path.join(project_dir, sid)
            tests = [d for d in os.listdir(sample_path) if os.path.isdir(os.path.join(sample_path, d))]
            test_menu.config(values=tests)
            if tests:
                test_var.set(tests[0])
                display_test_data()

        def display_test_data(event=None):
            sid = sample_var.get()
            ttype = test_var.get()
            test_path = os.path.join(project_dir, sid, ttype)
            meta_file = os.path.join(test_path, "metadata.pkl")
            if os.path.exists(meta_file):
                with open(meta_file, "rb") as f:
                    metadata = pickle.load(f)
            else:
                metadata = {}
            files = [fname for fname in os.listdir(test_path) if fname != "metadata.pkl"]

            text_display.config(state="normal")
            text_display.delete("1.0", tk.END)
            text_display.insert(tk.END, f"Sample ID: {sid}\nTest Type: {ttype}\n\nMetadata:\n")
            for k, v in metadata.items():
                text_display.insert(tk.END, f"  {k}: {v}\n")
            text_display.insert(tk.END, "\nFiles:\n")
            for fname in files:
                text_display.insert(tk.END, f"  {fname}\n")
            text_display.config(state="disabled")

        sample_menu.bind("<<ComboboxSelected>>", on_sample_change)
        test_menu.bind("<<ComboboxSelected>>", display_test_data)
        on_sample_change()

if __name__ == "__main__":
    root = tk.Tk()
    app = SampleAdderApp(root)
    root.mainloop()
