/**
 * UploadPanel Component - Handles image selection and upload.
 */

import { useCallback } from "react";
import { open } from "@tauri-apps/plugin-dialog";
import { invoke } from "@tauri-apps/api/core";
import { useImageStore } from "../../stores/imageStore";
import { useDataStore } from "../../stores/dataStore";
import type { PreviewResponse } from "../../types";

interface UploadPanelProps {
  className?: string;
}

export function UploadPanel({ className = "" }: UploadPanelProps) {
  const { imagePath, setImagePath, setOriginalImage, setProcessingState } = useImageStore();
  const { reset: resetData } = useDataStore();

  const handleSelectImage = useCallback(async () => {
    try {
      const selected = await open({
        multiple: false,
        filters: [
          {
            name: "Images",
            extensions: ["tif", "tiff", "png", "jpg", "jpeg"],
          },
        ],
      });

      if (selected) {
        // Reset previous state
        resetData();

        // Set new image path
        setImagePath(selected as string);
        setProcessingState({
          stage: "preprocessing",
          progress: 10,
          message: "Loading image...",
        });

        // Immediately load the original image for preview
        try {
          const result = await invoke<PreviewResponse>("preview_grid", {
            imagePath: selected as string,
            algorithm: 0, // 0 = original image only
          });

          if (result.success && result.preview_image) {
            setOriginalImage(result.preview_image);
            setProcessingState({
              stage: "idle",
              progress: 0,
              message: "Image loaded. Adjust calibration values, then click 'Detect Grid'.",
            });
          } else {
            setProcessingState({
              stage: "error",
              progress: 0,
              message: `Failed to load image: ${result.error || "Unknown error"}`,
            });
          }
        } catch (loadErr) {
          setProcessingState({
            stage: "error",
            progress: 0,
            message: `Error loading image: ${loadErr}`,
          });
        }
      }
    } catch (err) {
      setProcessingState({
        stage: "error",
        progress: 0,
        message: `Error selecting file: ${err}`,
        error: String(err),
      });
    }
  }, [setImagePath, setOriginalImage, setProcessingState, resetData]);

  const filename = imagePath?.split("/").pop() ?? null;

  return (
    <div className={`panel upload-panel ${className}`}>
      <h2>Upload</h2>
      <button onClick={handleSelectImage} className="btn btn-primary">
        Select Image
      </button>
      {filename && (
        <p className="file-path" title={imagePath ?? undefined}>
          {filename}
        </p>
      )}
    </div>
  );
}

export default UploadPanel;
