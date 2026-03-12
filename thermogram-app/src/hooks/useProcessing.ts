/**
 * useProcessing Hook - Handles image processing operations.
 */

import { useCallback } from "react";
import { invoke } from "@tauri-apps/api/core";
import { useImageStore, selectIsProcessing } from "../stores/imageStore";
import type { PreviewResponse, MatchTemplateResponse, DetectTemplateResponse, GetCalibrationResponse } from "../types";

export function useProcessing() {
  const {
    imagePath,
    calibration,
    chartType,
    detectedTemplate,
    gridCalibration,
    setOriginalImage,
    setHorizontalImage,
    setVerticalImage,
    setCombinedImage,
    setMatchImage,
    setLinePositions,
    setProcessingState,
    setViewMode,
    setDetectedTemplate,
    setGridCalibration,
  } = useImageStore();

  const isProcessing = useImageStore(selectIsProcessing);

  const processGridDetection = useCallback(async () => {
    if (!imagePath) {
      setProcessingState({
        stage: "error",
        message: "Please select an image first.",
      });
      return;
    }

    setProcessingState({
      stage: "preprocessing",
      progress: 10,
      message: "Detecting horizontal lines...",
    });

    try {
      // Get horizontal lines (mode 4)
      const horizontalResult = await invoke<PreviewResponse>("preview_grid", {
        imagePath: imagePath,
        algorithm: 4,
      });

      if (horizontalResult.success && horizontalResult.preview_image) {
        setHorizontalImage(horizontalResult.preview_image);
      }

      setProcessingState({
        stage: "dewarping",
        progress: 40,
        message: "Detecting vertical lines...",
      });

      // Get vertical lines (mode 5) - no curvature, we'll render client-side
      const verticalResult = await invoke<PreviewResponse>("preview_grid", {
        imagePath: imagePath,
        algorithm: 5,
      });

      if (verticalResult.success) {
        // Store line positions and curve coefficients for client-side rendering
        if (verticalResult.vertical_line_positions) {
          setLinePositions({
            vertical: verticalResult.vertical_line_positions,
            horizontal: horizontalResult.horizontal_line_positions ?? [],
            height: verticalResult.image_height ?? 0,
            width: verticalResult.image_width ?? 0,
            coeffA: verticalResult.curve_coeff_a ?? 0,
            coeffB: verticalResult.curve_coeff_b ?? 0,
          });
        }
        // Still store the preview image as fallback
        if (verticalResult.preview_image) {
          setVerticalImage(verticalResult.preview_image);
        }
      }

      setProcessingState({
        stage: "calibrating",
        progress: 70,
        message: "Creating combined view...",
      });

      // Get combined view (mode 6) - no curvature, we'll render client-side
      const combinedResult = await invoke<PreviewResponse>("preview_grid", {
        imagePath: imagePath,
        algorithm: 6,
      });

      if (combinedResult.success && combinedResult.preview_image) {
        setCombinedImage(combinedResult.preview_image);
      }

      const hLines = horizontalResult.horizontal_lines ?? 0;
      const vLines = verticalResult.vertical_lines ?? 0;

      // Check if calibration exists for vertical grid rendering
      const currentGridCalibration = useImageStore.getState().gridCalibration;

      if (currentGridCalibration) {
        setProcessingState({
          stage: "complete",
          progress: 100,
          message: `Done! H:${hLines} V:${vLines} | ${calibration.tempMin}°C - ${calibration.tempMax}°C, start ${calibration.startHour}:00`,
        });
      } else {
        setProcessingState({
          stage: "complete",
          progress: 100,
          message: `H:${hLines} detected | ⚠ Vertical grid requires calibration`,
        });
      }

      setViewMode("combined");
    } catch (err) {
      setProcessingState({
        stage: "error",
        progress: 0,
        message: `Error: ${err}`,
        error: String(err),
      });
    }
  }, [imagePath, calibration, setOriginalImage, setHorizontalImage, setVerticalImage, setCombinedImage, setProcessingState, setViewMode]);

  const processMatchTemplate = useCallback(async () => {
    if (!imagePath) {
      setProcessingState({
        stage: "error",
        message: "Please select an image first.",
      });
      return;
    }

    setProcessingState({
      stage: "preprocessing",
      progress: 20,
      message: "Running template matching...",
    });

    try {
      const matchResult = await invoke<MatchTemplateResponse>("match_template", {
        imagePath: imagePath,
      });

      if (matchResult.success && matchResult.match_image) {
        setMatchImage(matchResult.match_image);
        setProcessingState({
          stage: "complete",
          progress: 100,
          message: `Found ${matchResult.match_count ?? 0} matches`,
        });
        setViewMode("match");
      } else {
        setProcessingState({
          stage: "error",
          progress: 0,
          message: matchResult.error ?? "Template matching failed",
        });
      }
    } catch (err) {
      setProcessingState({
        stage: "error",
        progress: 0,
        message: `Error: ${err}`,
        error: String(err),
      });
    }
  }, [imagePath, setMatchImage, setProcessingState, setViewMode]);

  const loadGridCalibration = useCallback(async (templateId: string) => {
    try {
      const result = await invoke<GetCalibrationResponse>("get_calibration", {
        templateId,
      });

      if (result.success && result.exists && result.derived) {
        setGridCalibration({
          // Vertical line endpoints (for curve calculation)
          topPoint: result.derived.top_point,
          bottomPoint: result.derived.bottom_point,
          // Curve parameters
          curveCenterY: result.derived.curve_center_y,
          curvature: result.derived.curve_coeff_a, // This is curvature in pixels
          // Line positions
          lineSpacing: result.derived.line_spacing,
          linePositions: result.derived.line_positions,
          // Horizontal data
          horizontalSpacing: result.derived.horizontal_spacing ?? 0,
          horizontalPositions: result.derived.horizontal_positions ?? [],
          horizontalTopTemp: result.derived.horizontal_top_temp ?? 0,
          // Metadata
          calibratedAt: result.calibrated_at ?? "",
        });
        return true;
      } else {
        setGridCalibration(null);
        return false;
      }
    } catch (err) {
      console.error("Failed to load grid calibration:", err);
      setGridCalibration(null);
      return false;
    }
  }, [setGridCalibration]);

  const detectTemplate = useCallback(async () => {
    if (!imagePath) {
      return null;
    }

    try {
      const result = await invoke<DetectTemplateResponse>("detect_template", {
        imagePath: imagePath,
      });

      if (result.success && result.template_id) {
        const template = {
          templateId: result.template_id,
          chartType: result.chart_type ?? "unknown",
          confidence: result.confidence ?? 0,
          period: result.period ?? "unknown",
          gridColor: result.grid_color ?? "unknown",
        };
        setDetectedTemplate(template);

        // Load grid calibration for this template
        await loadGridCalibration(result.template_id);

        return template;
      } else {
        setDetectedTemplate(null);
        setGridCalibration(null);
        return null;
      }
    } catch (err) {
      console.error("Template detection error:", err);
      setDetectedTemplate(null);
      setGridCalibration(null);
      return null;
    }
  }, [imagePath, setDetectedTemplate, setGridCalibration, loadGridCalibration]);

  return {
    processGridDetection,
    processMatchTemplate,
    detectTemplate,
    loadGridCalibration,
    isProcessing,
    calibration,
    chartType,
    detectedTemplate,
    gridCalibration,
  };
}

export default useProcessing;
