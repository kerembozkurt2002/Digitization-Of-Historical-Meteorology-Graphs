/**
 * GridOverlay - Canvas overlay for real-time grid line rendering.
 * Draws vertical lines with calibrated curvature.
 *
 * Curve formula (matching CalibrationCanvas):
 * x(y) = x_base(y) + offset(y)
 * Where:
 *   x_base = linear interpolation from top to bottom point
 *   offset = curvature * (y - top.y) * (bottom.y - y) / [(centerY - top.y) * (bottom.y - centerY)]
 */

import { useEffect, useRef } from "react";
import { useImageStore } from "../../stores/imageStore";

interface GridOverlayProps {
  width: number;
  height: number;
  showVertical: boolean;
  showHorizontal: boolean;
}

export function GridOverlay({ width, height, showVertical, showHorizontal }: GridOverlayProps) {
  const canvasRef = useRef<HTMLCanvasElement>(null);

  const {
    horizontalLinePositions,
    imageHeight,
    imageWidth,
    calibration,
    gridCalibration,
  } = useImageStore();

  const hasCalibration = gridCalibration !== null;

  // Slider for spacing adjustment
  const vSpacing = calibration.vSpacing ?? 1.0;

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;

    const ctx = canvas.getContext("2d");
    if (!ctx) return;

    // Clear canvas
    ctx.clearRect(0, 0, width, height);

    // Calculate scale factors
    const scaleX = width / imageWidth;
    const scaleY = height / imageHeight;

    // Draw horizontal lines from calibration (straight lines, no curvature)
    if (showHorizontal && hasCalibration && gridCalibration && gridCalibration.horizontalPositions.length > 0) {
      ctx.strokeStyle = "#00cc00"; // Green for horizontal lines
      ctx.lineWidth = 1;

      for (const yPos of gridCalibration.horizontalPositions) {
        const scaledY = yPos * scaleY;
        ctx.beginPath();
        ctx.moveTo(0, scaledY);
        ctx.lineTo(width, scaledY);
        ctx.stroke();
      }
    } else if (showHorizontal && horizontalLinePositions.length > 0) {
      // Fallback to auto-detected positions
      ctx.strokeStyle = "#00ff00";
      ctx.lineWidth = 1;

      for (const yPos of horizontalLinePositions) {
        const scaledY = yPos * scaleY;
        ctx.beginPath();
        ctx.moveTo(0, scaledY);
        ctx.lineTo(width, scaledY);
        ctx.stroke();
      }
    }

    // Draw vertical lines ONLY if calibration exists
    if (showVertical && hasCalibration && gridCalibration) {
      const {
        topPoint,
        bottomPoint,
        linePositions,
        curveCenterY,
        curvature,
      } = gridCalibration;

      if (linePositions.length === 0 || !topPoint || !bottomPoint) return;

      ctx.strokeStyle = "#0066ff"; // Blue for vertical lines
      ctx.lineWidth = 1;

      // Reference line (first calibrated line)
      const refTopX = topPoint.x;
      const refBottomX = bottomPoint.x;
      const refTopY = topPoint.y;
      const refBottomY = bottomPoint.y;
      const yRange = refBottomY - refTopY;

      // Precompute denominator for offset (avoid division by zero)
      const denominator = (curveCenterY - refTopY) * (refBottomY - curveCenterY);
      const hasValidCurvature = Math.abs(denominator) > 0.001 && curvature !== 0;

      // Find center of image (x-axis) and reference line closest to it
      const imageCenterX = imageWidth / 2;
      const centerLineX = linePositions.reduce((prev, curr) =>
        Math.abs(curr - imageCenterX) < Math.abs(prev - imageCenterX) ? curr : prev
      );

      // Calculate adjusted positions based on vSpacing slider
      const adjustedPositions = linePositions.map(baseX => {
        const distanceFromCenter = baseX - centerLineX;
        return centerLineX + distanceFromCenter * vSpacing;
      });

      for (const lineX of adjustedPositions) {
        ctx.beginPath();

        // Calculate offset from reference line to this line
        const offsetFromRef = lineX - refTopX;

        // Draw curve point by point (same formula as CalibrationCanvas)
        const yStart = Math.max(0, refTopY);
        const yEnd = Math.min(imageHeight, refBottomY);

        for (let y = yStart; y <= yEnd; y += 3) {
          // Linear interpolation: straight line from top to bottom
          const t = yRange !== 0 ? (y - refTopY) / yRange : 0;
          const xBase = refTopX + (refBottomX - refTopX) * t + offsetFromRef;

          // Parabolic offset: 0 at endpoints, curvature at centerY
          let offset = 0;
          if (hasValidCurvature) {
            offset = curvature * (y - refTopY) * (refBottomY - y) / denominator;
          }

          const x = xBase + offset;

          const scaledX = x * scaleX;
          const scaledY = y * scaleY;

          if (y === yStart) {
            ctx.moveTo(scaledX, scaledY);
          } else {
            ctx.lineTo(scaledX, scaledY);
          }
        }

        ctx.stroke();
      }
    }
  }, [
    width,
    height,
    horizontalLinePositions,
    imageHeight,
    imageWidth,
    vSpacing,
    showVertical,
    showHorizontal,
    hasCalibration,
    gridCalibration,
  ]);

  // Don't render if no dimensions
  if (imageWidth === 0 || imageHeight === 0) {
    return null;
  }

  return (
    <canvas
      ref={canvasRef}
      width={width}
      height={height}
      style={{
        position: "absolute",
        top: 0,
        left: 0,
        pointerEvents: "none",
      }}
    />
  );
}

export default GridOverlay;
