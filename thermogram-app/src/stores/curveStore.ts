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
  dragPointIndex: number | null;

  editHistory: CurveEdit[];
  historyIndex: number;

  // Bounds (user-defined left/right X limits in natural image px)
  isBoundsModalOpen: boolean;
  xMin: number | null;
  xMax: number | null;

  // Actions
  extractCurve: (imagePath: string, templateId: string, sampleInterval?: number) => Promise<boolean>;
  setPoints: (points: CurvePoint[]) => void;
  updatePoint: (index: number, x: number, y: number) => void;
  deletePoint: (index: number) => void;
  insertPoint: (afterIndex: number, point: CurvePoint) => void;
  setSelectedPointIndex: (index: number | null) => void;
  setDragPointIndex: (index: number | null) => void;
  setShowCurve: (show: boolean) => void;
  resetEdits: () => void;
  undo: () => void;
  redo: () => void;
  canUndo: () => boolean;
  canRedo: () => boolean;
  clear: () => void;

  // Bounds actions
  openBoundsModal: () => void;
  closeBoundsModal: () => void;
  setBounds: (xMin: number, xMax: number) => void;
  clearBounds: () => void;
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
  dragPointIndex: null,
  editHistory: [],
  historyIndex: -1,
  isBoundsModalOpen: false,
  xMin: null,
  xMax: null,

  extractCurve: async (imagePath, templateId, sampleInterval = 5) => {
    set({ isExtracting: true, error: null });
    const { xMin, xMax } = get();

    try {
      const params: Record<string, unknown> = {
        imagePath,
        templateId,
        sampleInterval,
      };
      if (xMin !== null) params.xMin = Math.round(xMin);
      if (xMax !== null) params.xMax = Math.round(xMax);

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

  setSelectedPointIndex: (index) => set({ selectedPointIndex: index }),
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
      dragPointIndex: null,
      editHistory: [],
      historyIndex: -1,
      isBoundsModalOpen: false,
      xMin: null,
      xMax: null,
    }),

  openBoundsModal: () => set({ isBoundsModalOpen: true }),
  closeBoundsModal: () => set({ isBoundsModalOpen: false }),

  setBounds: (xMin: number, xMax: number) => {
    const left = Math.min(xMin, xMax);
    const right = Math.max(xMin, xMax);
    set({ xMin: left, xMax: right, isBoundsModalOpen: false });
  },

  clearBounds: () => set({ xMin: null, xMax: null }),
}));

export default useCurveStore;
