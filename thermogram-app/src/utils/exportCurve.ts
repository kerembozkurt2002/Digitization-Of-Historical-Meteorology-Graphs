/**
 * Export Curve Utility - Exports curve data to CSV format with precise interpolation.
 *
 * Converts pixel coordinates to time and temperature values using:
 * - Cylindrical curvature correction for accurate time interpolation
 * - Proper temperature interpolation between horizontal grid lines
 * - Date tracking across multi-day charts (weekly/4-day)
 * - Template-specific time intervals
 */

import type { CurvePoint } from "../types";
import {
  type GridCalibrationData,
  generateVerticalLineData,
  interpolateTemperature,
  interpolateTime,
  formatDateTime,
} from "./gridLineData";

export interface ExportConfig {
  startDate: Date;
  startHour: number;
  startMinute: number;
  templateId: string;
}

interface ExportRow {
  id: number;
  time: string;
  temperature: number;
  xValue: number;
  yValue: number;
  isEdited?: "yes" | "no";
}

/**
 * Check if a point has been edited by comparing with raw point.
 */
function isPointEdited(
  point: CurvePoint,
  rawPoint: CurvePoint | undefined
): boolean {
  if (!rawPoint) return true;
  const tolerance = 0.01;
  return (
    Math.abs(point.x - rawPoint.x) > tolerance ||
    Math.abs(point.y - rawPoint.y) > tolerance
  );
}

/**
 * Check if any point in the curve has been edited.
 */
export function isCurveEdited(
  points: CurvePoint[],
  rawPoints: CurvePoint[]
): boolean {
  if (points.length !== rawPoints.length) return true;

  for (let i = 0; i < points.length; i++) {
    if (isPointEdited(points[i], rawPoints[i])) {
      return true;
    }
  }

  return false;
}

/**
 * Generate export rows from curve points with precise interpolation.
 *
 * Uses curvature-corrected time calculation and proper temperature interpolation.
 */
export function generateExportData(
  points: CurvePoint[],
  rawPoints: CurvePoint[],
  calibration: GridCalibrationData,
  config: ExportConfig
): ExportRow[] {
  const hasEdits = isCurveEdited(points, rawPoints);

  // Generate vertical line data with times
  const verticalLines = generateVerticalLineData(
    calibration,
    config.templateId,
    config.startDate,
    config.startHour,
    config.startMinute
  );

  return points.map((point, index) => {
    // Interpolate time using curvature correction
    const time = interpolateTime(point.x, point.y, verticalLines, calibration);

    // Interpolate temperature from horizontal lines
    const temperature = interpolateTemperature(point.y, calibration);

    const row: ExportRow = {
      id: index + 1,
      time: formatDateTime(time),
      temperature,
      xValue: Math.round(point.x * 100) / 100,
      yValue: Math.round(point.y * 100) / 100,
    };

    if (hasEdits) {
      row.isEdited = isPointEdited(point, rawPoints[index]) ? "yes" : "no";
    }

    return row;
  });
}

/**
 * Convert export data to CSV string.
 *
 * Column order: id, time, temperature, xValue, yValue, [isEdited]
 */
export function exportToCSV(rows: ExportRow[]): string {
  if (rows.length === 0) return "";

  const hasEdits = rows[0].isEdited !== undefined;

  // Header
  const headers = hasEdits
    ? ["id", "time", "temperature", "xValue", "yValue", "isEdited"]
    : ["id", "time", "temperature", "xValue", "yValue"];

  const lines = [headers.join(",")];

  // Data rows
  for (const row of rows) {
    const values = hasEdits
      ? [row.id, row.time, row.temperature, row.xValue, row.yValue, row.isEdited]
      : [row.id, row.time, row.temperature, row.xValue, row.yValue];
    lines.push(values.join(","));
  }

  return lines.join("\n");
}

/**
 * Trigger CSV download in browser.
 */
export function downloadCSV(csvContent: string, filename: string): void {
  const blob = new Blob([csvContent], { type: "text/csv;charset=utf-8;" });
  const url = URL.createObjectURL(blob);

  const link = document.createElement("a");
  link.href = url;
  link.download = filename;
  link.style.display = "none";

  document.body.appendChild(link);
  link.click();
  document.body.removeChild(link);

  URL.revokeObjectURL(url);
}

/**
 * Main export function - generates CSV and triggers download.
 *
 * @param points - Edited curve points
 * @param rawPoints - Original extracted points (for edit tracking)
 * @param calibration - Grid calibration data
 * @param config - Export configuration (date, time, template)
 */
export function exportCurveData(
  points: CurvePoint[],
  rawPoints: CurvePoint[],
  calibration: GridCalibrationData,
  config: ExportConfig
): void {
  const rows = generateExportData(points, rawPoints, calibration, config);
  const csv = exportToCSV(rows);

  // Format filename with date
  const dateStr = config.startDate.toISOString().slice(0, 10);
  const filename = `${config.templateId}_curve_${dateStr}.csv`;

  downloadCSV(csv, filename);
}
