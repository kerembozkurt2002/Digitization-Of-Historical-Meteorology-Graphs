/**
 * Curve Store - Manages extracted curve state, editing, and multi-stroke drawing.
 */

import { create } from "zustand";
import { invoke } from "@tauri-apps/api/core";
import type {
  CurvePoint,
  CurveStroke,
  CurveBoundSegment,
  ExtractCurveResponse,
  SaveAnnotationResponse,
  CleanAnnotationResponse,
} from "../types";

interface CurveEdit {
  points: CurvePoint[];
}

interface CurveState {
  rawPoints: CurvePoint[];
  points: CurvePoint[];
  isExtracting: boolean;
  showCurve: boolean;
  error: string | null;

  selectedPointIndex: number | null;
  selectedPointIndices: number[];
  dragPointIndex: number | null;

  editHistory: CurveEdit[];
  historyIndex: number;

  isBoundsModalOpen: boolean;
  curveBounds: CurveBoundSegment[];
  nextBoundId: number;

  // Legacy single-bound compat (derived from curveBounds[0])
  xMin: number | null;
  xMax: number | null;
  yHint: number | null;
  yHintEnd: number | null;

  // Refine area state (rectangle selection)
  isRefineSelecting: boolean;
  refineXMin: number | null;
  refineXMax: number | null;
  refineYMin: number | null;
  refineYMax: number | null;
  isRefining: boolean;

  // Multi-stroke drawing state
  isDrawing: boolean;
  drawingStrokes: CurveStroke[];
  activeStrokeId: number | null;
  nextStrokeId: number;
  isSavingAnnotation: boolean;
  isRecalculating: boolean;

  // Actions
  extractCurve: (imagePath: string, templateId: string, sampleInterval?: number, xMin?: number, xMax?: number, yHint?: number, yHintEnd?: number) => Promise<boolean>;
  setPoints: (points: CurvePoint[]) => void;
  updatePoint: (index: number, x: number, y: number) => void;
  updateMultiplePointsY: (indices: number[], deltaY: number) => void;
  deletePoint: (index: number) => void;
  insertPoint: (afterIndex: number, point: CurvePoint) => void;
  setSelectedPointIndex: (index: number | null) => void;
  setSelectedPointIndices: (indices: number[]) => void;
  setDragPointIndex: (index: number | null) => void;
  setShowCurve: (show: boolean) => void;
  resetEdits: () => void;
  undo: () => void;
  redo: () => void;
  canUndo: () => boolean;
  canRedo: () => boolean;
  clear: () => void;
  deleteSelectedPoints: () => void;

  openBoundsModal: () => void;
  closeBoundsModal: () => void;
  setBounds: (xMin: number, xMax: number, yHint?: number, yHintEnd?: number) => void;
  setCurveBounds: (bounds: CurveBoundSegment[]) => void;
  addBoundSegment: (xMin: number, xMax: number, yHint?: number, yHintEnd?: number) => void;
  removeBoundSegment: (id: number) => void;
  clearBounds: () => void;

  // Refine area actions
  setRefineSelecting: (on: boolean) => void;
  setRefineArea: (xMin: number, xMax: number, yMin: number, yMax: number) => void;
  clearRefineArea: () => void;
  refineInArea: (imagePath: string, templateId: string) => Promise<boolean>;

  // Drawing actions
  setDrawingMode: (on: boolean) => void;
  addDrawingPoint: (p: CurvePoint) => void;
  finishStroke: () => void;
  startNewStroke: () => void;
  removeStroke: (id: number) => void;
  clearDrawing: () => void;
  saveAnnotation: (imagePath: string, templateId: string) => Promise<SaveAnnotationResponse>;
  recalculateFromDrawing: (imagePath: string, templateId: string) => Promise<boolean>;

  // Compat helpers
  getAllDrawingPoints: () => CurvePoint[];
  getTotalDrawingPoints: () => number;
}

