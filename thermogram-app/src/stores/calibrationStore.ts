/**
 * Calibration Store - Manages grid calibration modal state.
 *
 * Alignment Mode (when calibration exists):
 *   Step 1: Click anchor point (saved temp + time intersection)
 *   Step 2: Click end of same horizontal line (for rotation)
 *   -> Rotation applied, grid aligned
 *
 * Full Calibration Mode (7 steps):
 *   Step 1: Click horizontal line start + enter temperature
 *   Step 2: Click horizontal line end (for rotation calculation)
 *   Step 3: Adjust horizontal spacing slider
 *   Step 4: Click TOP of vertical line + enter hour
 *   Step 5: Click BOTTOM of same vertical line
 *   Step 6: Adjust curvature slider
 *   Step 7: Adjust vertical spacing slider
 */

import { create } from "zustand";

export interface Point {
  x: number;
  y: number;
}

// Saved calibration data for alignment mode
export interface SavedCalibrationData {
  // Reference values from calibration (for display)
  referenceHour: number;
  referenceMinute: number;
  referenceTemp: number;
  // Grid parameters
  verticalSpacing: number;
  horizontalSpacing: number;
  curvature: number;
  centerY: number;
  // Reference line shape (for curvature)
  topPoint: Point;
  bottomPoint: Point;
}

export type CalibrationPhase = "prompt" | "alignment" | "horizontal" | "vertical" | "complete";

interface CalibrationState {
  // Modal state
  isOpen: boolean;
  phase: CalibrationPhase;
  currentStep: number; // 1-7

  // Rotation angle (calculated from horizontal line points)
  rotationAngle: number; // radians

  // Alignment mode data (when calibration already exists)
  savedCalibration: SavedCalibrationData | null;
  alignmentPoint: Point | null; // First click - anchor point
  alignmentEndPoint: Point | null; // Second click - end of horizontal line

  // Horizontal calibration data (steps 1-3)
  horizontalTop: Point | null; // Start of horizontal line
  horizontalEndPoint: Point | null; // End of horizontal line (for rotation)
  horizontalTopTemp: number; // Temperature value

  // Spacing (direct pixel values)
  horizontalSpacing: number; // pixels between horizontal lines
  verticalSpacing: number; // pixels between vertical lines

  // Vertical calibration data (steps 4-7)
  verticalLine1Top: Point | null;
  verticalLine1Bottom: Point | null;
  verticalLine1Hour: number; // 0-23
  verticalLine1Minute: number; // 0-59

  // Curve parameters (controlled by sliders)
  centerY: number;
  curvature: number;

  // Image interaction
  zoom: number;
  pan: Point;

  // Template info
  templateId: string | null;
  imageWidth: number;
  imageHeight: number;

  // Actions
  openModal: (templateId: string, imageWidth: number, imageHeight: number) => void;
  openPrompt: (templateId: string, imageWidth: number, imageHeight: number) => void;
  openAlignment: (templateId: string, imageWidth: number, imageHeight: number, saved: SavedCalibrationData) => void;
  closeModal: () => void;
  startCalibration: () => void;
  startFullCalibration: () => void; // Switch from alignment to full calibration

  // Alignment mode
  setAlignmentPoint: (point: Point) => void;
  setAlignmentEndPoint: (point: Point) => void;
  calculateAlignmentRotation: () => number;

  // Step navigation
  nextStep: () => void;
  prevStep: () => void;

  // Point setters
  setHorizontalTop: (point: Point) => void;
  setHorizontalEndPoint: (point: Point) => void;
  setHorizontalTopTemp: (temp: number) => void;
  setVerticalLine1Top: (point: Point) => void;
  setVerticalLine1Bottom: (point: Point) => void;
  setVerticalLine1Hour: (hour: number) => void;
  setVerticalLine1Minute: (minute: number) => void;

  // Rotation
  calculateRotation: () => number;
  setRotationAngle: (angle: number) => void;

  // Slider setters
  setCenterY: (value: number) => void;
  setCurvature: (value: number) => void;
  setVerticalSpacing: (value: number) => void;
  setHorizontalSpacing: (value: number) => void;

