/**
 * useProcessing Hook - Handles image processing operations.
 */

import { useCallback } from "react";
import { invoke } from "@tauri-apps/api/core";
import { useImageStore } from "../stores/imageStore";
import type { DetectTemplateResponse, GetCalibrationResponse } from "../types";

export function useProcessing() {
  const {
    imagePath,
    calibration,
    chartType,
    detectedTemplate,
    gridCalibration,
    setDetectedTemplate,
    setGridCalibration,
  } = useImageStore();

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
          // Rotation from horizontal line calibration (step 1-2)
          rotationAngle: result.derived.rotation_angle ?? 0,
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
    detectTemplate,
    loadGridCalibration,
    calibration,
    chartType,
    detectedTemplate,
    gridCalibration,
  };
}

export default useProcessing;
