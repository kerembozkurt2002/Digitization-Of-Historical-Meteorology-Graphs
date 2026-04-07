/**
 * CurveBoundsModal — full-screen modal for manual left/right curve-bound selection.
 *
 * Shows the original image on a canvas, lets the user click two points
 * (left bound, right bound) visualised as cyan vertical dashed lines,
 * then applies them to trigger curve extraction.
 */

import { useCallback, useEffect, useRef, useState } from "react";
import { useImageStore } from "../../stores/imageStore";
import { useCurveStore } from "../../stores/curveStore";
import "./CurveBoundsModal.css";

type Phase = "left" | "right" | "done";

export function CurveBoundsModal() {
  const { isBoundsModalOpen, closeBoundsModal, setBounds, xMin, xMax } =
    useCurveStore();
  const { originalImage, imageWidth, imageHeight } = useImageStore();

  const canvasRef = useRef<HTMLCanvasElement>(null);
  const containerRef = useRef<HTMLDivElement>(null);
  const imgRef = useRef<HTMLImageElement | null>(null);

  const [zoom, setZoom] = useState(1);
  const [phase, setPhase] = useState<Phase>("left");
  const [leftX, setLeftX] = useState<number | null>(null);
  const [rightX, setRightX] = useState<number | null>(null);
  const [hoverX, setHoverX] = useState<number | null>(null);

  // Reset state whenever modal opens
  useEffect(() => {
    if (isBoundsModalOpen) {
      setPhase(xMin !== null && xMax !== null ? "done" : "left");
      setLeftX(xMin);
      setRightX(xMax);
      setZoom(1);
      setHoverX(null);
    }
  }, [isBoundsModalOpen, xMin, xMax]);

  // Load image into an offscreen HTMLImageElement for drawing
  useEffect(() => {
    if (!originalImage) return;
    const img = new Image();
    img.onload = () => {
      imgRef.current = img;
      drawCanvas();
    };
    img.src = `data:image/png;base64,${originalImage}`;
  }, [originalImage]); // eslint-disable-line react-hooks/exhaustive-deps

  // Fit zoom so the image fits inside the container on first open
  useEffect(() => {
    if (!isBoundsModalOpen || !containerRef.current || !imageWidth || !imageHeight) return;
    const rect = containerRef.current.getBoundingClientRect();
    const fitZoom = Math.min(rect.width / imageWidth, rect.height / imageHeight, 1);
    setZoom(fitZoom);
  }, [isBoundsModalOpen, imageWidth, imageHeight]);

  const drawCanvas = useCallback(() => {
    const canvas = canvasRef.current;
    const img = imgRef.current;
    if (!canvas || !img || !imageWidth || !imageHeight) return;

    const w = imageWidth * zoom;
    const h = imageHeight * zoom;
    canvas.width = w;
    canvas.height = h;

    const ctx = canvas.getContext("2d");
    if (!ctx) return;

    ctx.drawImage(img, 0, 0, w, h);

    const drawVerticalLine = (natX: number, color: string, lineWidth: number) => {
      const sx = natX * zoom;
      ctx.save();
      ctx.setLineDash([8, 6]);
      ctx.strokeStyle = color;
      ctx.lineWidth = lineWidth;
      ctx.beginPath();
      ctx.moveTo(sx, 0);
      ctx.lineTo(sx, h);
      ctx.stroke();
      ctx.restore();
    };

    // Shade outside the selected region
    if (leftX !== null && rightX !== null) {
      ctx.fillStyle = "rgba(0, 0, 0, 0.45)";
      const lx = leftX * zoom;
      const rx = rightX * zoom;
      ctx.fillRect(0, 0, lx, h);
      ctx.fillRect(rx, 0, w - rx, h);
    }

    if (leftX !== null) drawVerticalLine(leftX, "#00e5ff", 2);
    if (rightX !== null) drawVerticalLine(rightX, "#00e5ff", 2);

    // Hover preview line
    if (hoverX !== null && phase !== "done") {
      drawVerticalLine(hoverX, "rgba(0, 229, 255, 0.5)", 1);
    }

    // Labels
    const drawLabel = (natX: number, label: string) => {
      const sx = natX * zoom;
      ctx.font = "bold 13px sans-serif";
      ctx.fillStyle = "rgba(0,0,0,0.65)";
      const m = ctx.measureText(label);
      ctx.fillRect(sx + 6, 10, m.width + 8, 20);
      ctx.fillStyle = "#00e5ff";
      ctx.fillText(label, sx + 10, 25);
    };

    if (leftX !== null) drawLabel(leftX, `L: ${Math.round(leftX)}`);
    if (rightX !== null) drawLabel(rightX, `R: ${Math.round(rightX)}`);
  }, [imageWidth, imageHeight, zoom, leftX, rightX, hoverX, phase]);

  // Redraw whenever anything relevant changes
  useEffect(() => {
    if (isBoundsModalOpen) drawCanvas();
  }, [drawCanvas, isBoundsModalOpen]);

  const canvasToNatural = useCallback(
    (clientX: number, clientY: number): { nx: number; ny: number } => {
      const canvas = canvasRef.current;
      if (!canvas) return { nx: 0, ny: 0 };
      const rect = canvas.getBoundingClientRect();
      const scaleX = canvas.width / rect.width;
      const scaleY = canvas.height / rect.height;
      return {
        nx: ((clientX - rect.left) * scaleX) / zoom,
        ny: ((clientY - rect.top) * scaleY) / zoom,
      };
    },
    [zoom]
  );

  const handleCanvasClick = useCallback(
    (e: React.MouseEvent) => {
      const { nx } = canvasToNatural(e.clientX, e.clientY);

      if (phase === "left") {
        setLeftX(nx);
        setPhase("right");
      } else if (phase === "right") {
        setRightX(nx);
        setPhase("done");
      }
    },
    [phase, canvasToNatural]
  );

  const handleCanvasMove = useCallback(
    (e: React.MouseEvent) => {
      if (phase === "done") {
        setHoverX(null);
        return;
      }
      const { nx } = canvasToNatural(e.clientX, e.clientY);
      setHoverX(nx);
    },
    [phase, canvasToNatural]
  );

  const handleApply = useCallback(() => {
    if (leftX !== null && rightX !== null) {
      setBounds(leftX, rightX);
      closeBoundsModal();
    }
  }, [leftX, rightX, setBounds, closeBoundsModal]);

  const handleReset = useCallback(() => {
    setLeftX(null);
    setRightX(null);
    setPhase("left");
    setHoverX(null);
  }, []);

  const zoomIn = useCallback(() => setZoom((z) => Math.min(5, z + 0.25)), []);
  const zoomOut = useCallback(() => setZoom((z) => Math.max(0.1, z - 0.25)), []);
  const zoomReset = useCallback(() => setZoom(1), []);

  // Keyboard: Escape to close
  useEffect(() => {
    if (!isBoundsModalOpen) return;
    const handleKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") closeBoundsModal();
    };
    window.addEventListener("keydown", handleKey);
    return () => window.removeEventListener("keydown", handleKey);
  }, [isBoundsModalOpen, closeBoundsModal]);

  if (!isBoundsModalOpen || !originalImage) return null;

  const stepText =
    phase === "left"
      ? "Click to set the LEFT bound"
      : phase === "right"
        ? "Click to set the RIGHT bound"
        : "Bounds set — click Apply & Extract";

  return (
    <div className="curve-bounds-overlay">
      <div className="curve-bounds-modal">
        {/* Header */}
        <div className="curve-bounds-header">
          <h2>Set Curve Bounds</h2>
          <button className="close-btn" onClick={closeBoundsModal}>
            &times;
          </button>
        </div>

        {/* Instructions */}
        <div className="curve-bounds-instructions">
          <div className="step-info">
            <span className="step-number">
              {phase === "done" ? "\u2713" : phase === "left" ? "1/2" : "2/2"}
            </span>
            <span className={phase === "done" ? "step-complete" : "step-text"}>
              {stepText}
            </span>
          </div>
          {phase !== "left" && (
            <button className="btn btn-secondary btn-small" onClick={handleReset}>
              Reset
            </button>
          )}
        </div>

        {/* Canvas */}
        <div className="curve-bounds-canvas-container" ref={containerRef}>
          <div className="curve-bounds-canvas-wrapper">
            <canvas
              ref={canvasRef}
              onClick={handleCanvasClick}
              onMouseMove={handleCanvasMove}
              onMouseLeave={() => setHoverX(null)}
            />
          </div>
        </div>

        {/* Footer */}
        <div className="curve-bounds-footer">
          <div className="zoom-controls">
            <button className="btn btn-secondary btn-small" onClick={zoomOut}>
              &minus;
            </button>
            <span className="zoom-level">{Math.round(zoom * 100)}%</span>
            <button className="btn btn-secondary btn-small" onClick={zoomIn}>
              +
            </button>
            <button className="btn btn-secondary btn-small" onClick={zoomReset}>
              Fit
            </button>
          </div>

          <div className="action-buttons">
            <button className="btn btn-secondary" onClick={closeBoundsModal}>
              Cancel
            </button>
            <button
              className="btn btn-primary"
              disabled={phase !== "done"}
              onClick={handleApply}
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
