/**
 * useImageLoader Hook - Handles image loading from file path.
 *
 * Complete flow:
 * 1. Load image
 * 2. Detect template
 * 3. Load calibration (if exists)
 *
 * User can manually click "Align" or "Calibrate" buttons to open modals.
 */

import { useCallback } from "react";
import { invoke } from "@tauri-apps/api/core";
import { useImageStore } from "../stores/imageStore";
import type { SavedCalibrationData } from "../stores/calibrationStore";
import { useDataStore } from "../stores/dataStore";
import { useCurveStore } from "../stores/curveStore";
import type { PreviewResponse, DetectTemplateResponse, GetCalibrationResponse } from "../types";

export function useImageLoader() {
  const {
    setImagePath,
    setOriginalImage,
    setProcessingState,
    setImageDimensions,
    setDetectedTemplate,
    setGridCalibration,
  } = useImageStore();
  // Removed auto-open: const { openPrompt, openAlignment } = useCalibrationStore();
  // User can manually click "Align" or "Calibrate" buttons
  const { reset: resetData } = useDataStore();
  const { clear: clearCurve } = useCurveStore();

  const loadImageFromPath = useCallback(async (filePath: string): Promise<{ success: boolean; needsCalibration: boolean; templateId: string | null }> => {
    // Validate file extension
    const ext = filePath.split(".").pop()?.toLowerCase();
    const validExtensions = ["tif", "tiff", "png", "jpg", "jpeg"];

    if (!ext || !validExtensions.includes(ext)) {
      setProcessingState({
        stage: "error",
        progress: 0,
        message: `Invalid file type. Supported: ${validExtensions.join(", ")}`,
      });
      return { success: false, needsCalibration: false, templateId: null };
    }

    // Reset previous state
    resetData();
    clearCurve();
    setDetectedTemplate(null);
    setGridCalibration(null);

    // Set new image path
    setImagePath(filePath);
    setProcessingState({
      stage: "preprocessing",
      progress: 10,
      message: "Loading image...",
    });

    let imageWidth = 0;
    let imageHeight = 0;

    // Step 1: Load the original image for preview
    try {
      const result = await invoke<PreviewResponse>("preview_grid", {
        imagePath: filePath,
        algorithm: 0, // 0 = original image only
      });

      if (result.success && result.preview_image) {
        setOriginalImage(result.preview_image);
        // Set image dimensions
        if (result.image_width && result.image_height) {
          imageWidth = result.image_width;
          imageHeight = result.image_height;
          setImageDimensions(imageWidth, imageHeight);
        }
      } else {
        setProcessingState({
          stage: "error",
          progress: 0,
          message: `Failed to load image: ${result.error || "Unknown error"}`,
        });
        return { success: false, needsCalibration: false, templateId: null };
      }
    } catch (loadErr) {
      setProcessingState({
        stage: "error",
        progress: 0,
        message: `Error loading image: ${loadErr}`,
      });
      return { success: false, needsCalibration: false, templateId: null };
    }

    // Step 2: Detect template
    setProcessingState({
      stage: "preprocessing",
      progress: 30,
      message: "Detecting template...",
    });

    let templateId: string | null = null;
    try {
      const templateResult = await invoke<DetectTemplateResponse>("detect_template", {
        imagePath: filePath,
      });

      if (templateResult.success && templateResult.template_id) {
        templateId = templateResult.template_id;
        setDetectedTemplate({
          templateId: templateResult.template_id,
          chartType: templateResult.chart_type ?? "unknown",
          confidence: templateResult.confidence ?? 0,
          period: templateResult.period ?? "unknown",
          gridColor: templateResult.grid_color ?? "unknown",
        });
      }
    } catch (err) {
      console.error("Template detection error:", err);
    }

    // Step 3: Check if calibration exists for template
    let hasCalibration = false;

    if (templateId) {
      setProcessingState({
        stage: "preprocessing",
        progress: 60,
        message: "Checking calibration...",
      });

      try {
        const calibResult = await invoke<GetCalibrationResponse>("get_calibration", {
          templateId,
        });

        if (calibResult.success && calibResult.exists && calibResult.derived) {
          hasCalibration = true;
        }
      } catch (err) {
        console.error("Calibration check error:", err);
      }
    }

    // Done
    const needsCalibration = templateId !== null && !hasCalibration && imageWidth > 0 && imageHeight > 0;

    setProcessingState({
      stage: "idle",
      progress: 0,
      message: hasCalibration
        ? `Loaded: ${templateId} - Mark anchor point`
        : needsCalibration
          ? `Loaded: ${templateId} - Calibration needed`
          : "Image loaded",
    });

    // Don't auto-open alignment modal - user can click "Align" button when needed

    return { success: true, needsCalibration, templateId };
  }, [setImagePath, setOriginalImage, setProcessingState, setImageDimensions, setDetectedTemplate, setGridCalibration, resetData, clearCurve]);

  return { loadImageFromPath };
}

export default useImageLoader;
