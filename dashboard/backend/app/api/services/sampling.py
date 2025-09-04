# This file defines the SamplingService class for loading and parsing creek/point sampling data from an Excel file.
# It maps columns to standardized measurement types and units for downstream processing.

import pandas as pd
from datetime import datetime
import io

class SamplingService:
    def __init__(self, excel_file: str):
        # Load the Excel file from the provided path (temporary file from download_data.py)
        self.excel_path = excel_file
        print(f"[INFO] Loading file: {self.excel_path}")

    def get_sampling_data(self):
        try:
            # Read the Excel file
            df = pd.read_excel(self.excel_path, engine="openpyxl")
            print("[INFO] Successfully read Excel file")

            # Define mappings for type and units
            metric_mappings = {
                "E. coli (CFU/100 mL)": ("E. coli", "CFU/100 mL"),
                "Total coliform (CFU/100 mL)": ("Total coliform", "CFU/100 mL"),
                "Turbidity (NTU)": ("Turbidity", "NTU"),
                "pH": ("pH", "pH units"),
                "Conductivity (µS/cm)": ("Conductivity", "µS/cm"),
                "Chloride (mg/L)": ("Chloride", "mg/L"),
                "Total phosphorus (µg/L)": ("Total phosphorus", "µg/L"),
                "Soluble reactive phosphorus (µg/L)": ("Soluble reactive phosphorus", "µg/L"),
                "Total nitrogen (mg/L)": ("Total nitrogen", "mg/L"),
                "Nitrate nitrogen (mg/L)": ("Nitrate nitrogen", "mg/L"),
                "Ammonia nitrogen (mg/L)": ("Ammonia nitrogen", "mg/L"),
            }

            records = []
            for _, row in df.iterrows():
                # Use pandas to_datetime for flexible date parsing
                date = pd.to_datetime(str(row["Date"])).to_pydatetime()
                
                for metric_col, (metric_type, unit) in metric_mappings.items():
                    value = row[metric_col]
                    if pd.notna(value):
                        records.append({
                            "site_id": row["Site"],
                            "creek_id": row["Stream"],
                            "measurement_type": metric_type,
                            "value": float(value),
                            "unit": unit,
                            "recorded_at": date.isoformat()
                        })

            print(f"[INFO] Parsed {len(records)} sampling records")
            return records

        except Exception as e:
            print(f"[ERROR] Failed to load or parse sampling data: {e}")
            return []

if __name__ == "__main__":
    # For testing: Use a local file path or the temporary file path
    import sys
    if len(sys.argv) < 2:
        print("[ERROR] Please provide the path to the Excel file")
        sys.exit(1)
    excel_file = sys.argv[1]
    service = SamplingService(excel_file)
    data = service.get_sampling_data()
    for record in data[:5]:  # show first few
        print(record)