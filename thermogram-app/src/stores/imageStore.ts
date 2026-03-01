/**
 * Image Store - Manages image state and view settings.
 */

import { create } from "zustand";
import type {
  ViewMode,
  ProcessingState,
  ChartMetadata,
  ZoomState,
} from "../types";

interface ImageState {
  // File state
  imagePath: string | null;
  metadata: ChartMetadata | null;

  // Image data (base64 encoded)
  originalImage: string | null;
  preprocessedImage: string | null;
  dewarpedImage: string | null;
  segmentedImage: string | null;
  overlayImage: string | null;

  // View settings
  viewMode: ViewMode;
  zoom: ZoomState;

  // Processing state
  processing: ProcessingState;

  // Actions
  setImagePath: (path: string | null) => void;
  setMetadata: (metadata: ChartMetadata | null) => void;
  setOriginalImage: (image: string | null) => void;
  setPreprocessedImage: (image: string | null) => void;
  setDewarpedImage: (image: string | null) => void;
  setSegmentedImage: (image: string | null) => void;
  setOverlayImage: (image: string | null) => void;
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

export const useImageStore = create<ImageState>((set) => ({
  // Initial state
  imagePath: null,
  metadata: null,
  originalImage: null,
  preprocessedImage: null,
  dewarpedImage: null,
  segmentedImage: null,
  overlayImage: null,
  viewMode: "original",
  zoom: initialZoom,
  processing: initialProcessing,

  // Actions
  setImagePath: (path) =>
    set({
      imagePath: path,
      // Clear images when path changes
      originalImage: null,
      preprocessedImage: null,
      dewarpedImage: null,
      segmentedImage: null,
      overlayImage: null,
      viewMode: "original",
      processing: initialProcessing,
    }),

  setMetadata: (metadata) => set({ metadata }),

  setOriginalImage: (image) => set({ originalImage: image }),

  setPreprocessedImage: (image) => set({ preprocessedImage: image }),

  setDewarpedImage: (image) => set({ dewarpedImage: image }),

  setSegmentedImage: (image) => set({ segmentedImage: image }),

  setOverlayImage: (image) => set({ overlayImage: image }),

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
      preprocessedImage: null,
      dewarpedImage: null,
      segmentedImage: null,
      overlayImage: null,
    }),

  reset: () =>
    set({
      imagePath: null,
      metadata: null,
      originalImage: null,
      preprocessedImage: null,
      dewarpedImage: null,
      segmentedImage: null,
      overlayImage: null,
      viewMode: "original",
      zoom: initialZoom,
      processing: initialProcessing,
    }),
}));

// Selectors
export const selectCurrentImage = (state: ImageState): string | null => {
  switch (state.viewMode) {
    case "preprocessed":
      return state.preprocessedImage;
    case "dewarped":
      return state.dewarpedImage;
    case "segmented":
      return state.segmentedImage;
    case "overlay":
    case "adaptiveH":
      return state.overlayImage;
    case "original":
    default:
      return state.originalImage;
  }
};

export const selectIsProcessing = (state: ImageState): boolean => {
  return state.processing.stage !== "idle" && state.processing.stage !== "complete" && state.processing.stage !== "error";
};
