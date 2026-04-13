import pandas as pd
import os
import warnings

def load_neware_files(file_path: str, output_dir: str) -> dict:
    """
    Processes Neware Excel file into BioLogic-style CSV files per constant |current| block,
    with cycle and half-cycle labeling.

    Returns:
        dict with metadata for each saved block.
    """
    os.makedirs(output_dir, exist_ok=True)
    results = {}

    warnings.filterwarnings("ignore", category=UserWarning, module="openpyxl")

    # Read Excel fully first
    df = pd.read_excel(file_path, sheet_name="record", engine="openpyxl")

    # Sanitize column headers
    df.columns = df.columns.str.strip()

    # Validate required columns
    required_cols = ["Step Type", "Total Time", "Current(A)", "Voltage(V)", "Capacity(Ah)"]
    for col in required_cols:
        if col not in df.columns:
            raise ValueError(f"Required column '{col}' is missing in file.")

    # Keep only necessary columns
    df = df[required_cols].copy()

    # Convert time to seconds
    def hms_to_seconds(t):
        try:
            h, m, s = map(int, str(t).split(":"))
            return h * 3600 + m * 60 + s
        except:
            return None

    df["time_s"] = df["Total Time"].apply(hms_to_seconds)
    df["current_mA"] = df["Current(A)"] * 1000
    # Tolerance-based binning of current
    tol = 0.1  # mA
    df["abs_current"] = df["current_mA"].abs()
    df["abs_current_binned"] = (df["abs_current"] / tol).round() * tol

    df["voltage_V"] = df["Voltage(V)"]
    df["capacity_mAh"] = df["Capacity(Ah)"] * 1000
    df["is_rest"] = df["Step Type"].str.lower().str.contains("rest")

    # Assign block_id where abs_current changes (excluding rest)
    block_id = 0
    df["block_id"] = 0
    prev_val = None

    for i in range(len(df)):
        if df.at[i, "is_rest"]:
            df.at[i, "block_id"] = block_id
            continue

        curr_val = df.at[i, "abs_current_binned"]
        if prev_val is None:
            prev_val = curr_val
        elif curr_val != prev_val:
            block_id += 1
            prev_val = curr_val
        df.at[i, "block_id"] = block_id

    # Process each block
    base = os.path.splitext(os.path.basename(file_path))[0]

    for blk, block in df.groupby("block_id"):
        block = block.reset_index(drop=True)

        # Skip empty or all-rest blocks
        if block["is_rest"].all():
            continue

        # Normalize time
        block["time_s"] -= block["time_s"].iloc[0]

        # State-machine for cycle/half-cycle
        hc = []
        cn = []
        state = 0
        cycle = 0
        prev_sign = 0

        for i, row in block.iterrows():
            if row["is_rest"]:
                hc.append(0)
                cn.append(0)
                continue

            current_sign = 1 if row["current_mA"] > 0 else -1
            if prev_sign == 0:
                state = 1
                hc.append(1)
                cycle += 1
            elif state == 1 and current_sign != prev_sign:
                state = 2
                hc.append(2)
            elif state == 2 and current_sign != prev_sign:
                state = 1
                hc.append(1)
                cycle += 1
            else:
                hc.append(state)
            cn.append(cycle)
            prev_sign = current_sign

        block["half_cycle"] = hc
        block["cycle_number"] = cn

        final = block[["cycle_number", "half_cycle", "time_s", "current_mA", "voltage_V", "capacity_mAh"]]
        current_val = int(round(block.loc[~block["is_rest"], "abs_current"].iloc[0]))

        out_name = f"{base}_block{blk+1}_{current_val}mA.csv"
        out_path = os.path.join(output_dir, out_name)
        final.to_csv(out_path, index=False)

        results[out_name] = {
            "cycles": final["cycle_number"].nunique(),
            "points": len(final),
            "current_mA": current_val
        }

    return results
