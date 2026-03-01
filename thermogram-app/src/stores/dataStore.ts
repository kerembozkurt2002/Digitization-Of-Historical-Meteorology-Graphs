/**
 * Data Store - Manages extracted data points and validation state.
 */

import { create } from "zustand";
import type {
  DataPoint,
  ValidationIssue,
  CalibrationResult,
  SelectionState,
} from "../types";

interface DataState {
  // Data points
  dataPoints: DataPoint[];
  rawPoints: [number, number][];

  // Validation
  validationIssues: ValidationIssue[];
  overallConfidence: number;
  needsReview: boolean;
  reviewReason: string;

  // Calibration
  calibration: CalibrationResult | null;

  // Statistics
  stats: {
    tempMin: number;
    tempMax: number;
    tempMean: number;
    tempStd: number;
    totalSamples: number;
    interpolatedSamples: number;
    dataCompleteness: number;
    consistencyScore: number;
  };

  // Selection state
  selection: SelectionState;

  // Edit history for undo/redo
  editHistory: DataPoint[][];
  historyIndex: number;

  // Actions
  setDataPoints: (points: DataPoint[]) => void;
  setRawPoints: (points: [number, number][]) => void;
  setValidationIssues: (issues: ValidationIssue[]) => void;
  setOverallConfidence: (confidence: number) => void;
  setNeedsReview: (needsReview: boolean, reason?: string) => void;
  setCalibration: (calibration: CalibrationResult | null) => void;
  setStats: (stats: Partial<DataState["stats"]>) => void;
  setSelection: (selection: Partial<SelectionState>) => void;
  clearSelection: () => void;

  // Data point editing
  updateDataPoint: (index: number, updates: Partial<DataPoint>) => void;
  deleteDataPoint: (index: number) => void;
  addDataPoint: (point: DataPoint) => void;

  // Undo/redo
  undo: () => void;
  redo: () => void;
  canUndo: () => boolean;
  canRedo: () => boolean;

  // Reset
  reset: () => void;
}

const initialStats = {
  tempMin: 0,
  tempMax: 0,
  tempMean: 0,
  tempStd: 0,
  totalSamples: 0,
  interpolatedSamples: 0,
  dataCompleteness: 0,
  consistencyScore: 0,
};

const initialSelection: SelectionState = {
  selectedPointIndex: null,
  selectedRegion: null,
};

export const useDataStore = create<DataState>((set, get) => ({
  // Initial state
  dataPoints: [],
  rawPoints: [],
  validationIssues: [],
  overallConfidence: 0,
  needsReview: false,
  reviewReason: "",
  calibration: null,
  stats: initialStats,
  selection: initialSelection,
  editHistory: [],
  historyIndex: -1,

  // Actions
  setDataPoints: (points) =>
    set({
      dataPoints: points,
      editHistory: [points],
      historyIndex: 0,
    }),

  setRawPoints: (points) => set({ rawPoints: points }),

  setValidationIssues: (issues) => set({ validationIssues: issues }),

  setOverallConfidence: (confidence) => set({ overallConfidence: confidence }),

  setNeedsReview: (needsReview, reason = "") =>
    set({ needsReview, reviewReason: reason }),

  setCalibration: (calibration) => set({ calibration }),

  setStats: (newStats) =>
    set((state) => ({
      stats: { ...state.stats, ...newStats },
    })),

  setSelection: (selection) =>
    set((state) => ({
      selection: { ...state.selection, ...selection },
    })),

  clearSelection: () => set({ selection: initialSelection }),

  // Data point editing with history
  updateDataPoint: (index, updates) => {
    const state = get();
    const newPoints = [...state.dataPoints];
    newPoints[index] = {
      ...newPoints[index],
      ...updates,
      is_edited: true,
    };

    // Add to history
    const newHistory = state.editHistory.slice(0, state.historyIndex + 1);
    newHistory.push(newPoints);

    set({
      dataPoints: newPoints,
      editHistory: newHistory,
      historyIndex: newHistory.length - 1,
    });
  },

  deleteDataPoint: (index) => {
    const state = get();
    const newPoints = state.dataPoints.filter((_, i) => i !== index);

    // Add to history
    const newHistory = state.editHistory.slice(0, state.historyIndex + 1);
    newHistory.push(newPoints);

    set({
      dataPoints: newPoints,
      editHistory: newHistory,
      historyIndex: newHistory.length - 1,
      selection: initialSelection,
    });
  },

  addDataPoint: (point) => {
    const state = get();
    const newPoints = [...state.dataPoints, { ...point, is_added: true }];

    // Sort by datetime
    newPoints.sort((a, b) => a.datetime.localeCompare(b.datetime));

    // Add to history
    const newHistory = state.editHistory.slice(0, state.historyIndex + 1);
    newHistory.push(newPoints);

    set({
      dataPoints: newPoints,
      editHistory: newHistory,
      historyIndex: newHistory.length - 1,
    });
  },

  undo: () => {
    const state = get();
    if (state.historyIndex > 0) {
      const newIndex = state.historyIndex - 1;
      set({
        dataPoints: state.editHistory[newIndex],
        historyIndex: newIndex,
      });
    }
  },

  redo: () => {
    const state = get();
    if (state.historyIndex < state.editHistory.length - 1) {
      const newIndex = state.historyIndex + 1;
      set({
        dataPoints: state.editHistory[newIndex],
        historyIndex: newIndex,
      });
    }
  },

  canUndo: () => {
    const state = get();
    return state.historyIndex > 0;
  },

  canRedo: () => {
    const state = get();
    return state.historyIndex < state.editHistory.length - 1;
  },

  reset: () =>
    set({
      dataPoints: [],
      rawPoints: [],
      validationIssues: [],
      overallConfidence: 0,
      needsReview: false,
      reviewReason: "",
      calibration: null,
      stats: initialStats,
      selection: initialSelection,
      editHistory: [],
      historyIndex: -1,
    }),
}));

// Selectors
export const selectPointsWithIssues = (state: DataState): number[] => {
  return state.validationIssues.map((issue) => issue.index);
};

export const selectEditedPoints = (state: DataState): DataPoint[] => {
  return state.dataPoints.filter((p) => p.is_edited || p.is_added);
};

export const selectIssuesForPoint = (
  state: DataState,
  index: number
): ValidationIssue[] => {
  return state.validationIssues.filter((issue) => issue.index === index);
};
