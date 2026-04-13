# loaders/biologic_loader.py

import os
import numpy as np
from galvani.BioLogic import MPRfile

OUTPUT_COLUMNS = [
    "cycle_number",
    "half_cycle",
    "time_s",
    "current_mA",
    "voltage_V",
    "capacity_mAh",
]


def _pick_field(field_names, aliases):
    for name in aliases:
        if name in field_names:
            return name
    return None


def load_biologic_gcd_mpr(filepaths):
    results = {}

    for path in filepaths:
        filename = os.path.basename(path)
        result = {'data': None, 'meta': None, 'error': None}

        try:
            exp = MPRfile(path)
            data = exp.data
            field_names = set(data.dtype.names or ())

            time_col = _pick_field(field_names, ["time/s"])
            voltage_col = _pick_field(field_names, ["Ewe/V"])
            current_col = _pick_field(field_names, ["control/V/mA", "I/mA"])
            cap_col = _pick_field(field_names, ["Q charge/discharge/mA.h", "Q discharge/mA.h"])

            missing = []
            if time_col is None:
                missing.append("time/s")
            if voltage_col is None:
                missing.append("Ewe/V")
            if current_col is None:
                missing.append("control/V/mA or I/mA")
            if cap_col is None:
                missing.append("Q charge/discharge/mA.h or Q discharge/mA.h")
            if missing:
                raise ValueError(f"Missing required BioLogic columns: {', '.join(missing)}")

            time_s = np.asarray(data[time_col], dtype=float)
            voltage_v = np.asarray(data[voltage_col], dtype=float)
            current_ma = np.asarray(data[current_col], dtype=float)
            capacity_mah = np.asarray(data[cap_col], dtype=float)

            # Assign current sign (charge/discharge/rest).
            current_sign = np.where(np.abs(current_ma) < 1e-5, 0, np.where(current_ma > 0, 1, -1))

            # Track cycles from sign changes, while keeping numbering through rest periods.
            cycle = 0
            half = 0
            half_abs = 0
            prev_nonzero_sign = 0
            cycle_nums = []
            half_cycles = []

            for sign in current_sign:
                if sign == 0:
                    # Keep last known half/cycle during rest.
                    half_cycles.append(half)
                    cycle_nums.append(cycle)
                    continue

                if prev_nonzero_sign == 0:
                    cycle = 1
                    half = 1
                    half_abs = 1
                elif prev_nonzero_sign * sign < 0:
                    half_abs += 1
                    if half == 1:
                        half = 2
                    else:
                        half = 1
                        cycle += 1

                half_cycles.append(half)
                cycle_nums.append(cycle)
                prev_nonzero_sign = sign

            data_dict = {
                "cycle_number": np.asarray(cycle_nums, dtype=int),
                "half_cycle": np.asarray(half_cycles, dtype=int),
                "time_s": time_s,
                "current_mA": current_ma,
                "voltage_V": voltage_v,
                "capacity_mAh": capacity_mah,
            }

            # Extract metadata
            meta = {
                'num_half_cycles': int(half_abs),
                'max_voltage': float(np.nanmax(voltage_v)),
                'min_voltage': float(np.nanmin(voltage_v))
            }

            result['data'] = data_dict
            result['meta'] = meta

        except Exception as e:
            result['error'] = str(e)

        results[filename] = result

    return results
