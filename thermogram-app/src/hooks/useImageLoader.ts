/**
 * useImageLoader Hook - Handles image loading from file path.
 */

import { useCallback } from "react";
import { invoke } from "@tauri-apps/api/core";
import { useImageStore } from "../stores/imageStore";
import { useDataStore } from "../stores/dataStore";
import type { PreviewResponse } from "../types";

export function useImageLoader() {
  const { setImagePath, setOriginalImage, setProcessingState } = useImageStore();
  const { reset: resetData } = useDataStore();

  const loadImageFromPath = useCallback(async (filePath: string) => {
    // Validate file extension
    const ext = filePath.split(".").pop()?.toLowerCase();
    const validExtensions = ["tif", "tiff", "png", "jpg", "jpeg"];

    if (!ext || !validExtensions.includes(ext)) {
      setProcessingState({
        stage: "error",
        progress: 0,
        message: `Invalid file type. Supported: ${validExtensions.join(", ")}`,
      });
      return false;
    }

    // Reset previous state
    resetData();

    // Set new image path
    setImagePath(filePath);
    setProcessingState({
      stage: "preprocessing",
      progress: 10,
      message: "Loading image...",
    });

    // Load the original image for preview
    try {
      const result = await invoke<PreviewResponse>("preview_grid", {
        imagePath: filePath,
        algorithm: 0, // 0 = original image only
      });

      if (result.success && result.preview_image) {
        setOriginalImage(result.preview_image);
        setProcessingState({
          stage: "idle",
          progress: 0,
          message: "Image loaded. Adjust calibration values, then click 'Detect Grid'.",
        });
        return true;
      } else {
        setProcessingState({
          stage: "error",
          progress: 0,
          message: `Failed to load image: ${result.error || "Unknown error"}`,
        });
        return false;
      }
    } catch (loadErr) {
      setProcessingState({
        stage: "error",
        progress: 0,
        message: `Error loading image: ${loadErr}`,
      });
      return false;
    }
  }, [setImagePath, setOriginalImage, setProcessingState, resetData]);

  return { loadImageFromPath };
}

export default useImageLoader;
