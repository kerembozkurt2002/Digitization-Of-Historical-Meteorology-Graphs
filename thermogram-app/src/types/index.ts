/**
 * TypeScript types for the Thermogram Digitization application.
 */

// ============================================================================
// API Response Types
// ============================================================================

export interface PreviewResponse {
  success: boolean;
  error?: string;
  message?: string;
  vertical_lines?: number;
  horizontal_lines?: number;
  preview_image?: string;
  // Line positions for client-side rendering
  vertical_line_positions?: number[];
  horizontal_line_positions?: number[];
  image_height?: number;
  image_width?: number;
  // Curve coefficients: x = a*y² + b*y + x0
  curve_coeff_a?: number;
  curve_coeff_b?: number;
}


// ============================================================================
// Data Point Types
// ============================================================================

export interface DataPoint {
  x_pixel: number;
  y_pixel: number;
  datetime: string;
  temperature: number;
  confidence: number;
  is_edited: boolean;
  is_added: boolean;
}

export interface ValidationIssue {
  type: "out_of_range" | "sudden_jump" | "gap" | "low_confidence";
  index: number;
  message: string;
  severity: "info" | "warning" | "error";
  suggested_value?: number;
}

// ============================================================================
// Chart Configuration Types
// ============================================================================

export type ChartFormat = "daily" | "four_day" | "weekly";

/**
 * User-editable calibration settings for each chart.
 * These values can be overridden from defaults.
 */
export interface CalibrationSettings {
  tempMin: number;
  tempMax: number;
  startHour: number;
  curvature: number; // 0.0 = straight lines, 1.0 = full detected curvature
  vSpacing: number; // 1.0 = detected spacing, <1 = tighter, >1 = wider
}

/**
 * Default calibration values per chart type.
 */
export const CHART_TYPE_DEFAULTS: Record<ChartFormat, CalibrationSettings> = {
  daily: { tempMin: 10, tempMax: 40, startHour: 7, curvature: 0.5, vSpacing: 1.0 },
  four_day: { tempMin: 5, tempMax: 35, startHour: 12, curvature: 0.5, vSpacing: 1.0 },
  weekly: { tempMin: 0, tempMax: 30, startHour: 12, curvature: 0.5, vSpacing: 1.0 },
};

export interface ChartMetadata {
  filename: string;
  filepath: string;
  format: ChartFormat;
  year?: number;
  month?: string;
  day?: number;
  station?: string;
  instrument?: string;
}

export interface CalibrationPoint {
  x_pixel: number;
  y_pixel: number;
  datetime?: string;
  temperature?: number;
  is_reference: boolean;
}

// ============================================================================
// Processing State Types
// ============================================================================

export type ProcessingStage =
  | "idle"
  | "preprocessing"
  | "dewarping"
  | "calibrating"
  | "segmenting"
  | "digitizing"
  | "validating"
  | "complete"
  | "error";

export interface ProcessingState {
  stage: ProcessingStage;
  progress: number;
  message: string;
  error?: string;
}

// ============================================================================
// View Mode Types
// ============================================================================

export type ViewMode = "image" | "original" | "curve";

// ============================================================================
// Template Detection Types
// ============================================================================

export interface DetectTemplateResponse {
  success: boolean;
  error?: string;
  template_id?: string;
  chart_type?: string;
  confidence?: number;
  period?: string;
  grid_color?: string;
  all_scores?: Record<string, number>;
}

// ============================================================================
// Result Types (matching backend models)
// ============================================================================

export interface PreprocessResult {
  success: boolean;
  message: string;
  processed_image?: string;
  grayscale_image?: string;
  roi_bounds?: [number, number, number, number];
}

export interface DewarpResult {
  success: boolean;
  message: string;
  straightened_image?: string;
  grid_lines_detected: number;
  vertical_lines_count: number;
  horizontal_lines_count: number;
}

export interface CalibrationResult {
  success: boolean;
  message: string;
  time_gridlines: number[];
  temp_gridlines: number[];
  start_datetime?: string;
  end_datetime?: string;
  temp_min: number;
  temp_max: number;
  calibration_confidence: number;
}

