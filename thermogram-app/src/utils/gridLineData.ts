/**
 * Grid Line Data Utilities - Generate time/temperature data for grid lines
 * and calculate curved line positions for precise interpolation.
 *
 * The cylindrical chart recorder creates curved vertical lines due to the
 * drum rotation. This module handles the curvature correction for accurate
 * time interpolation.
 */

import { getTimeConfigForTemplate } from "./chartTimeConfig";

export interface Point {
  x: number;
  y: number;
}

export interface GridCalibrationData {
  // Vertical line endpoints (for curve calculation)
  topPoint: Point;
  bottomPoint: Point;
  // Curve parameters
  curveCenterY: number;
  curvature: number; // Curvature coefficient (pixels offset at apex)
  // Vertical line positions (base X positions)
  lineSpacing: number;
  linePositions: number[];
  // Horizontal data
  horizontalSpacing: number;
  horizontalPositions: number[];
  horizontalTopTemp: number;
  // Reference values for time calculation
  referenceHour: number;
  referenceMinute: number;
}

export interface VerticalLineData {
  index: number;
  baseX: number;
  time: Date;
}

export interface HorizontalLineData {
  index: number;
  yPosition: number;
  temperature: number;
}

/**
 * Calculate the X position of a curved vertical line at a given Y coordinate.
 *
 * The curvature formula models the parabolic curve of vertical lines on
 * cylindrical drum charts. The curve bulges outward at the center Y.
 *
 * Formula: x = xBase + curvature * (y - topY) * (bottomY - y) / denom
 * where denom = (centerY - topY) * (bottomY - centerY)
 *
 * @param baseX - The base X position of the vertical line (at top)
 * @param y - The Y coordinate to calculate X at
 * @param topPoint - Top point of the reference vertical line
 * @param bottomPoint - Bottom point of the reference vertical line
 * @param centerY - Y coordinate where curvature is maximum
 * @param curvature - Curvature coefficient (positive = bulge right)
 */
export function getVerticalLineXAtY(
  baseX: number,
  y: number,
  topPoint: Point,
  bottomPoint: Point,
  centerY: number,
  curvature: number
): number {
  // If no curvature, just interpolate linearly
  if (Math.abs(curvature) < 0.001) {
    const t = (y - topPoint.y) / (bottomPoint.y - topPoint.y);
    return topPoint.x + (bottomPoint.x - topPoint.x) * t + (baseX - topPoint.x);
  }

  // Calculate the denominator for normalization
  const denom = (centerY - topPoint.y) * (bottomPoint.y - centerY);

  if (Math.abs(denom) < 0.001) {
    // Fallback to linear if denominator is too small
    const t = (y - topPoint.y) / (bottomPoint.y - topPoint.y);
    return topPoint.x + (bottomPoint.x - topPoint.x) * t + (baseX - topPoint.x);
  }

  // Calculate the linear interpolation part (for slanted lines)
  const t = (y - topPoint.y) / (bottomPoint.y - topPoint.y);
  const xLinear = topPoint.x + (bottomPoint.x - topPoint.x) * t;

  // Calculate the curvature offset
  const curveOffset = curvature * (y - topPoint.y) * (bottomPoint.y - y) / denom;

  // Apply the base offset from the reference line
  const baseOffset = baseX - topPoint.x;

  return xLinear + curveOffset + baseOffset;
}

/**
 * Generate time data for each vertical line starting from a given date/time.
 *
 * @param calibration - Grid calibration data
 * @param templateId - Template ID to determine time interval
 * @param startDate - Start date of the chart
 * @param startHour - Hour of the first vertical line (default from calibration)
 * @param startMinute - Minute of the first vertical line (default from calibration)
 */
export function generateVerticalLineData(
  calibration: GridCalibrationData,
  templateId: string,
  startDate: Date,
  startHour?: number,
  startMinute?: number
): VerticalLineData[] {
  const { linePositions, referenceHour, referenceMinute } = calibration;
  const timeConfig = getTimeConfigForTemplate(templateId);

  // Use provided start time or fall back to calibration reference
  const hour = startHour ?? referenceHour;
  const minute = startMinute ?? referenceMinute;

  // Create the start datetime
  const baseTime = new Date(startDate);
  baseTime.setHours(hour, minute, 0, 0);

  return linePositions.map((baseX, index) => {
    const time = new Date(baseTime.getTime() + index * timeConfig.minutesPerLine * 60 * 1000);
    return {
      index,
      baseX,
      time,
    };
  });
}

/**
 * Generate temperature data for each horizontal line.
 *
 * @param calibration - Grid calibration data
 */
export function generateHorizontalLineData(
  calibration: GridCalibrationData
): HorizontalLineData[] {
  const { horizontalPositions, horizontalTopTemp } = calibration;

  return horizontalPositions.map((yPosition, index) => {
    // Temperature decreases by 1 degree per horizontal spacing
    // (going down the image = lower temperature)
    const temperature = horizontalTopTemp - index;
    return {
      index,
      yPosition,
      temperature,
    };
  });
}

/**
 * Find the two adjacent vertical lines that a point's X falls between,
 * accounting for the curvature at the point's Y coordinate.
 *
 * Returns the indices of the left and right lines, and the interpolation ratio.
 */
