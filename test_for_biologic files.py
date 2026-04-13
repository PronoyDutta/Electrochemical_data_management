from galvani import BioLogic as BL
import os

mpr_file_path = r'C:\Users\b1104371\OneDrive - Universität Salzburg\Research\Electrolyte variation\Charecterizations\SAXS\Christian_cells\cell2\data_reduced_with_mask\cell2_20250206_SKJB_0pt94_1MLiTFSI_DiGlyme_100uL_1G1PS_diamond_window_with-tape_C02.mpr'
os.chdir(mpr_file_path)
mpr = BL.MPRfile(mpr_file_path)
print(mpr)