  // Image controls
  setZoom: (zoom: number) => void;
  setPan: (x: number, y: number) => void;

  // Template
  setTemplateId: (templateId: string) => void;

  // Reset
  resetCalibration: () => void;
}

const initialState = {
  isOpen: false,
  phase: "prompt" as CalibrationPhase,
  currentStep: 1,
  rotationAngle: 0,
  savedCalibration: null as SavedCalibrationData | null,
  alignmentPoint: null as Point | null,
  alignmentEndPoint: null as Point | null,
  horizontalTop: null as Point | null,
  horizontalEndPoint: null as Point | null,
  horizontalTopTemp: 0,
  horizontalSpacing: 25, // default 25px
  verticalSpacing: 30, // default 30px
  verticalLine1Top: null as Point | null,
  verticalLine1Bottom: null as Point | null,
  verticalLine1Hour: 12,
  verticalLine1Minute: 0,
  centerY: 0,
  curvature: 0,
  zoom: 1.0,
  pan: { x: 0, y: 0 },
  templateId: null as string | null,
  imageWidth: 0,
  imageHeight: 0,
};

export const useCalibrationStore = create<CalibrationState>((set, get) => ({
  ...initialState,

  openModal: (templateId, imageWidth, imageHeight) =>
    set({
      ...initialState,
      isOpen: true,
      phase: "horizontal",
      currentStep: 1,
      centerY: imageHeight / 2,
      templateId,
      imageWidth,
      imageHeight,
    }),

  openPrompt: (templateId, imageWidth, imageHeight) =>
    set({
      ...initialState,
      isOpen: true,
      phase: "prompt",
      centerY: imageHeight / 2,
      templateId,
      imageWidth,
      imageHeight,
    }),

  openAlignment: (templateId, imageWidth, imageHeight, saved) =>
    set({
      ...initialState,
      isOpen: true,
      phase: "alignment",
      savedCalibration: saved,
      centerY: saved.centerY,
      curvature: saved.curvature,
      verticalSpacing: saved.verticalSpacing,
      horizontalSpacing: saved.horizontalSpacing,
      templateId,
      imageWidth,
      imageHeight,
    }),

  closeModal: () =>
    set({
      isOpen: false,
      phase: "prompt",
      currentStep: 1,
      alignmentPoint: null,
      alignmentEndPoint: null,
      rotationAngle: 0,
    }),

  startCalibration: () =>
    set({
      phase: "horizontal",
      currentStep: 1,
    }),

  startFullCalibration: () =>
    set({
      phase: "horizontal",
      currentStep: 1,
      savedCalibration: null,
      alignmentPoint: null,
      alignmentEndPoint: null,
      rotationAngle: 0,
    }),

  setAlignmentPoint: (point) => set({ alignmentPoint: point }),
  setAlignmentEndPoint: (point) => set({ alignmentEndPoint: point }),

  calculateAlignmentRotation: () => {
    const { alignmentPoint, alignmentEndPoint } = get();
    if (!alignmentPoint || !alignmentEndPoint) return 0;

    const dx = alignmentEndPoint.x - alignmentPoint.x;
    const dy = alignmentEndPoint.y - alignmentPoint.y;
    const angle = Math.atan2(dy, dx);
    return angle;
  },

  nextStep: () => {
    const { currentStep, phase } = get();

    if (phase === "horizontal") {
      if (currentStep === 2) {
        // After clicking horizontal end point, calculate rotation
        const rotation = get().calculateRotation();
        set({ rotationAngle: rotation, currentStep: 3 });
      } else if (currentStep === 3) {
        // After horizontal spacing, move to vertical phase
        set({ phase: "vertical", currentStep: 4 });
      } else {
        set({ currentStep: currentStep + 1 });
      }
    } else if (phase === "vertical") {
      if (currentStep === 7) {
        // After vertical spacing, complete
        set({ phase: "complete" });
      } else {
        set({ currentStep: currentStep + 1 });
      }
    }
  },

  prevStep: () => {
    const { currentStep, phase } = get();

    if (phase === "vertical") {
      if (currentStep === 4) {
        // Go back from vertical to horizontal spacing step
        set({ phase: "horizontal", currentStep: 3 });
      } else if (currentStep > 4) {
        set({ currentStep: currentStep - 1 });
      }
    } else if (phase === "horizontal" && currentStep > 1) {
      set({ currentStep: currentStep - 1 });
    }
  },

  setHorizontalTop: (point) => set({ horizontalTop: point }),
  setHorizontalEndPoint: (point) => set({ horizontalEndPoint: point }),
  setHorizontalTopTemp: (temp) => set({ horizontalTopTemp: temp }),
  setVerticalLine1Top: (point) => set({ verticalLine1Top: point }),
  setVerticalLine1Bottom: (point) => set({ verticalLine1Bottom: point }),
  setVerticalLine1Hour: (hour) => set({ verticalLine1Hour: Math.max(0, Math.min(23, hour)) }),
  setVerticalLine1Minute: (minute) => set({ verticalLine1Minute: Math.max(0, Math.min(59, minute)) }),

  calculateRotation: () => {
    const { horizontalTop, horizontalEndPoint } = get();
    if (!horizontalTop || !horizontalEndPoint) return 0;

    const dx = horizontalEndPoint.x - horizontalTop.x;
    const dy = horizontalEndPoint.y - horizontalTop.y;
    const angle = Math.atan2(dy, dx);
    return angle;
  },

  setRotationAngle: (angle) => set({ rotationAngle: angle }),

  setCenterY: (value) => set({ centerY: value }),
  setCurvature: (value) => set({ curvature: value }),
  setVerticalSpacing: (value) => set({ verticalSpacing: Math.max(1, value) }),
  setHorizontalSpacing: (value) => set({ horizontalSpacing: Math.max(1, value) }),

  setZoom: (zoom) => set({ zoom: Math.max(0.3, Math.min(3.0, zoom)) }),
  setPan: (x, y) => set({ pan: { x, y } }),

  setTemplateId: (templateId) => set({ templateId }),

  resetCalibration: () => {
    const { templateId, imageWidth, imageHeight } = get();
    set({
      ...initialState,
      isOpen: true,
      phase: "horizontal",
      currentStep: 1,
      centerY: imageHeight / 2,
      templateId,
      imageWidth,
      imageHeight,
    });
  },
}));

