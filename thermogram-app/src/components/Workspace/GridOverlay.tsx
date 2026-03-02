/**
 * GridOverlay - Canvas overlay for real-time grid line rendering.
 * Draws vertical lines with adjustable curvature without backend calls.
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
    verticalLinePositions,
    horizontalLinePositions,
    imageHeight,
    imageWidth,
    curveCoeffA,
    curveCoeffB,
    calibration,
  } = useImageStore();

  // Slider scales the detected curvature (0 = straight, 1 = full detected, 2 = exaggerated)
  const curvatureScale = (calibration.curvature ?? 0.5) * 2; // Map 0-1 to 0-2
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

    // Draw horizontal lines (green)
    if (showHorizontal && horizontalLinePositions.length > 0) {
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

    // Draw vertical lines (blue) with detected curvature
    if (showVertical && verticalLinePositions.length > 0) {
      ctx.strokeStyle = "#0000ff";
      ctx.lineWidth = 1;

      // Scale the detected coefficients by slider value
      const a = curveCoeffA * curvatureScale;
      const b = curveCoeffB * curvatureScale;
      const yMid = imageHeight / 2;

      // Find center of image (x-axis) and reference line closest to it
      const imageCenterX = imageWidth / 2;
      const centerLineX = verticalLinePositions.reduce((prev, curr) =>
        Math.abs(curr - imageCenterX) < Math.abs(prev - imageCenterX) ? curr : prev
      );

      // Calculate adjusted positions based on vSpacing
      const adjustedPositions = verticalLinePositions.map(xMid => {
        const distanceFromCenter = xMid - centerLineX;
        return centerLineX + distanceFromCenter * vSpacing;
      });

      for (const xMid of adjustedPositions) {
        ctx.beginPath();

        // Draw curve point by point
        // Formula keeps middle point fixed:
        // x = a*(y² - yMid²) + b*(y - yMid) + xMid
        // When y = yMid: x = xMid (fixed!)
        for (let y = 0; y < imageHeight; y += 5) {
          const dy = y - yMid;
          const x = a * (y * y - yMid * yMid) + b * dy + xMid;

          const scaledX = x * scaleX;
          const scaledY = y * scaleY;

          if (y === 0) {
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
    verticalLinePositions,
    horizontalLinePositions,
    imageHeight,
    imageWidth,
    curveCoeffA,
    curveCoeffB,
    curvatureScale,
    vSpacing,
    showVertical,
    showHorizontal,
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
