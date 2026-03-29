/**
 * CurveOverlay - Canvas overlay for displaying and editing the extracted curve.
 *
 * Renders the curve as a polyline with draggable control points.
 * Also draws vertical bound lines if set.
 * Sits on top of the thermogram image (and optionally the grid overlay).
 */

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useImageStore } from "../../stores/imageStore";
import { useCurveStore } from "../../stores/curveStore";
import {
  canvasToNatural,
  getContainedImageLayout,
  naturalToCanvas,
} from "../../utils/imageDisplayLayout";

interface CurveOverlayProps {
  width: number;
  height: number;
}

const POINT_RADIUS = 3;
const POINT_HOVER_RADIUS = 5;
const POINT_HIT_RADIUS = 10;
const SPARSE_DOT_INTERVAL = 20;
const CURVE_COLOR = "#ff2222";
const CURVE_EDITED_COLOR = "#ff8800";
const POINT_COLOR = "rgba(255,68,68,0.45)";
const POINT_HOVER_COLOR = "#ffaa00";
const POINT_SELECTED_COLOR = "#00ffaa";
const POINT_DRAG_COLOR = "#ffffff";

export function CurveOverlay({ width, height }: CurveOverlayProps) {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const { imageWidth, imageHeight } = useImageStore();
  const {
    points,
    rawPoints,
    showCurve,
    selectedPointIndex,
    dragPointIndex,
    updatePoint,
    setSelectedPointIndex,
    setDragPointIndex,
    xMin,
    xMax,
  } = useCurveStore();

  const [hoveredIndex, setHoveredIndex] = useState<number | null>(null);

  const layout = useMemo(
    () => getContainedImageLayout(width, height, imageWidth, imageHeight),
    [width, height, imageWidth, imageHeight]
  );

  const toScreen = useCallback(
    (px: number, py: number) => naturalToCanvas(px, py, layout),
    [layout]
  );

  const toImage = useCallback(
    (sx: number, sy: number) => canvasToNatural(sx, sy, layout),
    [layout]
  );

  // Draw curve, control points, and bound lines
  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext("2d");
    if (!ctx) return;

    ctx.clearRect(0, 0, width, height);

    // Draw vertical bound lines
    const drawBoundLine = (naturalX: number, color: string, label: string) => {
      const { sx: sx0 } = toScreen(naturalX, 0);
      ctx.save();
      ctx.setLineDash([6, 4]);
      ctx.strokeStyle = color;
      ctx.lineWidth = 2;
      ctx.beginPath();
      ctx.moveTo(sx0, 0);
      ctx.lineTo(sx0, height);
      ctx.stroke();
      ctx.setLineDash([]);
      ctx.font = "bold 12px sans-serif";
      ctx.fillStyle = color;
      ctx.fillText(label, sx0 + 4, 18);
      ctx.restore();
    };

    if (xMin !== null) drawBoundLine(xMin, "#00ccff", "L");
    if (xMax !== null) drawBoundLine(xMax, "#00ccff", "R");

    if (!showCurve || points.length < 2) return;

    const isEdited =
      rawPoints.length !== points.length ||
      points.some((p, i) => {
        const r = rawPoints[i];
        return !r || Math.abs(p.x - r.x) > 0.01 || Math.abs(p.y - r.y) > 0.01;
      });

    ctx.lineJoin = "round";
    ctx.lineCap = "round";
    const drawStroke = (lineWidth: number, strokeStyle: string) => {
      ctx.beginPath();
      ctx.strokeStyle = strokeStyle;
      ctx.lineWidth = lineWidth;
      for (let i = 0; i < points.length; i++) {
        const { sx, sy } = toScreen(points[i].x, points[i].y);
        if (i === 0) ctx.moveTo(sx, sy);
        else ctx.lineTo(sx, sy);
      }
      ctx.stroke();
    };
    drawStroke(2.5, "rgba(0,0,0,0.4)");
    drawStroke(1.5, isEdited ? CURVE_EDITED_COLOR : CURVE_COLOR);

    for (let i = 0; i < points.length; i++) {
      const isDragging = dragPointIndex === i;
      const isSelected = selectedPointIndex === i;
      const isHovered = hoveredIndex === i;
      const isSparse = i % SPARSE_DOT_INTERVAL === 0;

      if (!isDragging && !isSelected && !isHovered && !isSparse) continue;

      const { sx, sy } = toScreen(points[i].x, points[i].y);

      let color: string;
      let radius: number;

      if (isDragging) {
        color = POINT_DRAG_COLOR;
        radius = POINT_HOVER_RADIUS;
      } else if (isSelected) {
        color = POINT_SELECTED_COLOR;
        radius = POINT_HOVER_RADIUS;
      } else if (isHovered) {
        color = POINT_HOVER_COLOR;
        radius = POINT_HOVER_RADIUS;
      } else {
        color = POINT_COLOR;
        radius = POINT_RADIUS;
      }

      ctx.beginPath();
      ctx.arc(sx, sy, radius + 0.5, 0, Math.PI * 2);
      ctx.fillStyle = "rgba(0,0,0,0.35)";
      ctx.fill();

      ctx.beginPath();
      ctx.arc(sx, sy, radius, 0, Math.PI * 2);
      ctx.fillStyle = color;
      ctx.fill();
    }

    if (hoveredIndex !== null && hoveredIndex < points.length) {
      const pt = points[hoveredIndex];
      const { sx, sy } = toScreen(pt.x, pt.y);
      const label = `(${Math.round(pt.x)}, ${Math.round(pt.y)})`;
      ctx.font = "11px sans-serif";
      ctx.fillStyle = "rgba(0, 0, 0, 0.7)";
      const metrics = ctx.measureText(label);
      const tw = metrics.width + 8;
      const th = 18;
      const tx = Math.min(sx + 10, width - tw - 4);
      const ty = Math.max(sy - 24, 4);
      ctx.fillRect(tx, ty, tw, th);
      ctx.fillStyle = "#ffffff";
      ctx.fillText(label, tx + 4, ty + 13);
    }
  }, [
    width, height, points, rawPoints, showCurve,
    selectedPointIndex, dragPointIndex, hoveredIndex, toScreen,
    xMin, xMax,
  ]);

  const findNearestPoint = useCallback(
    (sx: number, sy: number): number | null => {
      let bestDist = POINT_HIT_RADIUS * POINT_HIT_RADIUS;
      let bestIdx: number | null = null;

      for (let i = 0; i < points.length; i++) {
        const { sx: px, sy: py } = toScreen(points[i].x, points[i].y);
        const dx = sx - px;
        const dy = sy - py;
        const dist = dx * dx + dy * dy;
        if (dist < bestDist) {
          bestDist = dist;
          bestIdx = i;
        }
      }

      return bestIdx;
    },
    [points, toScreen]
  );

  const getCanvasPos = useCallback(
    (e: React.MouseEvent) => {
      const canvas = canvasRef.current;
      if (!canvas) return { sx: 0, sy: 0 };
      const rect = canvas.getBoundingClientRect();
      return { sx: e.clientX - rect.left, sy: e.clientY - rect.top };
    },
    []
  );

  const handleMouseDown = useCallback(
    (e: React.MouseEvent) => {
      if (e.button !== 0) return;
      const { sx, sy } = getCanvasPos(e);
      const idx = findNearestPoint(sx, sy);

      if (idx !== null) {
        e.stopPropagation();
        setDragPointIndex(idx);
        setSelectedPointIndex(idx);
      } else {
        setSelectedPointIndex(null);
      }
    },
    [getCanvasPos, findNearestPoint, setDragPointIndex, setSelectedPointIndex]
  );

  const handleMouseMove = useCallback(
    (e: React.MouseEvent) => {
      const { sx, sy } = getCanvasPos(e);

      if (dragPointIndex !== null) {
        e.stopPropagation();
        let { nx: ix, ny: iy } = toImage(sx, sy);
        ix = Math.max(0, Math.min(imageWidth, ix));
        iy = Math.max(0, Math.min(imageHeight, iy));
        const curveStore = useCurveStore.getState();
        const newPoints = [...curveStore.points];
        newPoints[dragPointIndex] = { x: ix, y: iy };
        useCurveStore.setState({ points: newPoints });
      } else {
        const idx = findNearestPoint(sx, sy);
        setHoveredIndex(idx);
      }
    },
    [getCanvasPos, dragPointIndex, toImage, imageWidth, imageHeight, findNearestPoint]
  );

  const handleMouseUp = useCallback(
    (e: React.MouseEvent) => {
      if (dragPointIndex !== null) {
        e.stopPropagation();
        const { sx, sy } = getCanvasPos(e);
        let { nx: ix, ny: iy } = toImage(sx, sy);
        ix = Math.max(0, Math.min(imageWidth, ix));
        iy = Math.max(0, Math.min(imageHeight, iy));
        updatePoint(dragPointIndex, ix, iy);
        setDragPointIndex(null);
      }
    },
    [dragPointIndex, getCanvasPos, toImage, imageWidth, imageHeight, updatePoint, setDragPointIndex]
  );

  const handleMouseLeave = useCallback(() => {
    setHoveredIndex(null);
    if (dragPointIndex !== null) {
      setDragPointIndex(null);
    }
  }, [dragPointIndex, setDragPointIndex]);

  const hasBounds = xMin !== null || xMax !== null;
  const nothingToRender = !hasBounds && (!showCurve || points.length === 0);
  if (nothingToRender || imageWidth === 0 || imageHeight === 0) {
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
        zIndex: 2,
        pointerEvents: "auto",
        cursor: dragPointIndex !== null ? "grabbing" : hoveredIndex !== null ? "grab" : "default",
      }}
      onMouseDown={handleMouseDown}
      onMouseMove={handleMouseMove}
      onMouseUp={handleMouseUp}
      onMouseLeave={handleMouseLeave}
    />
  );
}

export default CurveOverlay;
