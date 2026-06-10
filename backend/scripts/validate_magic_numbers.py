"""Validate magic numbers engine against Excel cached values."""
import json
import sys
from pathlib import Path

from openpyxl import load_workbook

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from services.magic_numbers import DataSheet, compute_magic_numbers

EXCEL = Path(
    r"c:\Users\HOME\Desktop\4 - FUND JAIRO\2. ASSETS\2.1 THESIS\0. THESIS TOOL\FINANCIAL TOOL.xlsx"
)
JSON_PATH = Path(__file__).resolve().parents[1] / "data" / "msft_1data.json"

CHECKS = {
    "TOTALREVENUE": ("D7", "O7"),
    "FCFF": ("D21", "O21"),
    "ROE": ("D53", "O53"),
    "NET margin": ("D40", "O40"),
    "growth REVENUE": ("E27", "O27"),
}


def metric_lookup(result, label):
    for block in result["blocks"]:
        for m in block["metrics"]:
            if m["label"] == label:
                years = block["years"]
                return years[0], years[-1], m["values"][years[0]], m["values"][years[-1]]
    return None


def main():
    payload = json.loads(JSON_PATH.read_text(encoding="utf-8"))
    result = compute_magic_numbers(DataSheet(payload))
    mn = load_workbook(EXCEL, data_only=True)["2 MAGIC NUMBERS"]

    print("Validation vs Excel:")
    for label, (start_cell, end_cell) in CHECKS.items():
        found = metric_lookup(result, label)
        if not found:
            print(f"  {label}: NOT FOUND in engine")
            continue
        _, _, v_start, v_end = found
        x_start = mn[start_cell].value
        x_end = mn[end_cell].value
        ok_s = abs(v_start - x_start) < 0.01 if v_start and x_start else v_start == x_start
        ok_e = abs(v_end - x_end) < 0.0001 if v_end and x_end else v_end == x_end
        print(f"  {label}: start web={v_start} xl={x_start} {'OK' if ok_s else 'FAIL'}")
        print(f"           end   web={v_end} xl={x_end} {'OK' if ok_e else 'FAIL'}")


if __name__ == "__main__":
    main()
