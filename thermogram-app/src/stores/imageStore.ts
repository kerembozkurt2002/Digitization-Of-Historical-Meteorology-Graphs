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

interface DetectedTemplate {
  templateId: string;
  chartType: string;
  confidence: number;
  period: string;
  gridColor: string;
}

interface GridCalibrationData {
  // Vertical line endpoints (for curve calculation)
  topPoint: { x: number; y: number };
  bottomPoint: { x: number; y: number };
  // Curve parameters
  curveCenterY: number;
  curvature: number; // Curvature in pixels (how much apex is offset from base line)
  // Vertical line positions
  lineSpacing: number;
  linePositions: number[];
  // Horizontal data
  horizontalSpacing: number;
  horizontalPositions: number[];
  horizontalTopTemp: number;
  // Rotation angle (radians) - for correcting skewed scans
  rotationAngle?: number;
  // Metadata
  calibratedAt: string;
}

interface ImageState {
  // File state
  imagePath: string | null;
  metadata: ChartMetadata | null;

  // Template detection
  detectedTemplate: DetectedTemplate | null;

  // Grid calibration (from saved calibration file)
  gridCalibration: GridCalibrationData | null;

  // Chart type and calibration
  chartType: ChartFormat;
  calibration: CalibrationSettings;

  // Image data (base64 encoded)
  originalImage: string | null;

  // Image dimensions (for calibration modal)
  imageHeight: number;
  imageWidth: number;

  // View settings
  viewMode: ViewMode;
  zoom: ZoomState;

  // Processing state
  processing: ProcessingState;

  // Actions
  setImagePath: (path: string | null) => void;
  setMetadata: (metadata: ChartMetadata | null) => void;
  setDetectedTemplate: (template: DetectedTemplate | null) => void;
  setGridCalibration: (calibration: GridCalibrationData | null) => void;
  setChartType: (chartType: ChartFormat) => void;
  setCalibration: (calibration: Partial<CalibrationSettings>) => void;
  resetCalibrationToDefaults: () => void;
  setOriginalImage: (image: string | null) => void;
  setImageDimensions: (width: number, height: number) => void;
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
  detectedTemplate: null,
  gridCalibration: null,
  chartType: initialChartType,
  calibration: initialCalibration,
  originalImage: null,
  imageHeight: 0,
  imageWidth: 0,
  viewMode: "image",
  zoom: initialZoom,
  processing: initialProcessing,

  // Actions
  setImagePath: (path) =>
    set({
      imagePath: path,
      // DON'T clear originalImage - keep showing old image until new one loads
      viewMode: "image",
      processing: { stage: "preprocessing", progress: 10, message: "Loading image..." },
    }),

  setMetadata: (metadata) => set({ metadata }),

  setDetectedTemplate: (template) => set({ detectedTemplate: template }),

  setGridCalibration: (calibration) => set({ gridCalibration: calibration }),

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

  setImageDimensions: (width, height) =>
    set({
      imageWidth: width,
      imageHeight: height,
    }),

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
    }),

  reset: () =>
    set({
      imagePath: null,
      metadata: null,
      detectedTemplate: null,
      gridCalibration: null,
      chartType: initialChartType,
      calibration: initialCalibration,
      originalImage: null,
      imageHeight: 0,
      imageWidth: 0,
      viewMode: "image",
      zoom: initialZoom,
      processing: initialProcessing,
    }),
}));

// Selectors
export const selectCurrentImage = (state: ImageState): string | null => {
  return state.originalImage;
};

export const selectIsProcessing = (state: ImageState): boolean => {
  return state.processing.stage !== "idle" && state.processing.stage !== "complete" && state.processing.stage !== "error";
};
