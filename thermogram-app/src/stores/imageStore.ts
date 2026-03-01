/**
 * Image Store - Manages image state and view settings.
 */

import { create } from "zustand";
import type {
  ViewMode,
  ProcessingState,
  ChartMetadata,
  ZoomState,
  ChartFormat,
  CalibrationSettings,
} from "../types";
import { CHART_TYPE_DEFAULTS } from "../types";

interface ImageState {
  // File state
  imagePath: string | null;
  metadata: ChartMetadata | null;

  // Chart type and calibration
  chartType: ChartFormat;
  calibration: CalibrationSettings;

  // Image data (base64 encoded)
  originalImage: string | null;
  horizontalImage: string | null;
  verticalImage: string | null;
  combinedImage: string | null;

  // View settings
  viewMode: ViewMode;
  zoom: ZoomState;

  // Processing state
  processing: ProcessingState;

  // Actions
  setImagePath: (path: string | null) => void;
  setMetadata: (metadata: ChartMetadata | null) => void;
  setChartType: (chartType: ChartFormat) => void;
  setCalibration: (calibration: Partial<CalibrationSettings>) => void;
  resetCalibrationToDefaults: () => void;
  setOriginalImage: (image: string | null) => void;
  setHorizontalImage: (image: string | null) => void;
  setVerticalImage: (image: string | null) => void;
  setCombinedImage: (image: string | null) => void;
  setViewMode: (mode: ViewMode) => void;
  setZoom: (zoom: Partial<ZoomState>) => void;
  resetZoom: () => void;
  setProcessingState: (state: Partial<ProcessingState>) => void;
  clearImages: () => void;
  reset: () => void;
}

const initialZoom: ZoomState = {
  scale: 1,
  offsetX: 0,
  offsetY: 0,
};

const initialProcessing: ProcessingState = {
  stage: "idle",
  progress: 0,
  message: "Ready",
};

const initialChartType: ChartFormat = "daily";
const initialCalibration: CalibrationSettings = { ...CHART_TYPE_DEFAULTS.daily };

export const useImageStore = create<ImageState>((set) => ({
  // Initial state
  imagePath: null,
  metadata: null,
  chartType: initialChartType,
  calibration: initialCalibration,
  originalImage: null,
  horizontalImage: null,
  verticalImage: null,
  combinedImage: null,
  viewMode: "original",
  zoom: initialZoom,
  processing: initialProcessing,

  // Actions
  setImagePath: (path) =>
    set({
      imagePath: path,
      // Clear images when path changes
      originalImage: null,
      horizontalImage: null,
      verticalImage: null,
      combinedImage: null,
      viewMode: "original",
      processing: initialProcessing,
    }),

  setMetadata: (metadata) => set({ metadata }),

  setChartType: (chartType) =>
    set({
      chartType,
      calibration: { ...CHART_TYPE_DEFAULTS[chartType] },
    }),

  setCalibration: (calibration) =>
    set((state) => ({
      calibration: { ...state.calibration, ...calibration },
    })),

  resetCalibrationToDefaults: () =>
    set((state) => ({
      calibration: { ...CHART_TYPE_DEFAULTS[state.chartType] },
    })),

  setOriginalImage: (image) => set({ originalImage: image }),

  setHorizontalImage: (image) => set({ horizontalImage: image }),

  setVerticalImage: (image) => set({ verticalImage: image }),

  setCombinedImage: (image) => set({ combinedImage: image }),

  setViewMode: (mode) => set({ viewMode: mode }),

  setZoom: (zoom) =>
    set((state) => ({
      zoom: { ...state.zoom, ...zoom },
    })),

  resetZoom: () => set({ zoom: initialZoom }),

  setProcessingState: (newState) =>
    set((state) => ({
      processing: { ...state.processing, ...newState },
    })),

  clearImages: () =>
    set({
      originalImage: null,
      horizontalImage: null,
      verticalImage: null,
      combinedImage: null,
    }),

  reset: () =>
    set({
      imagePath: null,
      metadata: null,
      chartType: initialChartType,
      calibration: initialCalibration,
      originalImage: null,
      horizontalImage: null,
      verticalImage: null,
      combinedImage: null,
      viewMode: "original",
      zoom: initialZoom,
      processing: initialProcessing,
    }),
}));

// Selectors
export const selectCurrentImage = (state: ImageState): string | null => {
  switch (state.viewMode) {
    case "horizontal":
      return state.horizontalImage;
    case "vertical":
      return state.verticalImage;
    case "combined":
      return state.combinedImage;
    case "original":
    default:
      return state.originalImage;
  }
};

export const selectIsProcessing = (state: ImageState): boolean => {
  return state.processing.stage !== "idle" && state.processing.stage !== "complete" && state.processing.stage !== "error";
};
