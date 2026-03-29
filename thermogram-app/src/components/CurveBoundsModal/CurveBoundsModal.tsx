/**
 * CurveBoundsModal - Full-screen modal for selecting curve left/right X bounds.
 *
 * Shows the clean thermogram image (no curve overlay) with zoom support.
 * User clicks two points to define the horizontal extent of the curve.
 * Step 1: Click left bound
 * Step 2: Click right bound
 * Then "Apply & Extract" to close and run extraction.
 */

import { useCallback, useEffect, useRef, useState } from "react";
import { useImageStore } from "../../stores/imageStore";
import { useCurveStore } from "../../stores/curveStore";
import "./CurveBoundsModal.css";

export function CurveBoundsModal() {
  const {
    isBoundsModalOpen,
    closeBoundsModal,
    setBounds,
    xMin: savedXMin,
    xMax: savedXMax,
  } = useCurveStore();

  const { originalImage, imageWidth, imageHeight } = useImageStore();

  const canvasRef = useRef<HTMLCanvasElement>(null);
  const imageRef = useRef<HTMLImageElement | null>(null);

  const [zoom, setZoom] = useState(1.0);
  const [leftX, setLeftX] = useState<number | null>(null);
  const [rightX, setRightX] = useState<number | null>(null);
  const [hoverX, setHoverX] = useState<number | null>(null);

  const step = leftX === null ? 1 : rightX === null ? 2 : 3;

  // Initialise from saved bounds when opening
  useEffect(() => {
    if (isBoundsModalOpen) {
      setLeftX(savedXMin);
      setRightX(savedXMax);
      setHoverX(null);
    }
  }, [isBoundsModalOpen, savedXMin, savedXMax]);

  const canvasWidth = imageWidth * zoom;
  const canvasHeight = imageHeight * zoom;

  // Load image
  useEffect(() => {
    if (!originalImage) return;
    const img = new Image();
    img.onload = () => {
      imageRef.current = img;
      draw();
    };
    img.src = `data:image/png;base64,${originalImage}`;
  }, [originalImage]);

  const draw = useCallback(() => {
    const canvas = canvasRef.current;
    const ctx = canvas?.getContext("2d");
    const img = imageRef.current;
    if (!canvas || !ctx || !img) return;

    ctx.clearRect(0, 0, canvas.width, canvas.height);
    ctx.save();
    ctx.scale(zoom, zoom);
    ctx.drawImage(img, 0, 0);
    ctx.restore();

    // Draw bound lines
    const drawVertLine = (naturalX: number, color: string, label: string) => {
      const sx = naturalX * zoom;
      ctx.save();
      ctx.setLineDash([6, 4]);
      ctx.strokeStyle = color;
      ctx.lineWidth = 2;
      ctx.beginPath();
      ctx.moveTo(sx, 0);
      ctx.lineTo(sx, canvasHeight);
      ctx.stroke();
      ctx.setLineDash([]);

      ctx.font = "bold 14px sans-serif";
      ctx.fillStyle = "rgba(0,0,0,0.6)";
      const tw = ctx.measureText(label).width;
      ctx.fillRect(sx + 4, 8, tw + 10, 24);
      ctx.fillStyle = color;
      ctx.fillText(label, sx + 9, 26);
      ctx.restore();
    };

    if (leftX !== null) drawVertLine(leftX, "#00ccff", "L");
    if (rightX !== null) drawVertLine(rightX, "#00ccff", "R");

    // Shaded region between bounds
    if (leftX !== null && rightX !== null) {
      const l = Math.min(leftX, rightX) * zoom;
      const r = Math.max(leftX, rightX) * zoom;

      ctx.save();
      // Dim outside the bounds
      ctx.fillStyle = "rgba(0,0,0,0.35)";
      ctx.fillRect(0, 0, l, canvasHeight);
      ctx.fillRect(r, 0, canvasWidth - r, canvasHeight);
      ctx.restore();
    }

    // Hover crosshair
    if (hoverX !== null && step < 3) {
      const sx = hoverX * zoom;
      ctx.save();
      ctx.setLineDash([4, 4]);
      ctx.strokeStyle = "rgba(255,255,255,0.5)";
      ctx.lineWidth = 1;
      ctx.beginPath();
      ctx.moveTo(sx, 0);
      ctx.lineTo(sx, canvasHeight);
      ctx.stroke();
      ctx.setLineDash([]);
      ctx.restore();
    }
  }, [zoom, leftX, rightX, hoverX, step, canvasWidth, canvasHeight]);

  // Redraw on state changes
  useEffect(() => {
    draw();
  }, [draw]);

  const screenToImage = useCallback(
    (clientX: number, clientY: number) => {
      const canvas = canvasRef.current;
      if (!canvas) return { x: 0, y: 0 };
      const rect = canvas.getBoundingClientRect();
      return {
        x: (clientX - rect.left) / zoom,
        y: (clientY - rect.top) / zoom,
      };
    },
    [zoom]
  );

  const handleClick = useCallback(
    (e: React.MouseEvent) => {
      const { x } = screenToImage(e.clientX, e.clientY);
      if (x < 0 || x > imageWidth) return;

      if (step === 1) {
        setLeftX(x);
      } else if (step === 2) {
        setRightX(x);
      }
    },
    [screenToImage, imageWidth, step]
  );

  const handleMouseMove = useCallback(
    (e: React.MouseEvent) => {
      const { x } = screenToImage(e.clientX, e.clientY);
      setHoverX(Math.max(0, Math.min(imageWidth, x)));
    },
    [screenToImage, imageWidth]
  );

  const handleMouseLeave = useCallback(() => {
    setHoverX(null);
  }, []);

  const handleApply = useCallback(() => {
    if (leftX !== null && rightX !== null) {
      setBounds(leftX, rightX);
    }
  }, [leftX, rightX, setBounds]);

  const handleBack = useCallback(() => {
    if (rightX !== null) {
      setRightX(null);
    } else if (leftX !== null) {
      setLeftX(null);
    }
  }, [leftX, rightX]);

  const handleClearAndClose = useCallback(() => {
    closeBoundsModal();
  }, [closeBoundsModal]);

  const handleWheel = useCallback(
    (e: React.WheelEvent) => {
      if (e.ctrlKey || e.metaKey) {
        e.preventDefault();
        const delta = e.deltaY > 0 ? -0.1 : 0.1;
        setZoom((z) => Math.max(0.3, Math.min(3.0, z + delta)));
      }
    },
    []
  );

  // Keyboard shortcuts
  useEffect(() => {
    if (!isBoundsModalOpen) return;
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === "Escape") {
        closeBoundsModal();
      } else if (e.key === "Enter" && leftX !== null && rightX !== null) {
        handleApply();
      } else if (e.key === "+" || e.key === "=") {
        setZoom((z) => Math.min(3.0, z + 0.25));
      } else if (e.key === "-") {
        setZoom((z) => Math.max(0.3, z - 0.25));
      }
    };
    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [isBoundsModalOpen, closeBoundsModal, handleApply, leftX, rightX]);

  if (!isBoundsModalOpen || !originalImage) return null;

  const stepLabel =
    step === 1
      ? "Click the LEFT edge of the curve"
      : step === 2
        ? "Click the RIGHT edge of the curve"
        : "Bounds selected - click Apply & Extract";

  return (
    <div className="bounds-modal-overlay">
      <div className="bounds-modal">
        {/* Header */}
        <div className="bounds-header">
          <div className="bounds-title">
            <h2>Set Curve Bounds</h2>
            <span className="bounds-step-badge">
              Step {Math.min(step, 2)} of 2
            </span>
          </div>
          <button className="close-btn" onClick={handleClearAndClose} title="Close (Esc)">
            &times;
          </button>
        </div>

        {/* Progress */}
        <div className="bounds-progress">
          <div className="progress-bar">
            <div
              className="progress-fill"
              style={{ width: `${(Math.min(step, 2) / 2) * 100}%` }}
            />
          </div>
          <span className="progress-text">{stepLabel}</span>
        </div>

        {/* Status */}
        {(leftX !== null || rightX !== null) && (
          <div className="bounds-status-bar">
            {leftX !== null && (
              <span className="bounds-coord">L: {Math.round(leftX)}px</span>
            )}
            {rightX !== null && (
              <span className="bounds-coord">R: {Math.round(rightX)}px</span>
            )}
            {leftX !== null && rightX !== null && (
              <span className="bounds-coord">
                Width: {Math.round(Math.abs(rightX - leftX))}px
              </span>
            )}
          </div>
        )}

        {/* Canvas */}
        <div className="bounds-canvas-container">
          <div className="bounds-canvas-wrapper" style={{ cursor: step < 3 ? "crosshair" : "default" }}>
            <canvas
              ref={canvasRef}
              width={canvasWidth}
              height={canvasHeight}
              onClick={handleClick}
              onMouseMove={handleMouseMove}
              onMouseLeave={handleMouseLeave}
              onWheel={handleWheel}
            />
          </div>
        </div>

        {/* Footer */}
        <div className="bounds-footer">
          <div className="zoom-controls">
            <button
              className="btn btn-small"
              onClick={() => setZoom((z) => Math.max(0.3, z - 0.25))}
              disabled={zoom <= 0.3}
            >
              &minus;
            </button>
            <span className="zoom-level">{Math.round(zoom * 100)}%</span>
            <button
              className="btn btn-small"
              onClick={() => setZoom((z) => Math.min(3.0, z + 0.25))}
              disabled={zoom >= 3.0}
            >
              +
            </button>
          </div>

          <div className="action-buttons">
            <button className="btn btn-secondary" onClick={handleBack} disabled={leftX === null}>
              Back
            </button>
            <button className="btn btn-secondary" onClick={handleClearAndClose}>
              Cancel
            </button>
            <button
              className="btn btn-primary"
              onClick={handleApply}
              disabled={leftX === null || rightX === null}
            >
              Apply &amp; Extract
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}

export default CurveBoundsModal;