export interface SegmentResult {
  success: boolean;
  message: string;
  curve_mask?: string;
  skeleton_image?: string;
  segment_count: number;
  curve_width_avg: number;
}

export interface DigitizeResult {
  success: boolean;
  message: string;
  data_points: DataPoint[];
  total_samples: number;
  interpolated_samples: number;
  temp_min: number;
  temp_max: number;
  temp_mean: number;
  temp_std: number;
}

export interface ValidationResult {
  success: boolean;
  message: string;
  issues: ValidationIssue[];
  out_of_range_count: number;
  sudden_jump_count: number;
  gap_count: number;
  low_confidence_count: number;
  overall_confidence: number;
  needs_review: boolean;
  review_reason: string;
  data_completeness: number;
  consistency_score: number;
}

// ============================================================================
// Processing Session Types
// ============================================================================

export interface ProcessingSession {
  session_id: string;
  created_at: string;
  updated_at: string;
  metadata?: ChartMetadata;
  config_type: ChartFormat;
  current_stage: number;
  completed_stages: number[];
  preprocess_result?: PreprocessResult;
  dewarp_result?: DewarpResult;
  calibration_result?: CalibrationResult;
  segment_result?: SegmentResult;
  digitize_result?: DigitizeResult;
  validation_result?: ValidationResult;
}

// ============================================================================
// UI State Types
// ============================================================================

export interface ZoomState {
  scale: number;
  offsetX: number;
  offsetY: number;
}

export interface SelectionState {
  selectedPointIndex: number | null;
  selectedRegion: {
    x: number;
    y: number;
    width: number;
    height: number;
  } | null;
}

// ============================================================================
// Export Types
// ============================================================================

export type ExportFormat = "csv" | "json" | "excel";

export interface ExportOptions {
  format: ExportFormat;
  include_metadata: boolean;
  include_confidence: boolean;
  include_validation_flags: boolean;
  datetime_format: string;
  decimal_places: number;
}

// ============================================================================
// Grid Calibration Types
// ============================================================================

export interface CalibrationPoint {
  x: number;
  y: number;
}

export interface GridCalibrationDerived {
  top_point: CalibrationPoint;
  bottom_point: CalibrationPoint;
  curve_center_y: number;
  curve_coeff_a: number;
  line_slope?: number;
  line_mid_x?: number;
  line_mid_y?: number;
  line_spacing: number;
  line_positions: number[];
  // Horizontal data
  horizontal_spacing?: number;
  horizontal_positions?: number[];
  horizontal_top_temp?: number;
  horizontal_top_y?: number;
  // Rotation from horizontal line calibration (step 1-2)
  rotation_angle?: number;
  // Reference values for alignment mode
  reference_hour?: number;
  reference_minute?: number;
  reference_temp?: number;
}

export interface SaveCalibrationResponse {
  success: boolean;
  error?: string;
  template_id?: string;
  calibrated_at?: string;
  line_spacing?: number;
  curve_coeff_a?: number;
  curve_coeff_b?: number;
  curve_center_y?: number;
}

export interface GetCalibrationResponse {
  success: boolean;
  error?: string;
  exists?: boolean;
  template_id?: string;
  calibrated_at?: string;
  image_dimensions?: { width: number; height: number };
  derived?: GridCalibrationDerived;
}

// ============================================================================
// Curve Extraction Types
// ============================================================================

export interface CurvePoint {
  x: number;
  y: number;
}

export interface ExtractCurveResponse {
  success: boolean;
  error?: string;
  points?: CurvePoint[];
  num_points?: number;
  message?: string;
}

export interface CurveStroke {
  id: number;
  label: string;
  points: CurvePoint[];
}

export interface CurveBoundSegment {
  id: number;
  xMin: number;
  xMax: number;
  yHint?: number;
  yHintEnd?: number;
}

// Starting point for curve extraction - each point marks where a curve segment begins and ends
export interface CurveStartingPoint {
  id: number;
  x: number;
  y: number;
  // Ending point (second click) - marks where this segment ends
  endX?: number;
  endY?: number;
}


