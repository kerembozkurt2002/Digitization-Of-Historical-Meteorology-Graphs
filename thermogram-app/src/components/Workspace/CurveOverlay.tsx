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
 * - Multi-stroke freehand drawing for manual curve annotation
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
const STROKE_COLORS = ["#00ff88", "#00ddff", "#ccff00", "#ff66cc", "#ffaa00", "#aa88ff"];
const DRAWING_GLOW_COLOR = "rgba(0, 255, 136, 0.3)";
const POINT_COLOR = "rgba(255,68,68,0.45)";
const POINT_HOVER_COLOR = "#ffaa00";
const POINT_SELECTED_COLOR = "#00ffaa";
const POINT_MULTI_SELECTED_COLOR = "#00aaff";
const POINT_DRAG_COLOR = "#ffffff";
const SELECTION_BOX_COLOR = "rgba(0, 170, 255, 0.3)";
const SELECTION_BOX_BORDER = "rgba(0, 170, 255, 0.8)";
const REFINE_AREA_COLOR = "rgba(255, 165, 0, 0.15)";
const REFINE_AREA_BORDER = "rgba(255, 165, 0, 0.8)";
const REFINE_PENDING_COLOR = "rgba(255, 165, 0, 0.08)";
const REFINE_PENDING_BORDER = "rgba(255, 165, 0, 0.5)";
const STARTING_POINT_COLOR = "#00e5ff";
const STARTING_POINT_BORDER = "#ffffff";
const ENDING_POINT_COLOR = "#ff6b35";
const ENDING_POINT_BORDER = "#ffffff";

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
    isDrawing,
    drawingStrokes,
    activeStrokeId,
    addDrawingPoint,
    setSelectedPointIndex,
    setSelectedPointIndices,
    setDragPointIndex,
    isRefineSelecting,
    refineXMin,
    refineXMax,
    refineYMin,
    refineYMax,
    setRefineArea,
    // Starting points for curve extraction
    isMarkingStartingPoints,
    startingPoints,
    addStartingPoint,
    awaitingEndPoint,
  } = useCurveStore();

  const [hoveredIndex, setHoveredIndex] = useState<number | null>(null);
  const [selectionBox, setSelectionBox] = useState<SelectionBox | null>(null);
  const [isMultiDragging, setIsMultiDragging] = useState(false);
  const [multiDragStartY, setMultiDragStartY] = useState<number | null>(null);
  const [multiDragLastY, setMultiDragLastY] = useState<number | null>(null);
  const [isFreehandActive, setIsFreehandActive] = useState(false);
  const [refineDragStart, setRefineDragStart] = useState<{ sx: number; sy: number } | null>(null);
  const [refineDragEnd, setRefineDragEnd] = useState<{ sx: number; sy: number } | null>(null);

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

  const hasDrawingContent = drawingStrokes.some((s) => s.points.length > 0);
  const hasExtractedCurve = showCurve && points.length >= 2;

  // Main rendering effect
  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext("2d");
    if (!ctx) return;

    ctx.clearRect(0, 0, width, height);

    // --- Selection box (always drawn) ---
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

    // --- Confirmed refine area (rectangle) ---
    if (refineXMin !== null && refineXMax !== null && refineYMin !== null && refineYMax !== null) {
      const { sx: lx, sy: ty } = toScreen(refineXMin, refineYMin);
      const { sx: rx, sy: by } = toScreen(refineXMax, refineYMax);
      const rw = rx - lx;
      const rh = by - ty;
      ctx.fillStyle = REFINE_AREA_COLOR;
      ctx.fillRect(lx, ty, rw, rh);
      ctx.strokeStyle = REFINE_AREA_BORDER;
      ctx.lineWidth = 2;
      ctx.setLineDash([6, 3]);
      ctx.strokeRect(lx, ty, rw, rh);
      ctx.setLineDash([]);

      ctx.font = "bold 11px sans-serif";
      ctx.fillStyle = "rgba(0,0,0,0.7)";
      const label = "Refine Area";
      const m = ctx.measureText(label);
      ctx.fillRect(lx + 4, ty - 20, m.width + 8, 18);
      ctx.fillStyle = REFINE_AREA_BORDER;
      ctx.fillText(label, lx + 8, ty - 7);
    }

    // --- In-progress refine drag (rectangle) ---
    if (refineDragStart !== null && refineDragEnd !== null) {
      const x1 = Math.min(refineDragStart.sx, refineDragEnd.sx);
      const y1 = Math.min(refineDragStart.sy, refineDragEnd.sy);
      const x2 = Math.max(refineDragStart.sx, refineDragEnd.sx);
      const y2 = Math.max(refineDragStart.sy, refineDragEnd.sy);
      ctx.fillStyle = REFINE_PENDING_COLOR;
      ctx.fillRect(x1, y1, x2 - x1, y2 - y1);
      ctx.strokeStyle = REFINE_PENDING_BORDER;
      ctx.lineWidth = 1.5;
      ctx.setLineDash([4, 3]);
      ctx.strokeRect(x1, y1, x2 - x1, y2 - y1);
      ctx.setLineDash([]);
    }

    // --- Starting points for curve extraction ---
    if (startingPoints.length > 0 || isMarkingStartingPoints) {
      for (let i = 0; i < startingPoints.length; i++) {
        const sp = startingPoints[i];
        const { sx, sy } = toScreen(sp.x, sp.y);
        const hasEndPoint = sp.endX !== undefined && sp.endY !== undefined;

        // Draw starting point crosshair lines
        ctx.strokeStyle = STARTING_POINT_COLOR;
        ctx.lineWidth = 1;
        ctx.setLineDash([3, 3]);
        // Vertical line
        ctx.beginPath();
        ctx.moveTo(sx, 0);
        ctx.lineTo(sx, height);
        ctx.stroke();
        // Horizontal line (short)
        ctx.beginPath();
        ctx.moveTo(sx - 20, sy);
        ctx.lineTo(sx + 20, sy);
        ctx.stroke();
        ctx.setLineDash([]);

        // Draw starting point circle
        ctx.beginPath();
        ctx.arc(sx, sy, 8, 0, Math.PI * 2);
        ctx.fillStyle = STARTING_POINT_COLOR;
        ctx.fill();
        ctx.strokeStyle = STARTING_POINT_BORDER;
        ctx.lineWidth = 2;
        ctx.stroke();

        // Draw number label on starting point
        ctx.font = "bold 10px sans-serif";
        ctx.fillStyle = "#000000";
        ctx.textAlign = "center";
        ctx.textBaseline = "middle";
        ctx.fillText(String(i + 1), sx, sy);
        ctx.textAlign = "start";
        ctx.textBaseline = "alphabetic";

        // Draw "S" label for start
        ctx.font = "bold 9px sans-serif";
        ctx.fillStyle = "rgba(0, 0, 0, 0.7)";
        ctx.fillRect(sx + 10, sy - 18, 14, 14);
        ctx.fillStyle = STARTING_POINT_COLOR;
        ctx.fillText("S", sx + 14, sy - 7);

        // Draw ending point if exists
        if (hasEndPoint) {
          const { sx: ex, sy: ey } = toScreen(sp.endX!, sp.endY!);

          // Draw line connecting start to end
          ctx.strokeStyle = "rgba(255, 107, 53, 0.5)";
          ctx.lineWidth = 2;
          ctx.setLineDash([5, 5]);
          ctx.beginPath();
          ctx.moveTo(sx, sy);
          ctx.lineTo(ex, ey);
          ctx.stroke();
          ctx.setLineDash([]);

          // Draw ending point crosshair
          ctx.strokeStyle = ENDING_POINT_COLOR;
          ctx.lineWidth = 1;
          ctx.setLineDash([3, 3]);
          ctx.beginPath();
          ctx.moveTo(ex, 0);
          ctx.lineTo(ex, height);
          ctx.stroke();
          ctx.beginPath();
          ctx.moveTo(ex - 20, ey);
          ctx.lineTo(ex + 20, ey);
          ctx.stroke();
          ctx.setLineDash([]);

          // Draw ending point circle
          ctx.beginPath();
          ctx.arc(ex, ey, 8, 0, Math.PI * 2);
          ctx.fillStyle = ENDING_POINT_COLOR;
          ctx.fill();
          ctx.strokeStyle = ENDING_POINT_BORDER;
          ctx.lineWidth = 2;
          ctx.stroke();

          // Draw number label on ending point
          ctx.font = "bold 10px sans-serif";
          ctx.fillStyle = "#ffffff";
          ctx.textAlign = "center";
          ctx.textBaseline = "middle";
          ctx.fillText(String(i + 1), ex, ey);
          ctx.textAlign = "start";
          ctx.textBaseline = "alphabetic";

          // Draw "E" label for end
          ctx.font = "bold 9px sans-serif";
          ctx.fillStyle = "rgba(0, 0, 0, 0.7)";
          ctx.fillRect(ex + 10, ey - 18, 14, 14);
          ctx.fillStyle = ENDING_POINT_COLOR;
          ctx.fillText("E", ex + 14, ey - 7);
        }
      }

      // Hint text when in marking mode
      if (isMarkingStartingPoints) {
        ctx.font = "bold 14px sans-serif";
        ctx.fillStyle = "rgba(0, 0, 0, 0.7)";
        let label: string;
        let hintColor: string;
        if (awaitingEndPoint) {
          label = "Click to mark ENDING point";
          hintColor = ENDING_POINT_COLOR;
        } else {
          label = "Click to mark STARTING point";
          hintColor = STARTING_POINT_COLOR;
        }
        const metrics = ctx.measureText(label);
        const tw = metrics.width + 16;
        const th = 26;
        const tx = (width - tw) / 2;
        const ty = 12;
        ctx.fillRect(tx, ty, tw, th);
        ctx.fillStyle = hintColor;
        ctx.fillText(label, tx + 8, ty + 18);
      }
    }

    // --- Drawing strokes (always rendered when they exist) ---
    for (let si = 0; si < drawingStrokes.length; si++) {
      const stroke = drawingStrokes[si];
      if (stroke.points.length < 2) continue;
      const color = STROKE_COLORS[si % STROKE_COLORS.length];
      const isActive = stroke.id === activeStrokeId;

      ctx.beginPath();
      ctx.shadowColor = DRAWING_GLOW_COLOR;
      ctx.shadowBlur = 8;
      ctx.strokeStyle = color;
      ctx.globalAlpha = isActive ? 1.0 : 0.7;
      ctx.lineWidth = 2;
      ctx.lineJoin = "round";
      ctx.lineCap = "round";
      for (let i = 0; i < stroke.points.length; i++) {
        const { sx, sy } = toScreen(stroke.points[i].x, stroke.points[i].y);
        if (i === 0) ctx.moveTo(sx, sy);
        else ctx.lineTo(sx, sy);
      }
      ctx.stroke();
      ctx.shadowColor = "transparent";
      ctx.shadowBlur = 0;
      ctx.globalAlpha = 1.0;

      // Stroke label
      if (stroke.points.length > 0) {
        const firstPt = stroke.points[0];
        const { sx: lx, sy: ly } = toScreen(firstPt.x, firstPt.y);
        ctx.font = "bold 11px sans-serif";
        ctx.fillStyle = "rgba(0,0,0,0.7)";
        const label = stroke.label;
        const m = ctx.measureText(label);
        ctx.fillRect(lx - 2, ly - 16, m.width + 6, 16);
        ctx.fillStyle = color;
        ctx.fillText(label, lx + 1, ly - 3);
      }
    }

    // Drawing mode hint
    if (isDrawing && !hasDrawingContent) {
      ctx.font = "bold 14px sans-serif";
      ctx.fillStyle = "rgba(0, 0, 0, 0.7)";
      const label = "Hold mouse and trace the curve";
      const metrics = ctx.measureText(label);
      const tw = metrics.width + 16;
      const th = 26;
      const tx = (width - tw) / 2;
      const ty = 12;
      ctx.fillRect(tx, ty, tw, th);
      ctx.fillStyle = STROKE_COLORS[0];
      ctx.fillText(label, tx + 8, ty + 18);
    }

    // --- Extracted curve (only when showCurve is true) ---
    if (!hasExtractedCurve) return;

    const isEdited =
      rawPoints.length !== points.length ||
      points.some((p, i) => {
        const r = rawPoints[i];
        return !r || Math.abs(p.x - r.x) > 0.01 || Math.abs(p.y - r.y) > 0.01;
      });

    // Vertical bound lines
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
    const GAP_THRESHOLD = 15;
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
        const isGap = i > 0 && Math.abs(points[i].x - points[i - 1].x) > GAP_THRESHOLD;
        if (i === 0 || isGap) ctx.moveTo(sx, sy);
        else ctx.lineTo(sx, sy);
      }
      ctx.stroke();
      ctx.shadowColor = "transparent";
      ctx.shadowBlur = 0;
    };
    drawStroke(4, "rgba(255,34,34,0.25)", true);
    drawStroke(2.5, "rgba(0,0,0,0.4)");
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

    // Tooltip
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

    // Multi-selection badge
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
    drawingStrokes, activeStrokeId, isDrawing, hasDrawingContent, hasExtractedCurve,
    refineXMin, refineXMax, refineYMin, refineYMax, refineDragStart, refineDragEnd,
    startingPoints, isMarkingStartingPoints, awaitingEndPoint,
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
      const scaleX = canvas.width / rect.width;
      const scaleY = canvas.height / rect.height;
      return {
        sx: (e.clientX - rect.left) * scaleX,
        sy: (e.clientY - rect.top) * scaleY,
      };
    },
    []
  );

  const handleMouseDown = useCallback(
    (e: React.MouseEvent) => {
      if (e.button !== 0) return;
      const { sx, sy } = getCanvasPos(e);

      // Starting point marking mode
      if (isMarkingStartingPoints) {
        e.stopPropagation();
        const { nx, ny } = toImage(sx, sy);
        addStartingPoint(nx, ny);
        return;
      }

      if (isRefineSelecting) {
        e.stopPropagation();
        setRefineDragStart({ sx, sy });
        setRefineDragEnd({ sx, sy });
        return;
      }

      if (isDrawing) {
        e.stopPropagation();
        setIsFreehandActive(true);
        const { nx, ny } = toImage(sx, sy);
        addDrawingPoint({ x: nx, y: ny });
        return;
      }

      const isModifierPressed = e.ctrlKey || e.metaKey;

      if (isModifierPressed) {
        e.stopPropagation();
        setSelectionBox({ startX: sx, startY: sy, endX: sx, endY: sy });
        setSelectedPointIndices([]);
        setSelectedPointIndex(null);
      } else if (selectedPointIndices.length > 0) {
        const idx = findNearestPoint(sx, sy);
        if (idx !== null && selectedPointIndices.includes(idx)) {
          e.stopPropagation();
          setIsMultiDragging(true);
          const { ny } = toImage(sx, sy);
          setMultiDragStartY(ny);
          setMultiDragLastY(ny);
        } else {
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
     setSelectedPointIndices, selectedPointIndices, toImage, points, isDrawing, addDrawingPoint,
     isRefineSelecting, isMarkingStartingPoints, addStartingPoint]
  );

  const handleMouseMove = useCallback(
    (e: React.MouseEvent) => {
      const { sx, sy } = getCanvasPos(e);

      if (refineDragStart !== null) {
        e.stopPropagation();
        setRefineDragEnd({ sx, sy });
        return;
      }

      if (isDrawing && isFreehandActive) {
        e.stopPropagation();
        const { nx, ny } = toImage(sx, sy);
        addDrawingPoint({ x: nx, y: ny });
        return;
      }

      if (selectionBox) {
        e.stopPropagation();
        setSelectionBox((prev) => (prev ? { ...prev, endX: sx, endY: sy } : null));
      } else if (isMultiDragging && multiDragLastY !== null) {
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
     toImage, imageHeight, findNearestPoint, selectedPointIndices, applyGaussianInfluence,
     isDrawing, isFreehandActive, addDrawingPoint, refineDragStart]
  );

  const handleMouseUp = useCallback(
    (e: React.MouseEvent) => {
      if (isFreehandActive) {
        setIsFreehandActive(false);
        return;
      }

      const { sx, sy } = getCanvasPos(e);

      if (refineDragStart !== null) {
        e.stopPropagation();
        const sxMin = Math.min(refineDragStart.sx, sx);
        const sxMax = Math.max(refineDragStart.sx, sx);
        const syMin = Math.min(refineDragStart.sy, sy);
        const syMax = Math.max(refineDragStart.sy, sy);
        const { nx: nx1, ny: ny1 } = toImage(sxMin, syMin);
        const { nx: nx2, ny: ny2 } = toImage(sxMax, syMax);
        if (Math.abs(nx2 - nx1) > 10 && Math.abs(ny2 - ny1) > 5) {
          setRefineArea(nx1, nx2, ny1, ny2);
        }
        setRefineDragStart(null);
        setRefineDragEnd(null);
        return;
      }

      if (selectionBox) {
        e.stopPropagation();
        const finalBox = { ...selectionBox, endX: sx, endY: sy };
        const selectedIndices = findPointsInBox(finalBox);
        setSelectedPointIndices(selectedIndices);
        setSelectionBox(null);
      } else if (isMultiDragging && multiDragStartY !== null) {
        e.stopPropagation();
        const curveStore = useCurveStore.getState();
        useCurveStore.getState().setPoints([...curveStore.points]);
        setIsMultiDragging(false);
        setMultiDragStartY(null);
        setMultiDragLastY(null);
      } else if (dragPointIndex !== null) {
        e.stopPropagation();
        const curveStore = useCurveStore.getState();
        curveStore.setPoints([...curveStore.points]);
        dragStartPointsRef.current = null;
        setDragPointIndex(null);
      }
    },
    [selectionBox, isMultiDragging, multiDragStartY, dragPointIndex, getCanvasPos,
     toImage, imageHeight, setDragPointIndex, findPointsInBox, setSelectedPointIndices,
     isFreehandActive, refineDragStart, setRefineArea]
  );

  const handleMouseLeave = useCallback(() => {
    setHoveredIndex(null);
    if (isFreehandActive) {
      setIsFreehandActive(false);
    }
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
    if (refineDragStart) {
      setRefineDragStart(null);
      setRefineDragEnd(null);
    }
  }, [dragPointIndex, setDragPointIndex, selectionBox, isMultiDragging, isFreehandActive, refineDragStart]);

  const hasContent = isDrawing || hasDrawingContent || hasExtractedCurve || isRefineSelecting || refineXMin !== null || isMarkingStartingPoints || startingPoints.length > 0;
  if (!hasContent || imageWidth === 0 || imageHeight === 0) {
    return null;
  }

  const getCursor = () => {
    if (isMarkingStartingPoints) return "crosshair";
    if (isRefineSelecting || refineDragStart) return "crosshair";
    if (isDrawing) return "crosshair";
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
