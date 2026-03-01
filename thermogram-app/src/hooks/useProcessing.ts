/**
 * useProcessing Hook - Handles image processing operations.
 */

import { useCallback } from "react";
import { invoke } from "@tauri-apps/api/core";
import { useImageStore, selectIsProcessing } from "../stores/imageStore";
import type { PreviewResponse } from "../types";

export function useProcessing() {
  const {
    imagePath,
    calibration,
    chartType,
    setOriginalImage,
    setHorizontalImage,
    setVerticalImage,
    setCombinedImage,
    setProcessingState,
    setViewMode,
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

      // Get vertical lines (mode 5)
      const verticalResult = await invoke<PreviewResponse>("preview_grid", {
        imagePath: imagePath,
        algorithm: 5,
      });

      if (verticalResult.success && verticalResult.preview_image) {
        setVerticalImage(verticalResult.preview_image);
      }

      setProcessingState({
        stage: "calibrating",
        progress: 70,
        message: "Creating combined view...",
      });

      // Get combined view (mode 6)
      const combinedResult = await invoke<PreviewResponse>("preview_grid", {
        imagePath: imagePath,
        algorithm: 6,
      });

      if (combinedResult.success && combinedResult.preview_image) {
        setCombinedImage(combinedResult.preview_image);
      }

      const hLines = horizontalResult.horizontal_lines ?? 0;
      const vLines = verticalResult.vertical_lines ?? 0;

      setProcessingState({
        stage: "complete",
        progress: 100,
        message: `Done! H:${hLines} V:${vLines} | ${calibration.tempMin}°C - ${calibration.tempMax}°C, start ${calibration.startHour}:00`,
      });

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

  return {
    processGridDetection,
    isProcessing,
    calibration,
    chartType,
  };
}

export default useProcessing;
