import pandas as pd
from datetime import datetime
import os

class SamplingService:
    def __init__(self):
        # TEMPORARY: Load from local file
        self.excel_path = os.path.join(
            os.path.dirname(__file__),
            "../../samplingExcel/SampleData_Weekly.xlsx"
        )

        # FUTURE: Replace this with a call to the Borealis API
        # Example:
        # response = requests.get(BOREALIS_API_URL, headers={...})
        # df = pd.read_excel(BytesIO(response.content))

    def get_sampling_data(self):
        try:
            df = pd.read_excel(self.excel_path)

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
                date = datetime.strptime(str(row["Date"]), "%Y-%m-%d")
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

            return records

        except Exception as e:
            print(f"[ERROR] Failed to load or parse sampling data: {e}")
            return []

if __name__ == "__main__":
    service = SamplingService()
    data = service.get_sampling_data()
    for record in data[:5]:  # show first few
        print(record)
