/**
 * Curve Store - Manages extracted curve state, editing, and multi-stroke drawing.
 */

import { create } from "zustand";
import { invoke } from "@tauri-apps/api/core";
import type {
  CurvePoint,
  CurveStroke,
  CurveBoundSegment,
  CurveStartingPoint,
  ExtractCurveResponse,
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

  // Starting points for curve extraction (replaces bounds modal)
  isMarkingStartingPoints: boolean;
  startingPoints: CurveStartingPoint[];
  nextStartingPointId: number;
  // Track if we're waiting for end point (second click)
  awaitingEndPoint: boolean;

  // Legacy bounds compat (kept for backward compatibility)
  curveBounds: CurveBoundSegment[];
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

  // Multi-stroke drawing state (visual aid only, no annotation saving)
  isDrawing: boolean;
  drawingStrokes: CurveStroke[];
  activeStrokeId: number | null;
  nextStrokeId: number;

  // Actions
  extractCurve: (imagePath: string, templateId: string, sampleInterval?: number, xMin?: number, xMax?: number, yHint?: number, yHintEnd?: number, imageWidth?: number) => Promise<boolean>;
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

  // Starting points actions
  setMarkingStartingPoints: (on: boolean) => void;
  addStartingPoint: (x: number, y: number) => void;
  removeStartingPoint: (id: number) => void;
  clearStartingPoints: () => void;

  // Legacy bounds compat
  clearBounds: () => void;

  // Refine area actions
  setRefineSelecting: (on: boolean) => void;
  setRefineArea: (xMin: number, xMax: number, yMin: number, yMax: number) => void;
  clearRefineArea: () => void;
  refineInArea: (imagePath: string, templateId: string) => Promise<boolean>;

  // Drawing actions (visual aid only)
  setDrawingMode: (on: boolean) => void;
  addDrawingPoint: (p: CurvePoint) => void;
  finishStroke: () => void;
  startNewStroke: () => void;
  removeStroke: (id: number) => void;
  clearDrawing: () => void;

  // Snap drawing to curve and merge with existing points
  snapDrawingAndMerge: (imagePath: string, templateId: string) => Promise<boolean>;

  // Compat helpers
  getAllDrawingPoints: () => CurvePoint[];
  getTotalDrawingPoints: () => number;
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
  isMarkingStartingPoints: false,
  startingPoints: [],
  nextStartingPointId: 1,
  awaitingEndPoint: false,
  curveBounds: [],
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

  extractCurve: async (imagePath, templateId, sampleInterval = 5, xMin?: number, xMax?: number, yHint?: number, yHintEnd?: number, _imageWidth?: number) => {
    set({ isExtracting: true, error: null });

    try {
      const { startingPoints } = get();

      // If we have ANY starting points, ONLY extract within defined segments
      // (curve cannot exist outside of marked segments)
      if (startingPoints.length > 0 && xMin === undefined && xMax === undefined) {
        // Only process complete segments (those with both start and end points)
        const completeSegments = startingPoints.filter(sp => sp.endX !== undefined && sp.endY !== undefined);

        if (completeSegments.length === 0) {
          // User has started marking but no complete segments yet
          set({ isExtracting: false, error: "Complete at least one segment (mark both start and end points)" });
          return false;
        }

        const allPts: CurvePoint[] = [];

        for (let i = 0; i < completeSegments.length; i++) {
          const sp = completeSegments[i];

          const params: Record<string, unknown> = {
            imagePath,
            templateId,
            sampleInterval,
            xMin: Math.round(sp.x),
            xMax: Math.round(sp.endX!),
            yHint: Math.round(sp.y),
            yHintEnd: Math.round(sp.endY!),
          };

          const result = await invoke<ExtractCurveResponse>("extract_curve", params);
          if (result.success && result.points) {
            allPts.push(...result.points);
          }
        }

        if (allPts.length >= 2) {
          // Sort all points by X
          allPts.sort((a, b) => a.x - b.x);
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

      // NO starting points - extract full image (from first grid line to end)

      // Single extraction (no starting points, or explicit overrides)
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
      isMarkingStartingPoints: false,
      startingPoints: [],
      nextStartingPointId: 1,
      awaitingEndPoint: false,
      curveBounds: [],
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
    }),

  // Starting points actions
  setMarkingStartingPoints: (on) => set({ isMarkingStartingPoints: on, awaitingEndPoint: false }),

  addStartingPoint: (x, y) => {
    const state = get();

    if (state.awaitingEndPoint && state.startingPoints.length > 0) {
      // Second click: add ending point to the last starting point
      const lastIdx = state.startingPoints.length - 1;
      const updatedPoints = [...state.startingPoints];
      updatedPoints[lastIdx] = {
        ...updatedPoints[lastIdx],
        endX: x,
        endY: y,
      };
      // Sort by starting X
      updatedPoints.sort((a, b) => a.x - b.x);
      set({
        startingPoints: updatedPoints,
        awaitingEndPoint: false,
      });
    } else {
      // First click: add new starting point
      const newPoint: CurveStartingPoint = {
        id: state.nextStartingPointId,
        x,
        y,
      };
      const newPoints = [...state.startingPoints, newPoint].sort((a, b) => a.x - b.x);
      set({
        startingPoints: newPoints,
        nextStartingPointId: state.nextStartingPointId + 1,
        awaitingEndPoint: true, // Now waiting for ending point
      });
    }
  },

  removeStartingPoint: (id) => {
    const newPoints = get().startingPoints.filter((p) => p.id !== id);
    set({ startingPoints: newPoints });
  },

  clearStartingPoints: () => set({ startingPoints: [], nextStartingPointId: 1, awaitingEndPoint: false }),

  clearBounds: () => set({ curveBounds: [], xMin: null, xMax: null, yHint: null, yHintEnd: null, startingPoints: [], nextStartingPointId: 1, awaitingEndPoint: false }),

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
      // Use rectangle Y bounds as yHint/yHintEnd for search constraint
      const params: Record<string, unknown> = {
        imagePath,
        templateId,
        sampleInterval: 5,
        xMin: Math.round(rXMin),
        xMax: Math.round(rXMax),
        yMin: Math.round(rYMin),
        yMax: Math.round(rYMax),
        yHint: Math.round(rYMin),
        yHintEnd: Math.round(rYMax),
      };

      const result = await invoke<ExtractCurveResponse>("extract_curve", params);

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
        // Keep showCurve true so existing curve remains visible during drawing
        showCurve: true,
        activeStrokeId: id,
        nextStrokeId: id + 1,
        drawingStrokes: [
          ...get().drawingStrokes,
          { id, label: `Curve ${strokeCount + 1}`, points: [] },
        ],
      });
    } else {
      set({ isDrawing: false, activeStrokeId: null });
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
    }),

  snapDrawingAndMerge: async (imagePath, templateId) => {
    const state = get();
    const allDrawnPoints = state.drawingStrokes.flatMap((s) => s.points);

    if (allDrawnPoints.length < 2) {
      // Not enough drawn points, just clear drawing
      set({
        drawingStrokes: [],
        activeStrokeId: null,
        nextStrokeId: 1,
        isDrawing: false,
      });
      return false;
    }

    try {
      // Call backend to process drawn points
      const result = await invoke<ExtractCurveResponse>("snap_drawing_to_curve", {
        imagePath,
        templateId,
        drawnPoints: allDrawnPoints,
        snapBand: 5,
        sampleInterval: 5,
      });

      if (result.success && result.points && result.points.length > 0) {
        const drawnPoints = result.points;

        // Get X range of drawn points
        const drawnXMin = Math.min(...drawnPoints.map((p) => p.x));
        const drawnXMax = Math.max(...drawnPoints.map((p) => p.x));

        // Keep existing points outside the drawn range, replace inside
        const leftPoints = state.points.filter((p) => p.x < drawnXMin);
        const rightPoints = state.points.filter((p) => p.x > drawnXMax);

        // Merge: existing left + drawn + existing right (no blending, direct replacement)
        const mergedPoints = [...leftPoints, ...drawnPoints, ...rightPoints].sort(
          (a, b) => a.x - b.x
        );

        // Clear drawing and update curve
        set({
          ...pushHistory(state, mergedPoints),
          rawPoints: mergedPoints,
          drawingStrokes: [],
          activeStrokeId: null,
          nextStrokeId: 1,
          isDrawing: false,
        });

        return true;
      } else {
        // Failed - clear drawing without modifying curve
        set({
          drawingStrokes: [],
          activeStrokeId: null,
          nextStrokeId: 1,
          isDrawing: false,
          error: result.error || result.message || "Failed to process drawing",
        });
        return false;
      }
    } catch (err) {
      set({
        drawingStrokes: [],
        activeStrokeId: null,
        nextStrokeId: 1,
        isDrawing: false,
        error: String(err),
      });
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
