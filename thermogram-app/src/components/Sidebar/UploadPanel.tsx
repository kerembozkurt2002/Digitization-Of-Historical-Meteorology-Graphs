/**
 * UploadPanel Component - Handles image selection and upload.
 */

import { useCallback } from "react";
import { open } from "@tauri-apps/plugin-dialog";
import { useImageStore } from "../../stores/imageStore";
import { useDataStore } from "../../stores/dataStore";

interface UploadPanelProps {
  className?: string;
}

export function UploadPanel({ className = "" }: UploadPanelProps) {
  const { imagePath, setImagePath, setProcessingState } = useImageStore();
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
          stage: "idle",
          progress: 0,
          message: "Image selected. Click 'Detect Grid' to process.",
        });
      }
    } catch (err) {
      setProcessingState({
        stage: "error",
        progress: 0,
        message: `Error selecting file: ${err}`,
        error: String(err),
      });
    }
  }, [setImagePath, setProcessingState, resetData]);

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
