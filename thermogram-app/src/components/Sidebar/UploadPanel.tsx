/**
 * UploadPanel Component - Handles image selection and upload.
 */

import { useCallback } from "react";
import { open } from "@tauri-apps/plugin-dialog";
import { useImageStore } from "../../stores/imageStore";
import { useImageLoader } from "../../hooks/useImageLoader";

interface UploadPanelProps {
  className?: string;
}

export function UploadPanel({ className = "" }: UploadPanelProps) {
  const { imagePath, setProcessingState } = useImageStore();
  const { loadImageFromPath } = useImageLoader();

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
        await loadImageFromPath(selected as string);
      }
    } catch (err) {
      setProcessingState({
        stage: "error",
        progress: 0,
        message: `Error selecting file: ${err}`,
        error: String(err),
      });
    }
  }, [loadImageFromPath, setProcessingState]);

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
