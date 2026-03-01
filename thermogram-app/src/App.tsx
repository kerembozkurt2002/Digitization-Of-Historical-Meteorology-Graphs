import { useEffect } from "react";
import { useImageStore, selectCurrentImage } from "./stores/imageStore";
import { UploadPanel } from "./components/Sidebar/UploadPanel";
import { CalibrationPanel } from "./components/Sidebar/CalibrationPanel";
import { useProcessing } from "./hooks/useProcessing";
import type { ViewMode } from "./types";
import "./App.css";

function App() {
  const {
    imagePath,
    originalImage,
    horizontalImage,
    verticalImage,
    combinedImage,
    viewMode,
    setViewMode,
    processing,
  } = useImageStore();

  const currentImage = useImageStore(selectCurrentImage);
  const { processGridDetection, isProcessing } = useProcessing();

  // Keyboard shortcuts for switching views (1-4)
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (
        e.target instanceof HTMLInputElement ||
        e.target instanceof HTMLTextAreaElement
      ) {
        return;
      }

      switch (e.key) {
        case "1":
          if (originalImage) setViewMode("original");
          break;
        case "2":
          if (horizontalImage) setViewMode("horizontal");
          break;
        case "3":
          if (verticalImage) setViewMode("vertical");
          break;
        case "4":
          if (combinedImage) setViewMode("combined");
          break;
      }
    };

    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [originalImage, horizontalImage, verticalImage, combinedImage, setViewMode]);

  const isViewActive = (mode: ViewMode): boolean => viewMode === mode;

  return (
    <div className="app">
      <header className="header">
        <h1>Thermogram Digitizer</h1>
        <p className="subtitle">
          Kandilli Observatory Historical Data Digitization
        </p>
      </header>

      <div className="main-layout">
        <aside className="sidebar">
          <UploadPanel />

          <CalibrationPanel />

          <div className="panel">
            <h2>Process</h2>
            <button
              onClick={processGridDetection}
              disabled={!imagePath || isProcessing}
              className="btn btn-primary"
            >
              {isProcessing ? "Processing..." : "Detect Grid"}
            </button>
          </div>

          <div className="panel">
            <h2>View (1-4)</h2>
            <div className="view-buttons">
              <button
                onClick={() => setViewMode("original")}
                disabled={!originalImage}
                className={`btn ${isViewActive("original") ? "btn-active" : ""}`}
                title="Original image"
              >
                1. Original
              </button>
              <button
                onClick={() => setViewMode("horizontal")}
                disabled={!horizontalImage}
                className={`btn ${isViewActive("horizontal") ? "btn-active" : ""}`}
                title="Horizontal grid lines (green)"
              >
                2. H-Lines
              </button>
              <button
                onClick={() => setViewMode("vertical")}
                disabled={!verticalImage}
                className={`btn ${isViewActive("vertical") ? "btn-active" : ""}`}
                title="Vertical grid lines (blue)"
              >
                3. V-Lines
              </button>
              <button
                onClick={() => setViewMode("combined")}
                disabled={!combinedImage}
                className={`btn ${isViewActive("combined") ? "btn-active" : ""}`}
                title="Both horizontal and vertical lines"
              >
                4. Combined
              </button>
            </div>
          </div>

          <div className="panel status-panel">
            <h2>Status</h2>
            <p className="status-text">{processing.message || "Ready"}</p>
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
          ) : (
            <div className="placeholder">
              <p>Select an image to begin</p>
              <p className="hint">Supported formats: TIFF, PNG, JPG</p>
            </div>
          )}
        </main>
      </div>
    </div>
  );
}

export default App;
