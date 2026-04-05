/**
 * Curve Store - Manages extracted curve state and editing.
 *
 * Holds the raw extracted points, user edits (overrides), and undo/redo history.
 * The "effective" points list merges raw + edits for rendering.
 */

import { create } from "zustand";
import { invoke } from "@tauri-apps/api/core";
import type { CurvePoint, ExtractCurveResponse } from "../types";

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
  selectedPointIndices: number[]; // Multi-selection
  dragPointIndex: number | null;

  editHistory: CurveEdit[];
  historyIndex: number;

  // Actions
  extractCurve: (imagePath: string, templateId: string, sampleInterval?: number, xMin?: number, xMax?: number) => Promise<boolean>;
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

  extractCurve: async (imagePath, templateId, sampleInterval = 5, xMin?: number, xMax?: number) => {
    set({ isExtracting: true, error: null });

    try {
      const params: Record<string, unknown> = {
        imagePath,
        templateId,
        sampleInterval,
      };
      if (xMin !== undefined) params.xMin = Math.round(xMin);
      if (xMax !== undefined) params.xMax = Math.round(xMax);

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
    }),

  deleteSelectedPoints: () => {
    const state = get();
    const indicesToDelete = new Set<number>();

    // Add single selected point
    if (state.selectedPointIndex !== null) {
      indicesToDelete.add(state.selectedPointIndex);
    }

    // Add multi-selected points
    for (const idx of state.selectedPointIndices) {
      indicesToDelete.add(idx);
    }

    if (indicesToDelete.size === 0) return;

    // Filter out deleted points
    const newPoints = state.points.filter((_, i) => !indicesToDelete.has(i));

    set({
      ...pushHistory(state, newPoints),
      selectedPointIndex: null,
      selectedPointIndices: [],
    });
  },
}));

export default useCurveStore;
