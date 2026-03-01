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
    setOriginalImage,
    setOverlayImage,
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
      message: "Loading original...",
    });

    try {
      // Get original image (algorithm 0)
      const originalResult = await invoke<PreviewResponse>("preview_grid", {
        imagePath: imagePath,
        algorithm: 0,
      });

      if (originalResult.success && originalResult.preview_image) {
        setOriginalImage(originalResult.preview_image);
      }

      setProcessingState({
        stage: "dewarping",
        progress: 50,
        message: "Detecting horizontal grid lines...",
      });

      // Adaptive morphological algorithm (algorithm 4)
      const adaptiveResult = await invoke<PreviewResponse>("preview_grid", {
        imagePath: imagePath,
        algorithm: 4,
      });

      if (adaptiveResult.success && adaptiveResult.preview_image) {
        setOverlayImage(adaptiveResult.preview_image);
      }

      setProcessingState({
        stage: "complete",
        progress: 100,
        message: `Done! Horizontal lines: ${adaptiveResult.horizontal_lines ?? 0}. Press 1 for original, 2 for Adaptive-H.`,
      });

      setViewMode("adaptiveH");
    } catch (err) {
      setProcessingState({
        stage: "error",
        progress: 0,
        message: `Error: ${err}`,
        error: String(err),
      });
    }
  }, [imagePath, setOriginalImage, setOverlayImage, setProcessingState, setViewMode]);

  return {
    processGridDetection,
    isProcessing,
  };
}

export default useProcessing;