// Step instructions - detailed with actions
export const CALIBRATION_STEPS: Record<number, {
  phase: string;
  instruction: string;
  requiresInput?: boolean;
  inputType?: "temperature" | "time";
  isSliderStep?: boolean;
  sliderType?: "horizontalSpacing" | "curvature" | "verticalSpacing";
}> = {
  // Horizontal phase (steps 1-3)
  1: {
    phase: "horizontal",
    instruction: "Click the LEFT end of a horizontal grid line and enter its temperature (°C)",
    requiresInput: true,
    inputType: "temperature",
  },
  2: {
    phase: "horizontal",
    instruction: "Click the RIGHT end of the SAME horizontal line (for rotation alignment)",
    requiresInput: false,
  },
  3: {
    phase: "horizontal",
    instruction: "Adjust the spacing slider until horizontal grid lines align. Click Next when done",
    requiresInput: false,
    isSliderStep: true,
    sliderType: "horizontalSpacing",
  },
  // Vertical phase (steps 4-7)
  4: {
    phase: "vertical",
    instruction: "Click the TOP of a vertical grid line and enter the time",
    requiresInput: true,
    inputType: "time",
  },
  5: {
    phase: "vertical",
    instruction: "Click the BOTTOM of the SAME vertical line",
    requiresInput: false,
  },
  6: {
    phase: "vertical",
    instruction: "Adjust the curvature slider until the blue curve matches the grid line",
    requiresInput: false,
    isSliderStep: true,
    sliderType: "curvature",
  },
  7: {
    phase: "vertical",
    instruction: "Adjust the spacing slider until vertical grid lines align. Click Finish to save",
    requiresInput: false,
    isSliderStep: true,
    sliderType: "verticalSpacing",
  },
};

export default useCalibrationStore;