export function findAdjacentVerticalLines(
  x: number,
  y: number,
  calibration: GridCalibrationData
): { leftIndex: number; rightIndex: number; ratio: number } | null {
  const { linePositions, topPoint, bottomPoint, curveCenterY, curvature } = calibration;

  if (linePositions.length < 2) {
    return null;
  }

  // Calculate the actual X position of each vertical line at this Y
  const actualXPositions = linePositions.map((baseX) =>
    getVerticalLineXAtY(baseX, y, topPoint, bottomPoint, curveCenterY, curvature)
  );

  // Find which two lines the point falls between
  for (let i = 0; i < actualXPositions.length - 1; i++) {
    const leftX = actualXPositions[i];
    const rightX = actualXPositions[i + 1];

    if (x >= leftX && x <= rightX) {
      const ratio = (x - leftX) / (rightX - leftX);
      return { leftIndex: i, rightIndex: i + 1, ratio };
    }
  }

  // Handle edge cases: point is before first line or after last line
  if (x < actualXPositions[0]) {
    // Extrapolate before first line
    const leftX = actualXPositions[0];
    const rightX = actualXPositions[1];
    const ratio = (x - leftX) / (rightX - leftX); // Will be negative
    return { leftIndex: 0, rightIndex: 1, ratio };
  }

  if (x > actualXPositions[actualXPositions.length - 1]) {
    // Extrapolate after last line
    const lastIdx = actualXPositions.length - 1;
    const leftX = actualXPositions[lastIdx - 1];
    const rightX = actualXPositions[lastIdx];
    const ratio = (x - leftX) / (rightX - leftX); // Will be > 1
    return { leftIndex: lastIdx - 1, rightIndex: lastIdx, ratio };
  }

  return null;
}

/**
 * Find the two adjacent horizontal lines that a point's Y falls between.
 *
 * Returns the indices of the top and bottom lines, and the interpolation ratio.
 */
export function findAdjacentHorizontalLines(
  y: number,
  calibration: GridCalibrationData
): { topIndex: number; bottomIndex: number; ratio: number } | null {
  const { horizontalPositions } = calibration;

  if (horizontalPositions.length < 2) {
    return null;
  }

  // Horizontal positions are sorted top to bottom (Y increases)
  for (let i = 0; i < horizontalPositions.length - 1; i++) {
    const topY = horizontalPositions[i];
    const bottomY = horizontalPositions[i + 1];

    if (y >= topY && y <= bottomY) {
      const ratio = (y - topY) / (bottomY - topY);
      return { topIndex: i, bottomIndex: i + 1, ratio };
    }
  }

  // Handle edge cases
  if (y < horizontalPositions[0]) {
    const topY = horizontalPositions[0];
    const bottomY = horizontalPositions[1];
    const ratio = (y - topY) / (bottomY - topY);
    return { topIndex: 0, bottomIndex: 1, ratio };
  }

  if (y > horizontalPositions[horizontalPositions.length - 1]) {
    const lastIdx = horizontalPositions.length - 1;
    const topY = horizontalPositions[lastIdx - 1];
    const bottomY = horizontalPositions[lastIdx];
    const ratio = (y - topY) / (bottomY - topY);
    return { topIndex: lastIdx - 1, bottomIndex: lastIdx, ratio };
  }

  return null;
}

/**
 * Interpolate temperature from Y coordinate using horizontal lines.
 *
 * @param y - Y coordinate of the point
 * @param calibration - Grid calibration data
 * @returns Interpolated temperature value
 */
export function interpolateTemperature(
  y: number,
  calibration: GridCalibrationData
): number {
  const horizontalLines = generateHorizontalLineData(calibration);
  const adjacent = findAdjacentHorizontalLines(y, calibration);

  if (!adjacent || horizontalLines.length < 2) {
    // Fallback: simple calculation
    const { horizontalPositions, horizontalSpacing: hSpacing, horizontalTopTemp } = calibration;
    if (horizontalPositions.length === 0 || hSpacing <= 0) {
      return 0;
    }
    const topY = horizontalPositions[0];
    const degreesOffset = (y - topY) / hSpacing;
    return horizontalTopTemp - degreesOffset;
  }

  const topTemp = horizontalLines[adjacent.topIndex].temperature;
  const bottomTemp = horizontalLines[adjacent.bottomIndex].temperature;

  // Linear interpolation between temperatures
  const temperature = topTemp + adjacent.ratio * (bottomTemp - topTemp);

  // Round to 1 decimal place
  return Math.round(temperature * 10) / 10;
}

/**
 * Interpolate time from X coordinate using curved vertical lines.
 *
 * @param x - X coordinate of the point
 * @param y - Y coordinate of the point (needed for curvature calculation)
 * @param verticalLines - Pre-calculated vertical line data with times
 * @param calibration - Grid calibration data
 * @returns Interpolated time as Date
 */
export function interpolateTime(
  x: number,
  y: number,
  verticalLines: VerticalLineData[],
  calibration: GridCalibrationData
): Date {
  const adjacent = findAdjacentVerticalLines(x, y, calibration);

  if (!adjacent || verticalLines.length < 2) {
    // Fallback: use first line's time
    return verticalLines.length > 0 ? verticalLines[0].time : new Date();
  }

  const leftTime = verticalLines[adjacent.leftIndex].time.getTime();
  const rightTime = verticalLines[adjacent.rightIndex].time.getTime();

  // Linear interpolation between times
  const interpolatedTime = leftTime + adjacent.ratio * (rightTime - leftTime);

  return new Date(interpolatedTime);
}

/**
 * Format a Date as dd/mm/yyyy hh:mm string.
 */
export function formatDateTime(date: Date): string {
  const day = date.getDate().toString().padStart(2, "0");
  const month = (date.getMonth() + 1).toString().padStart(2, "0");
  const year = date.getFullYear();
  const hours = date.getHours().toString().padStart(2, "0");
  const minutes = date.getMinutes().toString().padStart(2, "0");

  return `${day}/${month}/${year} ${hours}:${minutes}`;
}
