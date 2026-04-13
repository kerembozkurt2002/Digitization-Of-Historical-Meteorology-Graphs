/**
 * CurveBoundsModal — full-screen modal for selecting curve bound segments.
 *
 * Supports defining multiple start/end point pairs for discontinuous curves.
 * Each pair defines a segment with left (start) and right (end) bounds plus
 * optional Y hints from the click positions.
 */

import { useCallback, useEffect, useRef, useState } from "react";
import { useImageStore } from "../../stores/imageStore";
import { useCurveStore } from "../../stores/curveStore";
import type { CurveBoundSegment } from "../../types";
import "./CurveBoundsModal.css";

type Phase = "left" | "right" | "idle";

const SEGMENT_COLORS = ["#00e5ff", "#ff6ec7", "#aaff00", "#ffaa00", "#aa88ff", "#ff5555"];

export function CurveBoundsModal() {
  const { isBoundsModalOpen, closeBoundsModal, setCurveBounds, curveBounds } =
    useCurveStore();
  const { originalImage, imageWidth, imageHeight } = useImageStore();

  const canvasRef = useRef<HTMLCanvasElement>(null);
  const containerRef = useRef<HTMLDivElement>(null);
  const imgRef = useRef<HTMLImageElement | null>(null);

  const [zoom, setZoom] = useState(1);
  const [phase, setPhase] = useState<Phase>("idle");
  const [segments, setSegments] = useState<CurveBoundSegment[]>([]);
  const [nextId, setNextId] = useState(1);

  // Pending pair being defined
  const [pendingLeftX, setPendingLeftX] = useState<number | null>(null);
  const [pendingLeftY, setPendingLeftY] = useState<number | null>(null);
  const [hoverX, setHoverX] = useState<number | null>(null);

  // Reset state whenever modal opens
  useEffect(() => {
    if (isBoundsModalOpen) {
      const existing = curveBounds.length > 0 ? [...curveBounds] : [];
      setSegments(existing);
      const maxId = existing.length > 0 ? Math.max(...existing.map((s) => s.id)) : 0;
      setNextId(maxId + 1);
      setPhase("idle");
      setPendingLeftX(null);
      setPendingLeftY(null);
      setZoom(1);
      setHoverX(null);
    }
  }, [isBoundsModalOpen, curveBounds]);

  // Load image
  useEffect(() => {
    if (!originalImage) return;
    const img = new Image();
    img.onload = () => {
      imgRef.current = img;
      drawCanvas();
    };
    img.src = `data:image/png;base64,${originalImage}`;
  }, [originalImage]); // eslint-disable-line react-hooks/exhaustive-deps

  // Fit zoom
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

    // Draw completed segments
    for (let si = 0; si < segments.length; si++) {
      const seg = segments[si];
      const color = SEGMENT_COLORS[si % SEGMENT_COLORS.length];
      const lx = seg.xMin * zoom;
      const rx = seg.xMax * zoom;

      // Shaded region
      ctx.fillStyle = color.replace(")", ", 0.08)").replace("rgb", "rgba").replace("#", "");
      // Use a simple highlight band
      ctx.save();
      ctx.globalAlpha = 0.12;
      ctx.fillStyle = color;
      ctx.fillRect(lx, 0, rx - lx, h);
      ctx.globalAlpha = 1.0;
      ctx.restore();

      // Bound lines
      const drawLine = (natX: number) => {
        const sx = natX * zoom;
        ctx.save();
        ctx.setLineDash([8, 6]);
        ctx.strokeStyle = color;
        ctx.lineWidth = 2;
        ctx.beginPath();
        ctx.moveTo(sx, 0);
        ctx.lineTo(sx, h);
        ctx.stroke();
        ctx.restore();
      };
      drawLine(seg.xMin);
      drawLine(seg.xMax);

      // Crosshairs at Y hints
      const drawCrosshair = (natX: number, natY: number) => {
        const cx = natX * zoom;
        const cy = natY * zoom;
        ctx.save();
        ctx.strokeStyle = color;
        ctx.lineWidth = 2;
        ctx.beginPath();
        ctx.arc(cx, cy, 8, 0, Math.PI * 2);
        ctx.stroke();
        ctx.beginPath();
        ctx.moveTo(cx - 12, cy);
        ctx.lineTo(cx + 12, cy);
        ctx.moveTo(cx, cy - 12);
        ctx.lineTo(cx, cy + 12);
        ctx.stroke();
        ctx.restore();
      };
      if (seg.yHint !== undefined) drawCrosshair(seg.xMin, seg.yHint);
      if (seg.yHintEnd !== undefined) drawCrosshair(seg.xMax, seg.yHintEnd);

      // Label
      ctx.font = "bold 12px sans-serif";
      ctx.fillStyle = "rgba(0,0,0,0.7)";
      const label = `Seg ${si + 1}`;
      const m = ctx.measureText(label);
      const labelX = lx + 6;
      ctx.fillRect(labelX, 8, m.width + 8, 20);
      ctx.fillStyle = color;
      ctx.fillText(label, labelX + 4, 23);
    }

    // Pending left line
    if (pendingLeftX !== null) {
      const nextColor = SEGMENT_COLORS[segments.length % SEGMENT_COLORS.length];
      const sx = pendingLeftX * zoom;
      ctx.save();
      ctx.setLineDash([8, 6]);
      ctx.strokeStyle = nextColor;
      ctx.lineWidth = 2;
      ctx.beginPath();
      ctx.moveTo(sx, 0);
      ctx.lineTo(sx, h);
      ctx.stroke();
      ctx.restore();
      if (pendingLeftY !== null) {
        const cy = pendingLeftY * zoom;
        ctx.save();
        ctx.strokeStyle = nextColor;
        ctx.lineWidth = 2;
        ctx.beginPath();
        ctx.arc(sx, cy, 8, 0, Math.PI * 2);
        ctx.stroke();
        ctx.beginPath();
        ctx.moveTo(sx - 12, cy);
        ctx.lineTo(sx + 12, cy);
        ctx.moveTo(sx, cy - 12);
        ctx.lineTo(sx, cy + 12);
        ctx.stroke();
        ctx.restore();
      }
    }

    // Hover preview line
    if (hoverX !== null && phase !== "idle") {
      ctx.save();
      ctx.setLineDash([4, 4]);
      ctx.strokeStyle = "rgba(255, 255, 255, 0.4)";
      ctx.lineWidth = 1;
      ctx.beginPath();
      const sx = hoverX * zoom;
      ctx.moveTo(sx, 0);
      ctx.lineTo(sx, h);
      ctx.stroke();
      ctx.restore();
    }
  }, [imageWidth, imageHeight, zoom, segments, pendingLeftX, pendingLeftY, hoverX, phase]);

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
      const { nx, ny } = canvasToNatural(e.clientX, e.clientY);

      if (phase === "left") {
        setPendingLeftX(nx);
        setPendingLeftY(ny);
        setPhase("right");
      } else if (phase === "right" && pendingLeftX !== null) {
        const newSeg: CurveBoundSegment = {
          id: nextId,
          xMin: Math.min(pendingLeftX, nx),
          xMax: Math.max(pendingLeftX, nx),
          yHint: pendingLeftX < nx ? (pendingLeftY ?? undefined) : ny,
          yHintEnd: pendingLeftX < nx ? ny : (pendingLeftY ?? undefined),
        };
        setSegments((prev) => [...prev, newSeg].sort((a, b) => a.xMin - b.xMin));
        setNextId((id) => id + 1);
        setPendingLeftX(null);
        setPendingLeftY(null);
        setPhase("idle");
      }
    },
    [phase, canvasToNatural, pendingLeftX, pendingLeftY, nextId]
  );

  const handleCanvasMove = useCallback(
    (e: React.MouseEvent) => {
      if (phase === "idle") {
        setHoverX(null);
        return;
      }
      const { nx } = canvasToNatural(e.clientX, e.clientY);
      setHoverX(nx);
    },
    [phase, canvasToNatural]
  );

  const handleStartAdding = useCallback(() => {
    setPhase("left");
    setPendingLeftX(null);
    setPendingLeftY(null);
  }, []);

  const handleRemoveSegment = useCallback((id: number) => {
    setSegments((prev) => prev.filter((s) => s.id !== id));
  }, []);

  const handleClearAll = useCallback(() => {
    setSegments([]);
    setPendingLeftX(null);
    setPendingLeftY(null);
    setPhase("idle");
  }, []);

  const handleCancel = useCallback(() => {
    if (phase !== "idle") {
      setPendingLeftX(null);
      setPendingLeftY(null);
      setPhase("idle");
    }
  }, [phase]);

  const handleApply = useCallback(() => {
    setCurveBounds(segments);
    closeBoundsModal();
  }, [segments, setCurveBounds, closeBoundsModal]);

  const zoomIn = useCallback(() => setZoom((z) => Math.min(5, z + 0.25)), []);
  const zoomOut = useCallback(() => setZoom((z) => Math.max(0.1, z - 0.25)), []);
  const zoomReset = useCallback(() => setZoom(1), []);

  useEffect(() => {
    if (!isBoundsModalOpen) return;
    const handleKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") {
        if (phase !== "idle") {
          setPendingLeftX(null);
          setPendingLeftY(null);
          setPhase("idle");
        } else {
          closeBoundsModal();
        }
      }
    };
    window.addEventListener("keydown", handleKey);
    return () => window.removeEventListener("keydown", handleKey);
  }, [isBoundsModalOpen, closeBoundsModal, phase]);

  if (!isBoundsModalOpen || !originalImage) return null;

  const stepText =
    phase === "left"
      ? "Click to set the START point of a curve segment"
      : phase === "right"
        ? "Click to set the END point of this segment"
        : segments.length === 0
          ? 'Click "Add Segment" to define curve bounds'
          : `${segments.length} segment(s) defined — add more or Apply`;

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

        {/* Instructions + segment list */}
        <div className="curve-bounds-instructions">
          <div className="step-info">
            <span className="step-number">
              {phase === "left" ? "1/2" : phase === "right" ? "2/2" : segments.length > 0 ? "\u2713" : ""}
            </span>
            <span className={segments.length > 0 && phase === "idle" ? "step-complete" : "step-text"}>
              {stepText}
            </span>
          </div>
          <div className="bounds-toolbar">
            {phase === "idle" && (
              <button className="btn btn-secondary btn-small" onClick={handleStartAdding}>
                + Add Segment
              </button>
            )}
            {phase !== "idle" && (
              <button className="btn btn-secondary btn-small" onClick={handleCancel}>
                Cancel
              </button>
            )}
            {segments.length > 0 && phase === "idle" && (
              <button className="btn btn-secondary btn-small" onClick={handleClearAll}>
                Clear All
              </button>
            )}
          </div>
        </div>

        {/* Segment list */}
        {segments.length > 0 && (
          <div className="curve-bounds-segments">
            {segments.map((seg, si) => (
              <div key={seg.id} className="segment-chip" style={{ borderColor: SEGMENT_COLORS[si % SEGMENT_COLORS.length] }}>
                <span className="segment-chip-label" style={{ color: SEGMENT_COLORS[si % SEGMENT_COLORS.length] }}>
                  Seg {si + 1}
                </span>
                <span className="segment-chip-range">
                  {Math.round(seg.xMin)} — {Math.round(seg.xMax)} px
                </span>
                <button
                  className="segment-chip-remove"
                  onClick={() => handleRemoveSegment(seg.id)}
                  title="Remove this segment"
                >
                  &times;
                </button>
              </div>
            ))}
          </div>
        )}

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
              disabled={segments.length === 0}
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
