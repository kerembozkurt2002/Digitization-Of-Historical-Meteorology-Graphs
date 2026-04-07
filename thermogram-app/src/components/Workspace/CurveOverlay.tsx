/**
 * CurveOverlay - Canvas overlay for displaying and editing the extracted curve.
 *
 * Renders the curve as a polyline with draggable control points.
 * Sits on top of the thermogram image (and optionally the grid overlay).
 *
 * Features:
 * - Single point drag (Y-axis only)
 * - Multi-select with Ctrl/Cmd + drag to draw selection box
 * - Multi-point drag (Y-axis only, all selected points move together)
 * - Delete selected points with Delete/Backspace key
 */

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useImageStore } from "../../stores/imageStore";
import { useCurveStore } from "../../stores/curveStore";
import type { CurvePoint } from "../../types";
import {
  canvasToNatural,
  getContainedImageLayout,
  naturalToCanvas,
} from "../../utils/imageDisplayLayout";

interface CurveOverlayProps {
  width: number;
  height: number;
}

interface SelectionBox {
  startX: number;
  startY: number;
  endX: number;
  endY: number;
}

const POINT_RADIUS = 3;
const POINT_HOVER_RADIUS = 5;
const POINT_HIT_RADIUS = 10;
const SPARSE_DOT_INTERVAL = 10;
const INFLUENCE_SIGMA = 5;
const CURVE_COLOR = "#ff2222";
const CURVE_EDITED_COLOR = "#ff8800";
const POINT_COLOR = "rgba(255,68,68,0.45)";
const POINT_HOVER_COLOR = "#ffaa00";
const POINT_SELECTED_COLOR = "#00ffaa";
const POINT_MULTI_SELECTED_COLOR = "#00aaff";
const POINT_DRAG_COLOR = "#ffffff";
const SELECTION_BOX_COLOR = "rgba(0, 170, 255, 0.3)";
const SELECTION_BOX_BORDER = "rgba(0, 170, 255, 0.8)";

