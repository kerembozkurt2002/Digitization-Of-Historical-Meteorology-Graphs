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
}

export interface DewarpResponse {
  success: boolean;
  error?: string;
  message?: string;
  grid_lines_detected?: number;
  original_image?: string;
  straightened_image?: string;
  forward_transform?: number[][];
  inverse_transform?: number[][];
  output_path?: string;
}

export interface HealthResponse {
  success: boolean;
  status: "healthy" | "degraded" | "unhealthy";
  message: string;
  version: string;
  stages_available?: string[];
  config_types?: string[];
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

export type ViewMode =
  | "original"
  | "preprocessed"
  | "dewarped"
  | "segmented"
  | "overlay"
  | "adaptiveH";

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