function boundsToLegacy(bounds: CurveBoundSegment[]): { xMin: number | null; xMax: number | null; yHint: number | null; yHintEnd: number | null } {
  if (bounds.length === 0) return { xMin: null, xMax: null, yHint: null, yHintEnd: null };
  const xMin = Math.min(...bounds.map((b) => b.xMin));
  const xMax = Math.max(...bounds.map((b) => b.xMax));
  const yHint = bounds[0].yHint ?? null;
  const yHintEnd = bounds[bounds.length - 1].yHintEnd ?? null;
  return { xMin, xMax, yHint, yHintEnd };
}

function pushHistory(state: CurveState, newPoints: CurvePoint[]): Partial<CurveState> {
  const newHistory = state.editHistory.slice(0, state.historyIndex + 1);
  newHistory.push({ points: newPoints });
  return {
    points: newPoints,
    editHistory: newHistory,
    historyIndex: newHistory.length - 1,
  };
}

export const useCurveStore = create<CurveState>((set, get) => ({
  rawPoints: [],
  points: [],
  isExtracting: false,
  showCurve: true,
  error: null,
  selectedPointIndex: null,
  selectedPointIndices: [],
  dragPointIndex: null,
  editHistory: [],
  historyIndex: -1,
  isBoundsModalOpen: false,
  curveBounds: [],
  nextBoundId: 1,
  xMin: null,
  xMax: null,
  yHint: null,
  yHintEnd: null,
  isRefineSelecting: false,
  refineXMin: null,
  refineXMax: null,
  refineYMin: null,
  refineYMax: null,
  isRefining: false,

  isDrawing: false,
  drawingStrokes: [],
  activeStrokeId: null,
  nextStrokeId: 1,
  isSavingAnnotation: false,
  isRecalculating: false,

  extractCurve: async (imagePath, templateId, sampleInterval = 5, xMin?: number, xMax?: number, yHint?: number, yHintEnd?: number) => {
    set({ isExtracting: true, error: null });

    try {
      const { curveBounds } = get();

      // Multi-segment: if we have 2+ bound segments AND the caller didn't
      // pass explicit overrides, run one extraction per segment.
      const useMultiBounds = curveBounds.length >= 2 && xMin === undefined && xMax === undefined;

      if (useMultiBounds) {
        const allPts: CurvePoint[] = [];
        for (const seg of curveBounds) {
          const params: Record<string, unknown> = {
            imagePath,
            templateId,
            sampleInterval,
            xMin: Math.round(seg.xMin),
            xMax: Math.round(seg.xMax),
          };
          if (seg.yHint !== undefined) params.yHint = Math.round(seg.yHint);
          if (seg.yHintEnd !== undefined) params.yHintEnd = Math.round(seg.yHintEnd);

          const result = await invoke<ExtractCurveResponse>("extract_curve", params);
          if (result.success && result.points) {
            allPts.push(...result.points);
          }
        }

        if (allPts.length >= 2) {
          set({
            rawPoints: allPts,
            points: [...allPts],
            isExtracting: false,
            showCurve: true,
            editHistory: [{ points: [...allPts] }],
            historyIndex: 0,
            selectedPointIndex: null,
          });
          return true;
        } else {
          set({ isExtracting: false, error: "No curve detected in any segment" });
          return false;
        }
      }

      // Single extraction (one or zero bound segments, or explicit overrides)
      const params: Record<string, unknown> = {
        imagePath,
        templateId,
        sampleInterval,
      };
      if (xMin !== undefined) params.xMin = Math.round(xMin);
      if (xMax !== undefined) params.xMax = Math.round(xMax);
      if (yHint !== undefined) params.yHint = Math.round(yHint);
      if (yHintEnd !== undefined) params.yHintEnd = Math.round(yHintEnd);

      const result = await invoke<ExtractCurveResponse>("extract_curve", params);

      if (result.success && result.points && result.points.length > 0) {
        const pts = result.points;
        set({
          rawPoints: pts,
          points: [...pts],
          isExtracting: false,
          showCurve: true,
          editHistory: [{ points: [...pts] }],
          historyIndex: 0,
          selectedPointIndex: null,
        });
        return true;
      } else {
        set({
          isExtracting: false,
          error: result.error || result.message || "No curve detected",
        });
        return false;
      }
    } catch (err) {
      set({
        isExtracting: false,
        error: String(err),
      });
      return false;
    }
  },

  setPoints: (points) => {
    set((state) => ({
      ...pushHistory(state, points),
    }));
  },

  updatePoint: (index, x, y) => {
    const state = get();
    const newPoints = [...state.points];
    if (index < 0 || index >= newPoints.length) return;
    newPoints[index] = { x, y };
    set(pushHistory(state, newPoints));
  },

  updateMultiplePointsY: (indices, deltaY) => {
    const state = get();
    const newPoints = [...state.points];
    for (const idx of indices) {
      if (idx >= 0 && idx < newPoints.length) {
        newPoints[idx] = { x: newPoints[idx].x, y: newPoints[idx].y + deltaY };
      }
    }
    set(pushHistory(state, newPoints));
  },

  deletePoint: (index) => {
    const state = get();
    const newPoints = state.points.filter((_, i) => i !== index);
    set({
      ...pushHistory(state, newPoints),
      selectedPointIndex: null,
    });
  },

  insertPoint: (afterIndex, point) => {
    const state = get();
    const newPoints = [...state.points];
    newPoints.splice(afterIndex + 1, 0, point);
    set(pushHistory(state, newPoints));
  },

  setSelectedPointIndex: (index) => set({ selectedPointIndex: index, selectedPointIndices: [] }),
  setSelectedPointIndices: (indices) => set({ selectedPointIndices: indices, selectedPointIndex: null }),
  setDragPointIndex: (index) => set({ dragPointIndex: index }),
  setShowCurve: (show) => set({ showCurve: show }),

  resetEdits: () => {
    const state = get();
    const pts = [...state.rawPoints];
    set({
      ...pushHistory(state, pts),
      selectedPointIndex: null,
    });
  },

  undo: () => {
    const state = get();
    if (state.historyIndex > 0) {
      const newIndex = state.historyIndex - 1;
      set({
        points: [...state.editHistory[newIndex].points],
        historyIndex: newIndex,
      });
    }
  },

  redo: () => {
    const state = get();
    if (state.historyIndex < state.editHistory.length - 1) {
      const newIndex = state.historyIndex + 1;
      set({
        points: [...state.editHistory[newIndex].points],
        historyIndex: newIndex,
      });
    }
  },

  canUndo: () => get().historyIndex > 0,
  canRedo: () => get().historyIndex < get().editHistory.length - 1,

  clear: () =>
    set({
      rawPoints: [],
      points: [],
      isExtracting: false,
      showCurve: true,
      error: null,
      selectedPointIndex: null,
      selectedPointIndices: [],
      dragPointIndex: null,
      editHistory: [],
      historyIndex: -1,
      isBoundsModalOpen: false,
      curveBounds: [],
      nextBoundId: 1,
      xMin: null,
      xMax: null,
      yHint: null,
      yHintEnd: null,
      isRefineSelecting: false,
      refineXMin: null,
      refineXMax: null,
      refineYMin: null,
      refineYMax: null,
      isRefining: false,
      isDrawing: false,
      drawingStrokes: [],
      activeStrokeId: null,
      nextStrokeId: 1,
      isSavingAnnotation: false,
      isRecalculating: false,
    }),

  openBoundsModal: () => set({ isBoundsModalOpen: true }),
  closeBoundsModal: () => set({ isBoundsModalOpen: false }),

  setBounds: (xMin, xMax, yHint?, yHintEnd?) => {
    const seg: CurveBoundSegment = {
      id: 1,
      xMin: Math.min(xMin, xMax),
      xMax: Math.max(xMin, xMax),
      yHint: yHint,
      yHintEnd: yHintEnd,
    };
    set({ curveBounds: [seg], nextBoundId: 2, ...boundsToLegacy([seg]) });
  },

  setCurveBounds: (bounds) => {
    const maxId = bounds.length > 0 ? Math.max(...bounds.map((b) => b.id)) : 0;
    set({ curveBounds: bounds, nextBoundId: maxId + 1, ...boundsToLegacy(bounds) });
  },

  addBoundSegment: (xMin, xMax, yHint?, yHintEnd?) => {
    const state = get();
    const seg: CurveBoundSegment = {
      id: state.nextBoundId,
      xMin: Math.min(xMin, xMax),
      xMax: Math.max(xMin, xMax),
      yHint,
      yHintEnd,
    };
    const newBounds = [...state.curveBounds, seg].sort((a, b) => a.xMin - b.xMin);
    set({ curveBounds: newBounds, nextBoundId: state.nextBoundId + 1, ...boundsToLegacy(newBounds) });
  },

  removeBoundSegment: (id) => {
    const newBounds = get().curveBounds.filter((b) => b.id !== id);
    set({ curveBounds: newBounds, ...boundsToLegacy(newBounds) });
  },

  clearBounds: () => set({ curveBounds: [], nextBoundId: 1, xMin: null, xMax: null, yHint: null, yHintEnd: null }),

  setRefineSelecting: (on) => set({ isRefineSelecting: on, refineXMin: null, refineXMax: null, refineYMin: null, refineYMax: null }),

  setRefineArea: (xMin, xMax, yMin, yMax) => set({
    refineXMin: Math.min(xMin, xMax),
    refineXMax: Math.max(xMin, xMax),
    refineYMin: Math.min(yMin, yMax),
    refineYMax: Math.max(yMin, yMax),
    isRefineSelecting: false,
  }),

  clearRefineArea: () => set({ refineXMin: null, refineXMax: null, refineYMin: null, refineYMax: null, isRefineSelecting: false }),

  refineInArea: async (imagePath, templateId) => {
    const state = get();
    if (state.refineXMin === null || state.refineXMax === null ||
        state.refineYMin === null || state.refineYMax === null ||
        state.points.length < 2) return false;

    const rXMin = state.refineXMin;
    const rXMax = state.refineXMax;
    const rYMin = state.refineYMin;
    const rYMax = state.refineYMax;
    set({ isRefining: true, error: null });

    try {
      // Check if user drew strokes within the refine range
      const strokesInRange = state.drawingStrokes.filter((s) =>
        s.points.some((p) => p.x >= rXMin && p.x <= rXMax)
      );
      const hasDrawing = strokesInRange.length > 0 &&
        strokesInRange.some((s) => s.points.filter((p) => p.x >= rXMin && p.x <= rXMax).length >= 2);

      const baseParams: Record<string, unknown> = {
        imagePath,
        templateId,
        sampleInterval: 5,
        xMin: Math.round(rXMin),
        xMax: Math.round(rXMax),
        yMin: Math.round(rYMin),
        yMax: Math.round(rYMax),
      };

      if (hasDrawing) {
        // Draw + Refine path: save drawing as annotation, clean it, then extract
        const allPoints = state.drawingStrokes.flatMap((s) => s.points);
        const strokeData = state.drawingStrokes
          .filter((s) => s.points.length > 0)
          .map((s) => ({
            id: s.id,
            label: s.label,
            num_points: s.points.length,
            points: s.points,
          }));

        const saveResult = await invoke<SaveAnnotationResponse>("save_curve_annotation", {
          imagePath,
          templateId,
          points: allPoints,
          strokes: strokeData,
        });

        if (!saveResult.success || !saveResult.path) {
          set({ isRefining: false, error: saveResult.error || "Failed to save annotation" });
          return false;
        }

        const cleanResult = await invoke<CleanAnnotationResponse>("clean_annotation", {
          filePath: saveResult.path,
        });

        if (!cleanResult.success) {
          set({ isRefining: false, error: cleanResult.error || "Failed to clean annotation" });
          return false;
        }

        const result = await invoke<ExtractCurveResponse>("extract_curve", baseParams);

        if (result.success && result.points && result.points.length > 0) {
          const kept = state.points.filter((p) => p.x < rXMin || p.x > rXMax);
          const merged = [...kept, ...result.points].sort((a, b) => a.x - b.x);

          set({
            ...pushHistory(state, merged),
            rawPoints: merged,
            isRefining: false,
            refineXMin: null,
            refineXMax: null,
            refineYMin: null,
            refineYMax: null,
            drawingStrokes: [],
            activeStrokeId: null,
            nextStrokeId: 1,
            isDrawing: false,
            showCurve: true,
          });
          return true;
        } else {
          set({ isRefining: false, error: result.error || result.message || "No curve detected in area" });
          return false;
        }
      }

      // No drawing: use rectangle Y bounds as yHint/yHintEnd for gravity
      baseParams.yHint = Math.round(rYMin);
      baseParams.yHintEnd = Math.round(rYMax);

      const result = await invoke<ExtractCurveResponse>("extract_curve", baseParams);

      if (result.success && result.points && result.points.length > 0) {
        const kept = state.points.filter((p) => p.x < rXMin || p.x > rXMax);
        const merged = [...kept, ...result.points].sort((a, b) => a.x - b.x);

        set({
          ...pushHistory(state, merged),
          rawPoints: merged,
          isRefining: false,
          refineXMin: null,
          refineXMax: null,
          refineYMin: null,
          refineYMax: null,
        });
        return true;
      } else {
        set({ isRefining: false, error: result.error || result.message || "No curve detected in area" });
        return false;
      }
    } catch (err) {
      set({ isRefining: false, error: String(err) });
      return false;
    }
  },

  setDrawingMode: (on) => {
    if (on) {
      const id = get().nextStrokeId;
      const strokeCount = get().drawingStrokes.length;
      set({
        isDrawing: true,
        showCurve: false,
        activeStrokeId: id,
        nextStrokeId: id + 1,
        drawingStrokes: [
          ...get().drawingStrokes,
          { id, label: `Curve ${strokeCount + 1}`, points: [] },
        ],
      });
    } else {
      set({ isDrawing: false, showCurve: true, activeStrokeId: null });
    }
  },

  addDrawingPoint: (p) => {
    const { activeStrokeId, drawingStrokes } = get();
    if (activeStrokeId === null) return;
    set({
      drawingStrokes: drawingStrokes.map((s) =>
        s.id === activeStrokeId ? { ...s, points: [...s.points, p] } : s
      ),
    });
  },

  finishStroke: () => {
    // Keep the stroke in the list but deactivate active tracking
    // (mouseup calls this -- the stroke stays, user can start a new one)
  },

  startNewStroke: () => {
    const id = get().nextStrokeId;
    const strokeCount = get().drawingStrokes.length;
    set({
      activeStrokeId: id,
      nextStrokeId: id + 1,
      drawingStrokes: [
        ...get().drawingStrokes,
        { id, label: `Curve ${strokeCount + 1}`, points: [] },
      ],
    });
  },

  removeStroke: (id) => {
    const state = get();
    const remaining = state.drawingStrokes.filter((s) => s.id !== id);
    set({
      drawingStrokes: remaining,
      activeStrokeId: state.activeStrokeId === id ? null : state.activeStrokeId,
    });
  },

  clearDrawing: () =>
    set({
      drawingStrokes: [],
      activeStrokeId: null,
      nextStrokeId: 1,
      isDrawing: false,
      showCurve: true,
    }),

  saveAnnotation: async (imagePath, templateId) => {
    set({ isSavingAnnotation: true });
    try {
      const strokes = get().drawingStrokes.filter((s) => s.points.length > 0);
      const allPoints = strokes.flatMap((s) => s.points);
      const strokeData = strokes.map((s) => ({
        id: s.id,
        label: s.label,
        num_points: s.points.length,
        points: s.points,
      }));

      const result = await invoke<SaveAnnotationResponse>("save_curve_annotation", {
        imagePath,
        templateId,
        points: allPoints,
        strokes: strokeData,
      });
      set({ isSavingAnnotation: false });
      return result;
    } catch (err) {
      set({ isSavingAnnotation: false });
      return { success: false, error: String(err) };
    }
  },

  recalculateFromDrawing: async (imagePath, templateId) => {
    const state = get();
    const strokes = state.drawingStrokes.filter((s) => s.points.length > 0);
    if (strokes.length === 0) return false;

    set({ isRecalculating: true, error: null });

    try {
      const allPoints = strokes.flatMap((s) => s.points);
      const strokeData = strokes.map((s) => ({
        id: s.id,
        label: s.label,
        num_points: s.points.length,
        points: s.points,
      }));

      const saveResult = await invoke<SaveAnnotationResponse>("save_curve_annotation", {
        imagePath,
        templateId,
        points: allPoints,
        strokes: strokeData,
      });

      if (!saveResult.success || !saveResult.path) {
        set({ isRecalculating: false, error: saveResult.error || "Failed to save annotation" });
        return false;
      }

      const cleanResult = await invoke<CleanAnnotationResponse>("clean_annotation", {
        filePath: saveResult.path,
      });

      if (!cleanResult.success) {
        set({ isRecalculating: false, error: cleanResult.error || "Failed to clean annotation" });
        return false;
      }

      // Auto-derive X bounds from drawn strokes when no manual bounds set
      let derivedXMin = state.xMin ?? undefined;
      let derivedXMax = state.xMax ?? undefined;
      if (derivedXMin === undefined || derivedXMax === undefined) {
        const allXs = strokes.flatMap((s) => s.points.map((p) => p.x));
        if (allXs.length > 0) {
          derivedXMin = derivedXMin ?? Math.min(...allXs);
          derivedXMax = derivedXMax ?? Math.max(...allXs);
        }
      }

      const bounds = {
        xMin: derivedXMin,
        xMax: derivedXMax,
        yHint: state.yHint ?? undefined,
        yHintEnd: state.yHintEnd ?? undefined,
      };

      const ok = await get().extractCurve(
        imagePath,
        templateId,
        5,
        bounds.xMin,
        bounds.xMax,
        bounds.yHint,
        bounds.yHintEnd,
      );

      // Clear drawing after recalculate so user sees only the refined curve
      set({
        isRecalculating: false,
        isDrawing: false,
        drawingStrokes: [],
        activeStrokeId: null,
        nextStrokeId: 1,
      });
      return ok;
    } catch (err) {
      set({ isRecalculating: false, error: String(err) });
      return false;
    }
  },

  getAllDrawingPoints: () => get().drawingStrokes.flatMap((s) => s.points),
  getTotalDrawingPoints: () => get().drawingStrokes.reduce((n, s) => n + s.points.length, 0),

  deleteSelectedPoints: () => {
    const state = get();
    const indicesToDelete = new Set<number>();

    if (state.selectedPointIndex !== null) {
      indicesToDelete.add(state.selectedPointIndex);
    }
    for (const idx of state.selectedPointIndices) {
      indicesToDelete.add(idx);
    }
    if (indicesToDelete.size === 0) return;

    const newPoints = state.points.filter((_, i) => !indicesToDelete.has(i));
    set({
      ...pushHistory(state, newPoints),
      selectedPointIndex: null,
      selectedPointIndices: [],
    });
  },
}));

export default useCurveStore;