export function CurveOverlay({ width, height }: CurveOverlayProps) {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const { imageWidth, imageHeight } = useImageStore();
  const {
    points,
    rawPoints,
    showCurve,
    selectedPointIndex,
    selectedPointIndices,
    dragPointIndex,
    xMin,
    xMax,
    setSelectedPointIndex,
    setSelectedPointIndices,
    setDragPointIndex,
  } = useCurveStore();

  const [hoveredIndex, setHoveredIndex] = useState<number | null>(null);
  const [selectionBox, setSelectionBox] = useState<SelectionBox | null>(null);
  const [isMultiDragging, setIsMultiDragging] = useState(false);
  const [multiDragStartY, setMultiDragStartY] = useState<number | null>(null);
  const [multiDragLastY, setMultiDragLastY] = useState<number | null>(null);

  // Snapshot of points at drag start — Gaussian influence is applied from this
  // baseline so that repeated mouse-move events don't compound.
  const dragStartPointsRef = useRef<CurvePoint[] | null>(null);

  const applyGaussianInfluence = useCallback(
    (pts: CurvePoint[], centerIdx: number, deltaY: number): CurvePoint[] => {
      const result = [...pts];
      const radius = Math.ceil(INFLUENCE_SIGMA * 3);
      for (let d = -radius; d <= radius; d++) {
        const j = centerIdx + d;
        if (j < 0 || j >= result.length) continue;
        const weight = Math.exp(-(d * d) / (2 * INFLUENCE_SIGMA * INFLUENCE_SIGMA));
        const newY = Math.max(0, Math.min(imageHeight, result[j].y + deltaY * weight));
        result[j] = { x: result[j].x, y: newY };
      }
      return result;
    },
    [imageHeight]
  );

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

  // Draw curve, control points, selection box, and bound lines
  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext("2d");
    if (!ctx) return;

    ctx.clearRect(0, 0, width, height);

    // Draw selection box if active
    if (selectionBox) {
      const { startX, startY, endX, endY } = selectionBox;
      const x = Math.min(startX, endX);
      const y = Math.min(startY, endY);
      const w = Math.abs(endX - startX);
      const h = Math.abs(endY - startY);

      ctx.fillStyle = SELECTION_BOX_COLOR;
      ctx.fillRect(x, y, w, h);
      ctx.strokeStyle = SELECTION_BOX_BORDER;
      ctx.lineWidth = 1;
      ctx.strokeRect(x, y, w, h);
    }

    if (!showCurve || points.length < 2) return;

    const isEdited =
      rawPoints.length !== points.length ||
      points.some((p, i) => {
        const r = rawPoints[i];
        return !r || Math.abs(p.x - r.x) > 0.01 || Math.abs(p.y - r.y) > 0.01;
      });

    // Draw vertical bound lines if set
    if (xMin !== null && xMax !== null) {
      const drawBoundLine = (natX: number) => {
        const { sx } = toScreen(natX, 0);
        ctx.save();
        ctx.setLineDash([6, 4]);
        ctx.strokeStyle = "rgba(0, 229, 255, 0.55)";
        ctx.lineWidth = 1.5;
        ctx.beginPath();
        ctx.moveTo(sx, 0);
        ctx.lineTo(sx, height);
        ctx.stroke();
        ctx.restore();
      };
      drawBoundLine(xMin);
      drawBoundLine(xMax);
    }

    ctx.lineJoin = "round";
    ctx.lineCap = "round";
    const drawStroke = (lineWidth: number, strokeStyle: string, shadow?: boolean) => {
      ctx.beginPath();
      if (shadow) {
        ctx.shadowColor = strokeStyle;
        ctx.shadowBlur = 6;
      }
      ctx.strokeStyle = strokeStyle;
      ctx.lineWidth = lineWidth;
      for (let i = 0; i < points.length; i++) {
        const { sx, sy } = toScreen(points[i].x, points[i].y);
        if (i === 0) ctx.moveTo(sx, sy);
        else ctx.lineTo(sx, sy);
      }
      ctx.stroke();
      ctx.shadowColor = "transparent";
      ctx.shadowBlur = 0;
    };
    // Glow layer
    drawStroke(4, "rgba(255,34,34,0.25)", true);
    // Shadow outline
    drawStroke(2.5, "rgba(0,0,0,0.4)");
    // Main curve
    drawStroke(1.5, isEdited ? CURVE_EDITED_COLOR : CURVE_COLOR);

    for (let i = 0; i < points.length; i++) {
      const isDragging = dragPointIndex === i || (isMultiDragging && selectedPointIndices.includes(i));
      const isSelected = selectedPointIndex === i;
      const isMultiSelected = selectedPointIndices.includes(i);
      const isHovered = hoveredIndex === i;
      const isSparse = i % SPARSE_DOT_INTERVAL === 0;

      if (!isDragging && !isSelected && !isMultiSelected && !isHovered && !isSparse) continue;

      const { sx, sy } = toScreen(points[i].x, points[i].y);

      let color: string;
      let radius: number;

      if (isDragging) {
        color = POINT_DRAG_COLOR;
        radius = POINT_HOVER_RADIUS;
      } else if (isSelected) {
        color = POINT_SELECTED_COLOR;
        radius = POINT_HOVER_RADIUS;
      } else if (isMultiSelected) {
        color = POINT_MULTI_SELECTED_COLOR;
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

    // Draw tooltip for hovered point
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

    // Draw multi-selection count indicator
    if (selectedPointIndices.length > 0 && !selectionBox) {
      const label = `${selectedPointIndices.length} points selected`;
      ctx.font = "bold 12px sans-serif";
      ctx.fillStyle = "rgba(0, 0, 0, 0.7)";
      const metrics = ctx.measureText(label);
      const tw = metrics.width + 12;
      const th = 22;
      ctx.fillRect(8, 8, tw, th);
      ctx.fillStyle = POINT_MULTI_SELECTED_COLOR;
      ctx.fillText(label, 14, 23);
    }
  }, [
    width, height, points, rawPoints, showCurve,
    selectedPointIndex, selectedPointIndices, dragPointIndex,
    hoveredIndex, toScreen, selectionBox, isMultiDragging, xMin, xMax,
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

  const findPointsInBox = useCallback(
    (box: SelectionBox): number[] => {
      const { startX, startY, endX, endY } = box;
      const minX = Math.min(startX, endX);
      const maxX = Math.max(startX, endX);
      const minY = Math.min(startY, endY);
      const maxY = Math.max(startY, endY);

      const indices: number[] = [];
      for (let i = 0; i < points.length; i++) {
        const { sx, sy } = toScreen(points[i].x, points[i].y);
        if (sx >= minX && sx <= maxX && sy >= minY && sy <= maxY) {
          indices.push(i);
        }
      }
      return indices;
    },
    [points, toScreen]
  );

  const getCanvasPos = useCallback(
    (e: React.MouseEvent) => {
      const canvas = canvasRef.current;
      if (!canvas) return { sx: 0, sy: 0 };
      const rect = canvas.getBoundingClientRect();
      // Scale mouse position if canvas CSS size differs from pixel size
      const scaleX = canvas.width / rect.width;
      const scaleY = canvas.height / rect.height;
      return {
        sx: (e.clientX - rect.left) * scaleX,
        sy: (e.clientY - rect.top) * scaleY
      };
    },
    []
  );

  const handleMouseDown = useCallback(
    (e: React.MouseEvent) => {
      if (e.button !== 0) return;
      const { sx, sy } = getCanvasPos(e);
      const isModifierPressed = e.ctrlKey || e.metaKey;

      if (isModifierPressed) {
        // Start selection box
        e.stopPropagation();
        setSelectionBox({ startX: sx, startY: sy, endX: sx, endY: sy });
        setSelectedPointIndices([]);
        setSelectedPointIndex(null);
      } else if (selectedPointIndices.length > 0) {
        // Check if clicking on a multi-selected point to start multi-drag
        const idx = findNearestPoint(sx, sy);
        if (idx !== null && selectedPointIndices.includes(idx)) {
          e.stopPropagation();
          setIsMultiDragging(true);
          const { ny } = toImage(sx, sy);
          setMultiDragStartY(ny);
          setMultiDragLastY(ny);
        } else {
          // Clicking elsewhere clears multi-selection
          setSelectedPointIndices([]);
          if (idx !== null) {
            e.stopPropagation();
            dragStartPointsRef.current = [...useCurveStore.getState().points];
            setDragPointIndex(idx);
            setSelectedPointIndex(idx);
          } else {
            setSelectedPointIndex(null);
          }
        }
      } else {
        // Normal single point drag
        const idx = findNearestPoint(sx, sy);
        if (idx !== null) {
          e.stopPropagation();
          dragStartPointsRef.current = [...useCurveStore.getState().points];
          setDragPointIndex(idx);
          setSelectedPointIndex(idx);
        } else {
          setSelectedPointIndex(null);
        }
      }
    },
    [getCanvasPos, findNearestPoint, setDragPointIndex, setSelectedPointIndex,
     setSelectedPointIndices, selectedPointIndices, toImage, points]
  );

  const handleMouseMove = useCallback(
    (e: React.MouseEvent) => {
      const { sx, sy } = getCanvasPos(e);

      if (selectionBox) {
        // Update selection box
        e.stopPropagation();
        setSelectionBox(prev => prev ? { ...prev, endX: sx, endY: sy } : null);
      } else if (isMultiDragging && multiDragLastY !== null) {
        // Multi-point drag — uniform shift for all selected points
        e.stopPropagation();
        const { ny: currentY } = toImage(sx, sy);
        const deltaY = currentY - multiDragLastY;

        const curveStore = useCurveStore.getState();
        const newPoints = [...curveStore.points];
        for (const idx of selectedPointIndices) {
          if (idx >= 0 && idx < newPoints.length) {
            const newY = Math.max(0, Math.min(imageHeight, newPoints[idx].y + deltaY));
            newPoints[idx] = { x: newPoints[idx].x, y: newY };
          }
        }
        useCurveStore.setState({ points: newPoints });
        setMultiDragLastY(currentY);
      } else if (dragPointIndex !== null) {
        // Single point drag with Gaussian influence on neighbors
        e.stopPropagation();
        let { ny: iy } = toImage(sx, sy);
        iy = Math.max(0, Math.min(imageHeight, iy));
        const origPts = dragStartPointsRef.current;
        if (origPts) {
          const deltaY = iy - origPts[dragPointIndex].y;
          const newPoints = applyGaussianInfluence(origPts, dragPointIndex, deltaY);
          useCurveStore.setState({ points: newPoints });
        }
      } else {
        const idx = findNearestPoint(sx, sy);
        setHoveredIndex(idx);
      }
    },
    [getCanvasPos, selectionBox, isMultiDragging, multiDragLastY, dragPointIndex,
     toImage, imageHeight, findNearestPoint, selectedPointIndices, applyGaussianInfluence]
  );

  const handleMouseUp = useCallback(
    (e: React.MouseEvent) => {
      const { sx, sy } = getCanvasPos(e);

      if (selectionBox) {
        // Finish selection box
        e.stopPropagation();
        const finalBox = { ...selectionBox, endX: sx, endY: sy };
        const selectedIndices = findPointsInBox(finalBox);
        setSelectedPointIndices(selectedIndices);
        setSelectionBox(null);
      } else if (isMultiDragging && multiDragStartY !== null) {
        // Finish multi-drag - record to history
        e.stopPropagation();

        // The points are already updated in real-time, just push to history
        const curveStore = useCurveStore.getState();
        // Use setPoints to properly record in history
        useCurveStore.getState().setPoints([...curveStore.points]);

        setIsMultiDragging(false);
        setMultiDragStartY(null);
        setMultiDragLastY(null);
      } else if (dragPointIndex !== null) {
        // Finish single point drag — commit Gaussian-influenced result to history
        e.stopPropagation();
        const curveStore = useCurveStore.getState();
        curveStore.setPoints([...curveStore.points]);
        dragStartPointsRef.current = null;
        setDragPointIndex(null);
      }
    },
    [selectionBox, isMultiDragging, multiDragStartY, dragPointIndex, getCanvasPos,
     toImage, imageHeight, setDragPointIndex, findPointsInBox, setSelectedPointIndices]
  );

  const handleMouseLeave = useCallback(() => {
    setHoveredIndex(null);
    if (dragPointIndex !== null) {
      dragStartPointsRef.current = null;
      setDragPointIndex(null);
    }
    if (selectionBox) {
      setSelectionBox(null);
    }
    if (isMultiDragging) {
      setIsMultiDragging(false);
      setMultiDragStartY(null);
      setMultiDragLastY(null);
    }
  }, [dragPointIndex, setDragPointIndex, selectionBox, isMultiDragging]);

  if (!showCurve || points.length === 0 || imageWidth === 0 || imageHeight === 0) {
    return null;
  }

  const getCursor = () => {
    if (selectionBox) return "crosshair";
    if (isMultiDragging || dragPointIndex !== null) return "grabbing";
    if (selectedPointIndices.length > 0 && hoveredIndex !== null && selectedPointIndices.includes(hoveredIndex)) {
      return "grab";
    }
    if (hoveredIndex !== null) return "grab";
    return "default";
  };

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
        cursor: getCursor(),
      }}
      onMouseDown={handleMouseDown}
      onMouseMove={handleMouseMove}
      onMouseUp={handleMouseUp}
      onMouseLeave={handleMouseLeave}
    />
  );
}

export default CurveOverlay;
