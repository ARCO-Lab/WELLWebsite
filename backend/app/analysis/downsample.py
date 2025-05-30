import numpy as np
import pandas as pd
from collections import defaultdict

def summarize_metrics(data: pd.DataFrame, max_points=300):
    # Rename for internal consistency
    data = data.rename(columns={"measurement_type": "metric", "recorded_at": "timestamp"})

    summary_output = defaultdict(dict)
    grouped = data.groupby("metric")

    for metric, group in grouped:
        if metric == "Battery":
            continue
        if metric == "RH":
            metric = "Relative Humidity"
        group_sorted = group.sort_values("timestamp")
        values = group_sorted["value"].values
        timestamps = pd.to_datetime(group_sorted["timestamp"]).values

        # Downsample
        step = max(1, len(values) // max_points)
        ds_values = values[::step]
        ds_times = timestamps[::step]

        # Summary statistics
        avg_val = np.mean(ds_values)
        max_val = np.max(ds_values)
        max_time = pd.to_datetime(ds_times[np.argmax(ds_values)]).strftime("%b %d %H:%M")
        min_val = np.min(ds_values)
        min_time = pd.to_datetime(ds_times[np.argmin(ds_values)]).strftime("%b %d %H:%M")

        # Trend: simple linear regression slope
        slope = np.polyfit(range(len(ds_values)), ds_values, 1)[0]
        rising_trend = slope > 0.05
        falling_trend = slope < -0.05

        # Detect anomalies
        anomalies = []
        std_dev = np.std(ds_values)
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

        summary_output[metric] = summary

    return dict(summary_output)


def downsample(weather_data_list, logger_data_list, quality_data_list):
    # Convert list of dicts to DataFrame and rename keys
    weather_df = pd.DataFrame(weather_data_list)
    logger_df = pd.DataFrame(logger_data_list)
    quality_df = pd.DataFrame(quality_data_list)

    weather_summary = summarize_metrics(weather_df)
    logger_summary = summarize_metrics(logger_df)
    quality_summary = summarize_metrics(quality_df)

    return weather_summary, logger_summary, quality_summary
