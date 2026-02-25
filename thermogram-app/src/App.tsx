import { useState, useCallback, useEffect } from "react";
import { invoke } from "@tauri-apps/api/core";
import { open } from "@tauri-apps/plugin-dialog";
import "./App.css";

interface PreviewResponse {
  success: boolean;
  error?: string;
  message?: string;
  vertical_lines?: number;
  horizontal_lines?: number;
  preview_image?: string;
}

type ViewMode = "original" | "adaptiveH";

function App() {
  const [imagePath, setImagePath] = useState<string | null>(null);
  const [originalImage, setOriginalImage] = useState<string | null>(null);
  const [adaptiveHImage, setAdaptiveHImage] = useState<string | null>(null);
  const [processing, setProcessing] = useState(false);
  const [status, setStatus] = useState<string>("");
  const [gridInfo, setGridInfo] = useState<string>("");
  const [viewMode, setViewMode] = useState<ViewMode>("original");

  // Keyboard shortcuts for switching views (1, 2)
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.target instanceof HTMLInputElement || e.target instanceof HTMLTextAreaElement) {
        return;
      }

      switch (e.key) {
        case "1":
          if (originalImage) setViewMode("original");
          break;
        case "2":
          if (adaptiveHImage) setViewMode("adaptiveH");
          break;
      }
    };

    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [originalImage, adaptiveHImage]);

  const selectImage = useCallback(async () => {
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
        setImagePath(selected as string);
        setOriginalImage(null);
        setAdaptiveHImage(null);
        setStatus("Image selected. Click 'Detect Grid' to process.");
        setGridInfo("");
        setViewMode("original");
      }
    } catch (err) {
      setStatus(`Error selecting file: ${err}`);
    }
  }, []);

  const processAllViews = useCallback(async () => {
    if (!imagePath) {
      setStatus("Please select an image first.");
      return;
    }

    setProcessing(true);
    setStatus("Processing...");

    try {
      // Get original image
      setStatus("Loading original...");
      const originalResult = await invoke<PreviewResponse>("preview_grid", {
        imagePath: imagePath,
        algorithm: 0,
      });
      if (originalResult.success) {
        setOriginalImage(originalResult.preview_image || null);
      }

      // Adaptive-H algorithm
      setStatus("Detecting horizontal grid lines...");
      const adaptiveResult = await invoke<PreviewResponse>("preview_grid", {
        imagePath: imagePath,
        algorithm: 4,
      });
      if (adaptiveResult.success) {
        setAdaptiveHImage(adaptiveResult.preview_image || null);
        setGridInfo(`Horizontal lines: ${adaptiveResult.horizontal_lines}`);
      }

      setStatus("Done! Press 1 for original, 2 for Adaptive-H.");
      setViewMode("adaptiveH");
    } catch (err) {
      setStatus(`Error: ${err}`);
    } finally {
      setProcessing(false);
    }
  }, [imagePath]);

  const getCurrentImage = () => {
    switch (viewMode) {
      case "adaptiveH":
        return adaptiveHImage;
      default:
        return originalImage;
    }
  };

  const currentImage = getCurrentImage();

  return (
    <div className="app">
      <header className="header">
        <h1>Thermogram Digitizer</h1>
        <p className="subtitle">Kandilli Observatory Historical Data Digitization</p>
      </header>

      <div className="main-layout">
        <aside className="sidebar">
          <div className="panel">
            <h2>Upload</h2>
            <button onClick={selectImage} className="btn btn-primary">
              Select Image
            </button>
            {imagePath && (
              <p className="file-path" title={imagePath}>
                {imagePath.split("/").pop()}
              </p>
            )}
          </div>

          <div className="panel">
            <h2>Process</h2>
            <button
              onClick={processAllViews}
              disabled={!imagePath || processing}
              className="btn btn-primary"
            >
              {processing ? "Processing..." : "Detect Grid"}
            </button>
          </div>

          <div className="panel">
            <h2>View (1-2)</h2>
            <div className="view-buttons">
              <button
                onClick={() => setViewMode("original")}
                disabled={!originalImage}
                className={`btn ${viewMode === "original" ? "btn-active" : ""}`}
                title="Original file without any overlay"
              >
                1. Original
              </button>
              <button
                onClick={() => setViewMode("adaptiveH")}
                disabled={!adaptiveHImage}
                className={`btn ${viewMode === "adaptiveH" ? "btn-active" : ""}`}
                title="Adaptive Threshold + Morphological (Horizontal)"
              >
                2. Adaptive-H
              </button>
            </div>
          </div>

          <div className="panel status-panel">
            <h2>Status</h2>
            <p className="status-text">{status || "Ready"}</p>
            {gridInfo && <p className="grid-info">{gridInfo}</p>}
          </div>
        </aside>

        <main className="workspace">
          {currentImage ? (
            <div className="image-container">
              <img
                src={`data:image/png;base64,${currentImage}`}
                alt={viewMode}
                className="thermogram-image"
              />
            </div>
          ) : imagePath ? (
            <div className="placeholder">
              <p>Click "Detect Grid" to process the image</p>
            </div>
          ) : (
            <div className="placeholder">
              <p>Select an image to begin</p>
              <p className="hint">
                Supported formats: TIFF, PNG, JPG
              </p>
            </div>
          )}
        </main>
      </div>
    </div>
  );
}

export default App;
