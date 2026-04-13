import tkinter as tk
from tkinter import filedialog, ttk
from datetime import datetime

class SampleAdderApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Add Electrochemical Sample")
        self.file_paths = []
        self.source_var = tk.StringVar(value="BioLogic")

        self.setup_source_selector()
        self.setup_file_selector()
        self.setup_metadata_fields()

    def setup_source_selector(self):
        frame = ttk.LabelFrame(self.root, text="Instrument Type")
        frame.pack(fill="x", padx=10, pady=5)

        ttk.Radiobutton(frame, text="BioLogic", variable=self.source_var, value="BioLogic").pack(side="left", padx=10)
        ttk.Radiobutton(frame, text="Neware", variable=self.source_var, value="Neware").pack(side="left", padx=10)

    def setup_file_selector(self):
        self.file_frame = ttk.LabelFrame(self.root, text="Select Raw Data Files")
        self.file_frame.pack(fill="x", padx=10, pady=5)

        btn = ttk.Button(self.file_frame, text="Browse Files", command=self.select_files)
        btn.pack(side="left", padx=10, pady=5)

        self.file_label = ttk.Label(self.file_frame, text="No files selected", wraplength=400)
        self.file_label.pack(side="left", fill="x", expand=True)

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
        add_entry("Electrolyte", "electrolyte")
        add_entry("Electrode", "electrode")

        # Test Type dropdown
        ttk.Label(frame, text="Test Type").grid(row=len(self.entries), column=0, sticky="w", padx=5, pady=2)
        self.test_type_var = tk.StringVar(value="GCD")
        test_type_options = ["GCD", "CV", "EIS", "GITT", "Rate", "OCP", "Other"]
        test_type_menu = ttk.Combobox(frame, textvariable=self.test_type_var, values=test_type_options, state="readonly")
        test_type_menu.grid(row=len(self.entries), column=1, padx=5, pady=2)
        self.entries["test_type"] = self.test_type_var

        # Notes
        ttk.Label(frame, text="Notes").grid(row=len(self.entries)+1, column=0, sticky="nw", padx=5, pady=2)
        self.notes_text = tk.Text(frame, width=40, height=4)
        self.notes_text.grid(row=len(self.entries)+1, column=1, padx=5, pady=2)
        self.entries["notes"] = self.notes_text

        # Auto-filled date
        self.entries["date"] = datetime.today().strftime("%Y-%m-%d")

    def select_files(self):
        source = self.source_var.get()
        filetypes = [("BioLogic MPR files", "*.mpr")] if source == "BioLogic" else [("Neware CSV files", "*.csv")]

        files = filedialog.askopenfilenames(title=f"Select {source} files", filetypes=filetypes)
        self.file_paths = list(files)

        if self.file_paths:
            self.file_label.config(text="\n".join(self.file_paths))
        else:
            self.file_label.config(text="No files selected")

    def get_metadata(self):
        """
        Collects all metadata from the GUI into a dictionary
        """
        metadata = {
            "source": self.source_var.get(),
            "file_paths": self.file_paths,
            "sample_id": self.entries["sample_id"].get().strip(),
            "mass_mg": self.entries["mass_mg"].get().strip(),
            "electrolyte": self.entries["electrolyte"].get().strip(),
            "electrode": self.entries["electrode"].get().strip(),
            "test_type": self.entries["test_type"].get().strip(),
            "notes": self.entries["notes"].get("1.0", "end-1c").strip(),
            "date": self.entries["date"]
        }
        return metadata

# Run GUI
if __name__ == "__main__":
    root = tk.Tk()
    app = SampleAdderApp(root)
    root.mainloop()
