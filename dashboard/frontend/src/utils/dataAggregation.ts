/**
 * Data aggregation utilities for high-performance rendering of large datasets in Highcharts.
 * Handles dynamic grouping based on chart pixel width and zoom level.
 */

export type AggregationMethod = 'average' | 'sum' | 'open' | 'close' | 'min' | 'max';

export interface AggregatedPoint {
  timestamp: number;
  value: number;
  originalCount?: number; // Number of raw points in this group
}

export interface AggregationConfig {
  targetPixelWidth?: number; // Pixels per aggregated point (default: 3)
  approximation?: AggregationMethod;
  preserveExtremes?: boolean; // Keep min/max detection
}

/**
 * Calculates the optimal group size based on chart dimensions and dataset size.
 * Formula: groupSize = ceil(totalPoints / (chartWidthPixels / targetPixelWidth))
 */
export function calculateGroupSize(
  totalPoints: number,
  chartPixelWidth: number,
  xMin?: number,
  xMax?: number,
  targetPixelWidth: number = 3
): number {
  // If we have zoom bounds, calculate points in visible range
  let visiblePoints = totalPoints;
  if (xMin !== undefined && xMax !== undefined && xMin !== xMax) {
    // Approximate visible points ratio
    const totalTimespan = (xMax - xMin) * 1.1; // Account for pan margin
    visiblePoints = Math.ceil(totalPoints * ((xMax - xMin) / totalTimespan));
  }

  // Ensure we have at least 1 point
  const targetPointsToDisplay = Math.max(1, Math.floor(chartPixelWidth / targetPixelWidth));
  const groupSize = Math.max(1, Math.ceil(visiblePoints / targetPointsToDisplay));
  
  return groupSize;
}

/**
 * Aggregates a single group of points using the specified method.
 */
function aggregateGroup(
  group: [number, number][],
  approximation: AggregationMethod = 'average'
): [number, number] {
  if (group.length === 0) return [0, 0];
  if (group.length === 1) return group[0];

  const values = group.map(p => p[1]);
  const timestamp = group[0][0]; // Use first timestamp in group

  let aggregatedValue: number;

  switch (approximation) {
    case 'sum':
      aggregatedValue = values.reduce((a, b) => a + b, 0);
      break;
    case 'open':
      aggregatedValue = values[0];
      break;
    case 'close':
      aggregatedValue = values[values.length - 1];
      break;
    case 'min':
      aggregatedValue = Math.min(...values);
      break;
    case 'max':
      aggregatedValue = Math.max(...values);
      break;
    case 'average':
    default:
      aggregatedValue = values.reduce((a, b) => a + b, 0) / values.length;
  }

  return [timestamp, aggregatedValue];
}

/**
 * Aggregates time series data based on group size.
 * Groups consecutive points and applies aggregation method to each group.
 */
export function aggregateTimeSeriesData(
  data: [number, number][],
  groupSize: number = 1,
  config: AggregationConfig = {}
): [number, number][] {
  const { approximation = 'average' } = config;

  if (groupSize <= 1 || data.length <= 1) {
    return data;
  }

  const aggregated: [number, number][] = [];

  for (let i = 0; i < data.length; i += groupSize) {
    const group = data.slice(i, i + groupSize);
    const aggregatedPoint = aggregateGroup(group, approximation);
    aggregated.push(aggregatedPoint);
  }

  return aggregated;
}

/**
 * Smart aggregation that considers both the dataset size and chart pixel width.
 * Returns aggregated data optimized for display.
 */
export function smartAggregateData(
  data: [number, number][],
  chartPixelWidth: number,
  config: AggregationConfig & { xMin?: number; xMax?: number } = {}
): {
  aggregated: [number, number][];
  groupSize: number;
  pointsReduction: number; // (original - aggregated) / original * 100
} {
  const { targetPixelWidth = 3, approximation = 'average', xMin, xMax } = config;

  if (data.length === 0 || chartPixelWidth <= 0) {
    return {
      aggregated: data,
      groupSize: 1,
      pointsReduction: 0,
    };
  }

  const groupSize = calculateGroupSize(data.length, chartPixelWidth, xMin, xMax, targetPixelWidth);
  const aggregated = aggregateTimeSeriesData(data, groupSize, { approximation });
  const pointsReduction = ((data.length - aggregated.length) / data.length) * 100;

  return {
    aggregated,
    groupSize,
    pointsReduction,
  };
}

/**
 * Re-aggregates data based on new zoom bounds.
 * Useful for responding to Highcharts afterSetExtremes events.
 */
export function reaggregateOnZoom(
  originalData: [number, number][],
  chartPixelWidth: number,
  xMin: number,
  xMax: number,
  config: AggregationConfig = {}
): {
  aggregated: [number, number][];
  groupSize: number;
} {
  const { targetPixelWidth = 3, approximation = 'average' } = config;

  // Use only the visible range to decide grouping density,
  // but keep the full timeline data so users can zoom back out.
  const visiblePoints = originalData.filter(([timestamp]) => timestamp >= xMin && timestamp <= xMax).length;
  const targetPointsToDisplay = Math.max(1, Math.floor(chartPixelWidth / targetPixelWidth));
  const groupSize = Math.max(1, Math.ceil(visiblePoints / targetPointsToDisplay));
  const aggregated = aggregateTimeSeriesData(originalData, groupSize, { approximation });

  return {
    aggregated,
    groupSize,
  };
}

/**
 * Filters aggregated data to show original data points when heavily zoomed in.
 * Useful for progressive disclosure of detail as user zooms deeper.
 */
export function getDetailedDataInRange(
  originalData: [number, number][],
  xMin: number,
  xMax: number,
  maxPoints: number = 5000
): [number, number][] {
  let filtered = originalData.filter(([timestamp]) => timestamp >= xMin && timestamp <= xMax);

  // If still too many points after filtering, aggregate
  if (filtered.length > maxPoints) {
    const groupSize = Math.ceil(filtered.length / maxPoints);
    filtered = aggregateTimeSeriesData(filtered, groupSize, { approximation: 'average' });
  }

  return filtered;
}

/**
 * Calculates aggregation metadata for debugging/logging purposes.
 */
export function getAggregationStats(
  originalLength: number,
  aggregatedLength: number
): {
  reductionPercentage: number;
  compressionRatio: number;
  groupSize: number;
} {
  const reductionPercentage = ((originalLength - aggregatedLength) / originalLength) * 100;
  const compressionRatio = originalLength / aggregatedLength;
  const groupSize = Math.ceil(originalLength / aggregatedLength);

  return {
    reductionPercentage: Math.round(reductionPercentage * 100) / 100,
    compressionRatio: Math.round(compressionRatio * 100) / 100,
    groupSize,
  };
}
