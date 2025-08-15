import numpy as np
import pandas as pd
from collections import defaultdict


METRIC_NAME_MAP = {
    "RH": "Relative Humidity",
    "ODO": "Dissolved Oxygen (ODO)",
    "ODOSat": "Dissolved Oxygen Saturation (ODOSat)",
    "TDS": "Total Dissolved Solids (TDS)",
    "TSS": "Total Suspended Solids (TSS)",
    "Rain": "Rainfall",
}

# Helper function to contain the core summarization logic for a given dataset
def _create_metric_summaries(data: pd.DataFrame, max_points=300):
    summary_output = defaultdict(dict)
    if data.empty:
        return {}
        
    grouped = data.groupby("metric")

    for metric, group in grouped:
        if metric == "Battery":
            continue
        
        metric_display_name = METRIC_NAME_MAP.get(metric, metric)
        
        group_sorted = group.sort_values("timestamp")
        values = group_sorted["value"].values
        timestamps = pd.to_datetime(group_sorted["timestamp"]).values

        if len(values) == 0:
            continue

        step = max(1, len(values) // max_points)
        ds_values = values[::step]
        ds_times = timestamps[::step]

        avg_val = np.mean(ds_values)
        max_val = np.max(ds_values)
        max_time = pd.to_datetime(ds_times[np.argmax(ds_values)]).strftime("%b %d %H:%M")
        min_val = np.min(ds_values)
        min_time = pd.to_datetime(ds_times[np.argmin(ds_values)]).strftime("%b %d %H:%M")

        slope = np.polyfit(range(len(ds_values)), ds_values, 1)[0]
        rising_trend = slope > 0.05
        falling_trend = slope < -0.05

        anomalies = []
        std_dev = np.std(ds_values)
        if std_dev > 0:
            for v, t in zip(ds_values, ds_times):
                if abs(v - avg_val) > 2.5 * std_dev:
                    anomalies.append(f"{'spike' if v > avg_val else 'drop'} at {pd.to_datetime(t).strftime('%b %d %H:%M')}")

        summary = {
            "avg": round(avg_val, 2),
            "max": f"{round(max_val, 2)} on {max_time}",
            "min": f"{round(min_val, 2)} on {min_time}",
        }

        if rising_trend:
            summary["rising_trend"] = True
        elif falling_trend:
            summary["falling_trend"] = True
        else:
            summary["stable"] = True

        if anomalies:
            summary["anomalies"] = anomalies

        summary_output[metric_display_name] = summary

    return dict(summary_output)


def summarize_metrics(data: pd.DataFrame, max_points=300):
    if data.empty:
        return {}

    data = data.rename(columns={"measurement_type": "metric", "recorded_at": "timestamp"})

    # If the dataframe has multiple station_ids, group by station first.
    if 'station_id' in data.columns and data['station_id'].nunique() > 1:
        station_summary_output = defaultdict(dict)
        for station_id, station_group in data.groupby('station_id'):
            metric_summaries = _create_metric_summaries(station_group, max_points)
            station_summary_output[str(station_id)] = metric_summaries
        return dict(station_summary_output)
    else:
        # Otherwise, process as a single entity (for weather, quality).
        return _create_metric_summaries(data, max_points)



def summarize_sampling_data(data: pd.DataFrame):
    """
    Summarizes sampling data into a nested dictionary structure.
    The structure is: Creek -> Site -> Measurement Type -> Stats.
    This is different from sensor data due to the hierarchical nature.
    """
    if data.empty:
        return {}

    # Ensure 'value' is numeric, coercing errors and dropping invalid rows
    data['value'] = pd.to_numeric(data['value'], errors='coerce')
    data.dropna(subset=['value'], inplace=True)

    summary = defaultdict(lambda: defaultdict(dict))
    
    # Group by all three hierarchical levels at once for efficiency
    grouped = data.groupby(['creek_id', 'site_id', 'measurement_type'])

    for (creek_id, site_id, m_type), group in grouped:
        stats = {
            'min': round(group['value'].min(), 2),
            'max': round(group['value'].max(), 2),
            'avg': round(group['value'].mean(), 2),
            'count': len(group),
            'unit': group['unit'].iloc[0] if not group.empty else None
        }
        summary[str(creek_id)][str(site_id)][m_type] = stats
            
    # Convert defaultdict to regular dict for clean JSON output
    return {k: dict(v) for k, v in summary.items()}


def downsample(weather_data_list, logger_data_list, quality_data_list):
    # Convert list of dicts to DataFrame and rename keys
    weather_df = pd.DataFrame(weather_data_list)
    logger_df = pd.DataFrame(logger_data_list)
    quality_df = pd.DataFrame(quality_data_list)

    weather_summary = summarize_metrics(weather_df)
    logger_summary = summarize_metrics(logger_df)
    quality_summary = summarize_metrics(quality_df)

    return weather_summary, logger_summary, quality_summary
