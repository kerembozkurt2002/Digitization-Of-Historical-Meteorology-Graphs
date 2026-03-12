/**
 * CalibrationCanvas - Interactive canvas for multi-step calibration.
 *
 * Features:
 * - Click to place points
 * - Real-time curve preview with FIXED endpoints
 * - Full grid preview on spacing steps
 * - Rotation support (CSS transform)
 * - Pan and zoom support
 *
 * New step order:
 * - Steps 1-3: Horizontal (rotation + spacing)
 * - Steps 4-7: Vertical (curvature + spacing)
 */

import { useCallback, useEffect, useRef } from "react";
import { useCalibrationStore } from "../../stores/calibrationStore";

interface CalibrationCanvasProps {
  imageData: string;
  width: number;
  height: number;
}

export function CalibrationCanvas({ imageData, width, height }: CalibrationCanvasProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const imageRef = useRef<HTMLImageElement | null>(null);

  const {
    currentStep,
    phase,
    zoom,
    rotationAngle,
    // Alignment mode
    savedCalibration,
    alignmentPoint,
    alignmentEndPoint,
    setAlignmentPoint,
    setAlignmentEndPoint,
    calculateAlignmentRotation,
    // Horizontal points (steps 1-3)
    horizontalTop,
    horizontalEndPoint,
    setHorizontalTop,
    setHorizontalEndPoint,
    // Spacing (pixel values)
    horizontalSpacing,
    verticalSpacing,
    // Vertical points (steps 4-7)
    verticalLine1Top,
    verticalLine1Bottom,
    setVerticalLine1Top,
    setVerticalLine1Bottom,
    // Curve params
    centerY,
    curvature,
  } = useCalibrationStore();

  // Canvas size = image size * zoom for scrollable display
  const canvasWidth = width * zoom;
  const canvasHeight = height * zoom;

  // Load image
  useEffect(() => {
    const img = new Image();
    img.onload = () => {
      imageRef.current = img;
      drawCanvas();
    };
    img.src = `data:image/png;base64,${imageData}`;
  }, [imageData]);

  // Redraw when state changes
  useEffect(() => {
    drawCanvas();
  }, [
    currentStep, phase, zoom, rotationAngle,
    horizontalTop, horizontalEndPoint, horizontalSpacing,
    verticalLine1Top, verticalLine1Bottom,
    centerY, curvature, verticalSpacing,
    canvasWidth, canvasHeight,
    alignmentPoint, alignmentEndPoint, savedCalibration
  ]);


  const drawCanvas = useCallback(() => {
    const canvas = canvasRef.current;
    const ctx = canvas?.getContext("2d");
    const img = imageRef.current;
    if (!canvas || !ctx || !img) return;

    ctx.clearRect(0, 0, canvas.width, canvas.height);
    ctx.save();

    // Apply rotation if we have rotation angle (step 3+)
    if (phase !== "alignment" && rotationAngle !== 0 && currentStep >= 3) {
      // Rotate around the horizontal top point
      const pivotX = (horizontalTop?.x ?? 0) * zoom;
      const pivotY = (horizontalTop?.y ?? 0) * zoom;
      ctx.translate(pivotX, pivotY);
      ctx.rotate(-rotationAngle); // Negative to counter the detected rotation
      ctx.translate(-pivotX, -pivotY);
    }

    ctx.scale(zoom, zoom);

    // Draw image
    ctx.drawImage(img, 0, 0);

    ctx.restore();
    ctx.save();
    ctx.scale(zoom, zoom);

    // Draw calibration elements based on phase and step
    if (phase === "alignment") {
      drawAlignmentPreview(ctx);
    } else if (phase === "horizontal") {
      if (currentStep === 3) {
        // Step 3: Full horizontal grid preview with spacing adjustment
        drawHorizontalGridPreview(ctx);
      } else {
        drawHorizontalCalibration(ctx);
      }
    } else if (phase === "vertical") {
      if (currentStep === 7) {
        // Step 7: Full vertical grid preview with spacing adjustment
        drawVerticalGridPreview(ctx);
      } else {
        drawVerticalCalibration(ctx);
      }
    }

    ctx.restore();
  }, [
    zoom, phase, currentStep, rotationAngle,
    horizontalTop, horizontalEndPoint, horizontalSpacing,
    verticalLine1Top, verticalLine1Bottom,
    centerY, curvature, verticalSpacing, height, width,
    alignmentPoint, alignmentEndPoint, savedCalibration
  ]);

  // Draw horizontal calibration (steps 1-2)
  const drawHorizontalCalibration = (ctx: CanvasRenderingContext2D) => {
    // Draw horizontal top point (step 1)
    if (horizontalTop) {
      drawPoint(ctx, horizontalTop.x, horizontalTop.y, "#ff6b6b", "H1");

      // Draw line from start to end if we have end point (step 2)
      if (horizontalEndPoint) {
        drawPoint(ctx, horizontalEndPoint.x, horizontalEndPoint.y, "#4ecdc4", "H2");

        // Draw line connecting the two points
        ctx.beginPath();
        ctx.strokeStyle = "#00cc00";
        ctx.lineWidth = 2 / zoom;
        ctx.setLineDash([5 / zoom, 5 / zoom]);
        ctx.moveTo(horizontalTop.x, horizontalTop.y);
        ctx.lineTo(horizontalEndPoint.x, horizontalEndPoint.y);
        ctx.stroke();
        ctx.setLineDash([]);

        // Draw a reference horizontal line to show where it should be
        ctx.beginPath();
        ctx.strokeStyle = "#ffcc00";
        ctx.lineWidth = 1 / zoom;
        ctx.moveTo(0, horizontalTop.y);
        ctx.lineTo(width, horizontalTop.y);
        ctx.stroke();
      } else {
        // Just draw horizontal line at the point
        ctx.beginPath();
        ctx.strokeStyle = "#00cc00";
        ctx.lineWidth = 1 / zoom;
        ctx.moveTo(0, horizontalTop.y);
        ctx.lineTo(width, horizontalTop.y);
        ctx.stroke();
      }
    }
  };

  // Draw full horizontal grid preview for spacing adjustment (step 3)
  const drawHorizontalGridPreview = (ctx: CanvasRenderingContext2D) => {
    if (!horizontalTop) return;

    // Generate line positions based on horizontalSpacing
    // NOTE: No lines ABOVE the first horizontal line
    const linePositions: number[] = [];

    // Lines from top line downward only
    let y = horizontalTop.y;
    while (y <= height + horizontalSpacing) {
      if (y >= 0 && y <= height) {
        linePositions.push(y);
      }
      y += horizontalSpacing;
    }

    // Draw all horizontal lines
    ctx.strokeStyle = "#00cc00";
    ctx.lineWidth = 1 / zoom;

    for (const lineY of linePositions) {
      ctx.beginPath();
      ctx.moveTo(0, lineY);
      ctx.lineTo(width, lineY);
      ctx.stroke();
    }

    // Draw reference point
    drawPoint(ctx, horizontalTop.x, horizontalTop.y, "#ff6b6b", "H1");
  };

  // Draw vertical calibration (steps 4-6)
  const drawVerticalCalibration = (ctx: CanvasRenderingContext2D) => {
    // Draw first vertical line points and curve
    if (verticalLine1Top) {
      drawPoint(ctx, verticalLine1Top.x, verticalLine1Top.y, "#ff6b6b", "V1");

      if (verticalLine1Bottom) {
        drawPoint(ctx, verticalLine1Bottom.x, verticalLine1Bottom.y, "#4ecdc4", "V2");

        // Draw the calibrated curve (BLUE) with fixed endpoints
        drawCalibratedVerticalLine(
          ctx,
          verticalLine1Top,
          verticalLine1Bottom,
          centerY,
          curvature
        );

        // Draw crosshair at curve apex (only during curvature slider step)
        if (currentStep === 6) {
          drawCurveApexCrosshair(ctx, verticalLine1Top, verticalLine1Bottom, centerY, curvature);
        }
      }
    }

    // Also draw horizontal grid for reference (from step 3)
    if (horizontalTop && currentStep >= 4) {
      ctx.save();
      ctx.globalAlpha = 0.5;

      let y = horizontalTop.y;
      while (y <= height + horizontalSpacing) {
        if (y >= 0 && y <= height) {
          ctx.beginPath();
          ctx.strokeStyle = "#00cc00";
          ctx.lineWidth = 1 / zoom;
          ctx.moveTo(0, y);
          ctx.lineTo(width, y);
          ctx.stroke();
        }
        y += horizontalSpacing;
      }

      ctx.restore();
    }
  };

  // Draw full vertical grid preview for spacing adjustment (step 7)
  const drawVerticalGridPreview = (ctx: CanvasRenderingContext2D) => {
    if (!verticalLine1Top || !verticalLine1Bottom) return;

    const top = verticalLine1Top;
    const bottom = verticalLine1Bottom;
    const yStart = Math.min(top.y, bottom.y);
    const yEnd = Math.max(top.y, bottom.y);
    const yRange = bottom.y - top.y;
    const denominator = (centerY - top.y) * (bottom.y - centerY);
    const hasValidCurvature = Math.abs(denominator) > 0.001 && curvature !== 0;

    // Generate line positions based on verticalSpacing
    // NOTE: No lines to the LEFT of the first vertical line
    const linePositions: number[] = [];

    // Lines from first line to right only
    let x = top.x;
    while (x <= width + verticalSpacing) {
      if (x >= 0 && x <= width) {
        linePositions.push(x);
      }
      x += verticalSpacing;
    }

    // Sort positions
    linePositions.sort((a, b) => a - b);

    // Draw all vertical lines with curvature
    ctx.strokeStyle = "#0066ff";
    ctx.lineWidth = 1 / zoom;

    for (const lineX of linePositions) {
      ctx.beginPath();
      const offsetFromRef = lineX - top.x;

      for (let y = yStart; y <= yEnd; y += 3) {
        const t = yRange !== 0 ? (y - top.y) / yRange : 0;
        const xBase = top.x + (bottom.x - top.x) * t + offsetFromRef;

        let offset = 0;
        if (hasValidCurvature) {
          offset = curvature * (y - top.y) * (bottom.y - y) / denominator;
        }

        const finalX = xBase + offset;

        if (y === yStart) {
          ctx.moveTo(finalX, y);
        } else {
          ctx.lineTo(finalX, y);
        }
      }
      ctx.stroke();
    }

    // Draw reference point
    drawPoint(ctx, verticalLine1Top.x, verticalLine1Top.y, "#ff6b6b", "V1");

    // Also draw horizontal grid for reference
    if (horizontalTop) {
      ctx.save();
      ctx.globalAlpha = 0.5;

      let y = horizontalTop.y;
      while (y <= height + horizontalSpacing) {
        if (y >= 0 && y <= height) {
          ctx.beginPath();
          ctx.strokeStyle = "#00cc00";
          ctx.lineWidth = 1 / zoom;
          ctx.moveTo(0, y);
          ctx.lineTo(width, y);
          ctx.stroke();
        }
        y += horizontalSpacing;
      }

      ctx.restore();
    }
  };

  // Draw alignment preview - shows grid based on two anchor points
  const drawAlignmentPreview = (ctx: CanvasRenderingContext2D) => {
    // Draw first point if exists
    if (alignmentPoint) {
      drawPoint(ctx, alignmentPoint.x, alignmentPoint.y, "#ff6b6b", "A1");

      // If we have both points, show the rotation preview
      if (alignmentEndPoint && savedCalibration) {
        drawPoint(ctx, alignmentEndPoint.x, alignmentEndPoint.y, "#4ecdc4", "A2");

        // Draw line connecting the two points
        ctx.beginPath();
        ctx.strokeStyle = "#ffcc00";
        ctx.lineWidth = 2 / zoom;
        ctx.setLineDash([5 / zoom, 5 / zoom]);
        ctx.moveTo(alignmentPoint.x, alignmentPoint.y);
        ctx.lineTo(alignmentEndPoint.x, alignmentEndPoint.y);
        ctx.stroke();
        ctx.setLineDash([]);

        // Calculate and draw the rotated grid preview
        const rotation = calculateAlignmentRotation();
        drawRotatedAlignmentGrid(ctx, rotation);
      }
    }
  };

  // Draw alignment grid with rotation applied
  const drawRotatedAlignmentGrid = (ctx: CanvasRenderingContext2D, rotation: number) => {
    if (!alignmentPoint || !savedCalibration) return;

    const {
      verticalSpacing: vSpacing,
      horizontalSpacing: hSpacing,
      curvature: curv,
      centerY: origCenterY,
      topPoint: origTop,
      bottomPoint: origBottom,
    } = savedCalibration;

    // Calculate offset
    const offsetX = alignmentPoint.x - origTop.x;
    const offsetY = alignmentPoint.y - origTop.y;

    const newTopX = alignmentPoint.x;
    const newTopY = alignmentPoint.y;
    const newBottomX = origBottom.x + offsetX;
    const newBottomY = origBottom.y + offsetY;
    const newCenterY = origCenterY + offsetY;

    // Apply rotation transform around alignment point
    ctx.save();
    ctx.translate(alignmentPoint.x, alignmentPoint.y);
    ctx.rotate(-rotation); // Counter the detected rotation
    ctx.translate(-alignmentPoint.x, -alignmentPoint.y);

    // Curve parameters
    const yStart = Math.min(newTopY, newBottomY);
    const yEnd = Math.max(newTopY, newBottomY);
    const yRange = newBottomY - newTopY;
    const denominator = (newCenterY - newTopY) * (newBottomY - newCenterY);
    const hasValidCurvature = Math.abs(denominator) > 0.001 && curv !== 0;

    // Generate vertical line positions (to the right only)
    const vLinePositions: number[] = [];
    let x = newTopX;
    while (x <= width + vSpacing) {
      if (x >= 0 && x <= width) {
        vLinePositions.push(x);
      }
      x += vSpacing;
    }

    // Draw vertical lines with curvature
    ctx.strokeStyle = "#0066ff";
    ctx.lineWidth = 1 / zoom;

    for (const lineX of vLinePositions) {
      ctx.beginPath();
      const offsetFromRef = lineX - newTopX;

      for (let y = yStart; y <= yEnd; y += 3) {
        const t = yRange !== 0 ? (y - newTopY) / yRange : 0;
        const xBase = newTopX + (newBottomX - newTopX) * t + offsetFromRef;

        let curveOffset = 0;
        if (hasValidCurvature) {
          curveOffset = curv * (y - newTopY) * (newBottomY - y) / denominator;
        }

        const finalX = xBase + curveOffset;

        if (y === yStart) {
          ctx.moveTo(finalX, y);
        } else {
          ctx.lineTo(finalX, y);
        }
      }
      ctx.stroke();
    }

    // Generate horizontal line positions
    const hLinePositions: number[] = [];
    let y = newTopY;
    while (y <= height + hSpacing) {
      if (y >= 0 && y <= height) {
        hLinePositions.push(y);
      }
      y += hSpacing;
    }

    // Draw horizontal lines
    ctx.strokeStyle = "#00cc00";
    ctx.lineWidth = 1 / zoom;

    for (const lineY of hLinePositions) {
      ctx.beginPath();
      ctx.moveTo(0, lineY);
      ctx.lineTo(width * 2, lineY); // Extended to account for rotation
      ctx.stroke();
    }

    ctx.restore();
  };

  const drawPoint = (
    ctx: CanvasRenderingContext2D,
    x: number,
    y: number,
    color: string,
    label: string
  ) => {
    // Outer circle
    ctx.beginPath();
    ctx.arc(x, y, 10 / zoom, 0, Math.PI * 2);
    ctx.fillStyle = "white";
    ctx.fill();

    // Inner circle
    ctx.beginPath();
    ctx.arc(x, y, 8 / zoom, 0, Math.PI * 2);
    ctx.fillStyle = color;
    ctx.fill();

    // Cross marker
    ctx.beginPath();
    ctx.strokeStyle = "white";
    ctx.lineWidth = 2 / zoom;
    const crossSize = 5 / zoom;
    ctx.moveTo(x - crossSize, y);
    ctx.lineTo(x + crossSize, y);
    ctx.moveTo(x, y - crossSize);
    ctx.lineTo(x, y + crossSize);
    ctx.stroke();

    // Label
    ctx.fillStyle = "white";
    ctx.font = `bold ${14 / zoom}px sans-serif`;
    ctx.textAlign = "center";
    ctx.fillText(label, x, y - 16 / zoom);
  };

  const drawCalibratedVerticalLine = (
    ctx: CanvasRenderingContext2D,
    top: { x: number; y: number },
    bottom: { x: number; y: number },
    centerY: number,
    curvature: number
  ) => {
    ctx.beginPath();
    ctx.strokeStyle = "#0066ff";
    ctx.lineWidth = 2 / zoom;

    const yStart = Math.min(top.y, bottom.y);
    const yEnd = Math.max(top.y, bottom.y);
    const yRange = bottom.y - top.y;

    const denominator = (centerY - top.y) * (bottom.y - centerY);
    const hasValidCurvature = Math.abs(denominator) > 0.001 && curvature !== 0;

    for (let y = yStart; y <= yEnd; y += 2) {
      const t = yRange !== 0 ? (y - top.y) / yRange : 0;
      const xBase = top.x + (bottom.x - top.x) * t;

      let offset = 0;
      if (hasValidCurvature) {
        offset = curvature * (y - top.y) * (bottom.y - y) / denominator;
      }

      const x = xBase + offset;

      if (y === yStart) {
        ctx.moveTo(x, y);
      } else {
        ctx.lineTo(x, y);
      }
    }

    ctx.stroke();
  };

  const drawCurveApexCrosshair = (
    ctx: CanvasRenderingContext2D,
    top: { x: number; y: number },
    bottom: { x: number; y: number },
    centerY: number,
    curvature: number
  ) => {
    const apexY = Math.max(top.y, Math.min(bottom.y, centerY));

    const yRange = bottom.y - top.y;
    const t = yRange !== 0 ? (apexY - top.y) / yRange : 0;
    const xBase = top.x + (bottom.x - top.x) * t;
    const apexX = xBase + curvature;

    // Draw black crosshair
    ctx.strokeStyle = "#000000";
    ctx.lineWidth = 1 / zoom;

    ctx.beginPath();
    ctx.moveTo(apexX, top.y);
    ctx.lineTo(apexX, bottom.y);
    ctx.stroke();

    ctx.beginPath();
    ctx.moveTo(0, apexY);
    ctx.lineTo(width, apexY);
    ctx.stroke();
  };

  // Convert screen to image coordinates
  const screenToImage = useCallback(
    (screenX: number, screenY: number) => {
      const canvas = canvasRef.current;
      if (!canvas) return { x: 0, y: 0 };

      const rect = canvas.getBoundingClientRect();
      const canvasX = screenX - rect.left;
      const canvasY = screenY - rect.top;

      const imageX = canvasX / zoom;
      const imageY = canvasY / zoom;

      return { x: imageX, y: imageY };
    },
    [zoom]
  );

  // Handle click to place point
  const handleClick = useCallback(
    (e: React.MouseEvent) => {
      const { x, y } = screenToImage(e.clientX, e.clientY);

      // Validate bounds
      if (x < 0 || x > width || y < 0 || y > height) return;

      // Set point based on current phase and step
      if (phase === "alignment") {
        // Alignment mode has 2 clicks
        if (!alignmentPoint) {
          setAlignmentPoint({ x, y });
        } else if (!alignmentEndPoint) {
          setAlignmentEndPoint({ x, y });
        }
      } else if (phase === "horizontal") {
        switch (currentStep) {
          case 1:
            setHorizontalTop({ x, y });
            break;
          case 2:
            setHorizontalEndPoint({ x, y });
            break;
        }
      } else if (phase === "vertical") {
        switch (currentStep) {
          case 4:
            setVerticalLine1Top({ x, y });
            break;
          case 5:
            setVerticalLine1Bottom({ x, y });
            break;
        }
      }
    },
    [
      screenToImage, width, height, phase, currentStep,
      alignmentPoint, alignmentEndPoint,
      setAlignmentPoint, setAlignmentEndPoint,
      setHorizontalTop, setHorizontalEndPoint,
      setVerticalLine1Top, setVerticalLine1Bottom
    ]
  );

  // Ctrl + Mouse wheel for zoom
  const handleWheel = useCallback(
    (e: React.WheelEvent) => {
      if (e.ctrlKey || e.metaKey) {
        e.preventDefault();
        const { setZoom } = useCalibrationStore.getState();
        const delta = e.deltaY > 0 ? -0.1 : 0.1;
        setZoom(zoom + delta);
      }
    },
    [zoom]
  );

  // Cursor style
  const getCursor = () => {
    // Alignment mode always needs crosshair
    if (phase === "alignment") return "crosshair";
    // Slider steps: 3 (horizontal spacing), 6 (curvature), 7 (vertical spacing)
    if (currentStep === 3 || currentStep === 6 || currentStep === 7) return "default";
    return "crosshair";
  };

  return (
    <div
      ref={containerRef}
      className="calibration-canvas-wrapper"
      style={{ cursor: getCursor() }}
    >
      <canvas
        ref={canvasRef}
        width={canvasWidth}
        height={canvasHeight}
        onClick={handleClick}
        onWheel={handleWheel}
      />
    </div>
  );
}

export default CalibrationCanvas;
