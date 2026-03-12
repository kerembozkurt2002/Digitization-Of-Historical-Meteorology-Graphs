/**
 * CalibrationModal - Full-screen modal for comprehensive grid calibration.
 *
 * Alignment Mode: Mark 2 points (anchor + end of horizontal) to apply existing calibration
 * Full Calibration: 7-step process for new calibration
 *   Steps 1-3: Horizontal (rotation + spacing)
 *   Steps 4-7: Vertical (curvature + spacing)
 */

import { useCallback, useEffect, useState } from "react";
import { invoke } from "@tauri-apps/api/core";
import { useCalibrationStore, CALIBRATION_STEPS } from "../../stores/calibrationStore";
import { useImageStore } from "../../stores/imageStore";
import { useProcessing } from "../../hooks/useProcessing";
import { CalibrationCanvas } from "./CalibrationCanvas";
import { TEMPLATES } from "../Sidebar/TemplateSelector";
import { rotateImage } from "../../utils/imageRotation";
import type { SaveCalibrationResponse } from "../../types";
import "./CalibrationModal.css";

export function CalibrationModal() {
  const {
    isOpen,
    phase,
    currentStep,
    templateId,
    imageWidth,
    imageHeight,
    zoom,
    rotationAngle,
    // Alignment mode data
    savedCalibration,
    alignmentPoint,
    alignmentEndPoint,
    calculateAlignmentRotation,
    clearAlignmentPoint,
    clearAlignmentEndPoint,
    startFullCalibration,
    // Horizontal data (steps 1-3)
    horizontalTop,
    horizontalEndPoint,
    horizontalTopTemp,
    horizontalSpacing,
    // Vertical data (steps 4-7)
    verticalLine1Top,
    verticalLine1Bottom,
    verticalLine1Hour,
    verticalLine1Minute,
    verticalSpacing,
    centerY,
    curvature,
    // Actions
    closeModal,
    startCalibration,
    nextStep,
    prevStep,
    setHorizontalTopTemp,
    setHorizontalSpacing,
    setVerticalLine1Hour,
    setVerticalLine1Minute,
    setVerticalSpacing,
    setCenterY,
    setCurvature,
    setZoom,
    resetCalibration,
    setTemplateId,
  } = useCalibrationStore();

  const { originalImage, setOriginalImage, setGridCalibration, setViewMode } = useImageStore();
  const { loadGridCalibration } = useProcessing();
  const [isSaving, setIsSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Alignment step derived from point state (no useState needed)
  // Step 1: waiting for first click (alignmentPoint === null)
  // Step 2: waiting for second click (alignmentPoint !== null)
  const alignmentStep = alignmentPoint === null ? 1 : 2;

  // Format time for display
  const formatTimeDisplay = (hour: number, minute: number) => {
    return `${hour.toString().padStart(2, '0')}:${minute.toString().padStart(2, '0')}`;
  };

  // Convert radians to degrees for display
  const radToDeg = (rad: number) => (rad * 180 / Math.PI).toFixed(2);

  const [isApplyingAlignment, setIsApplyingAlignment] = useState(false);

  // Handle alignment apply - rotate image first, then apply grid
  const handleApplyAlignment = useCallback(async () => {
    if (!alignmentPoint || !alignmentEndPoint || !savedCalibration || !originalImage) return;

    const {
      verticalSpacing,
      horizontalSpacing,
      curvature,
      centerY: origCenterY,
      topPoint: origTop,
      bottomPoint: origBottom,
    } = savedCalibration;

    // Calculate rotation from the two alignment points
    const rotation = calculateAlignmentRotation();

    setIsApplyingAlignment(true);

    try {
      // Rotate image around alignmentPoint (first click)
      if (rotation !== 0) {
        const result = await rotateImage(
          originalImage,
          rotation,
          alignmentPoint.x,
          alignmentPoint.y
        );
        setOriginalImage(result.rotatedImage);
      }

      // After rotation, alignmentPoint stays the same (it's the center)
      // topPoint = alignmentPoint
      // bottomPoint = alignmentPoint + original offset (no rotation needed, image is already rotated)
      const origDx = origBottom.x - origTop.x;
      const origDy = origBottom.y - origTop.y;

      const newTopPoint = { x: alignmentPoint.x, y: alignmentPoint.y };
      const newBottomPoint = {
        x: alignmentPoint.x + origDx,
        y: alignmentPoint.y + origDy,
      };

      const origCenterOffset = origCenterY - origTop.y;
      const newCenterY = alignmentPoint.y + origCenterOffset;

      // Generate vertical line positions (to the right only)
      const verticalPositions: number[] = [];
      let x = alignmentPoint.x;
      while (x <= imageWidth + verticalSpacing) {
        if (x >= 0 && x <= imageWidth) {
          verticalPositions.push(x);
        }
        x += verticalSpacing;
      }

      // Generate horizontal line positions (starting from alignment Y, going down)
      const horizontalPositions: number[] = [];
      let y = alignmentPoint.y;
      while (y <= imageHeight + horizontalSpacing) {
        if (y >= 0 && y <= imageHeight) {
          horizontalPositions.push(y);
        }
        y += horizontalSpacing;
      }

      // Update grid calibration in image store
      setGridCalibration({
        topPoint: newTopPoint,
        bottomPoint: newBottomPoint,
        curveCenterY: newCenterY,
        curvature: curvature,
        lineSpacing: verticalSpacing,
        linePositions: verticalPositions,
        horizontalSpacing: horizontalSpacing,
        horizontalPositions: horizontalPositions,
        horizontalTopTemp: savedCalibration.referenceTemp,
        calibratedAt: new Date().toISOString(),
      });

      // Switch to grid view after alignment
      setViewMode("original");
      closeModal();
    } catch (err) {
      console.error("Failed to apply alignment:", err);
    } finally {
      setIsApplyingAlignment(false);
    }
  }, [alignmentPoint, alignmentEndPoint, savedCalibration, originalImage, imageWidth, imageHeight, setOriginalImage, setGridCalibration, setViewMode, closeModal, calculateAlignmentRotation]);

  // Handle alignment back button
  // Priority: clear endPoint first, then clear alignmentPoint
  const handleAlignmentBack = useCallback(() => {
    if (alignmentEndPoint) {
      // Second point exists -> clear it (stays in step 2 since alignmentPoint still exists)
      clearAlignmentEndPoint();
    } else if (alignmentPoint) {
      // Only first point exists -> clear it (goes to step 1)
      clearAlignmentPoint();
    }
  }, [alignmentPoint, alignmentEndPoint, clearAlignmentEndPoint, clearAlignmentPoint]);

  const canProceed = useCallback(() => {
    switch (currentStep) {
      case 1: // Horizontal top point + temp
        return horizontalTop !== null;
      case 2: // Horizontal end point
        return horizontalEndPoint !== null;
      case 3: // Horizontal spacing slider
        return true;
      case 4: // Vertical top point + time
        return verticalLine1Top !== null;
      case 5: // Vertical bottom point
        return verticalLine1Bottom !== null;
      case 6: // Curvature slider
        return true;
      case 7: // Vertical spacing slider
        return true;
      default:
        return false;
    }
  }, [currentStep, horizontalTop, horizontalEndPoint, verticalLine1Top, verticalLine1Bottom]);

  const handleSave = useCallback(async () => {
    if (!templateId) return;

    setIsSaving(true);
    setError(null);

    try {
      const hTop = horizontalTop!;
      const hEnd = horizontalEndPoint!;
      const v1Top = verticalLine1Top!;
      const v1Bottom = verticalLine1Bottom!;

      // Format time as "HH:MM" string for backend
      const formatTime = (hour: number, minute: number) =>
        `${hour.toString().padStart(2, '0')}:${minute.toString().padStart(2, '0')}`;

      const result = await invoke<SaveCalibrationResponse>("save_calibration_simple", {
        templateId,
        // Horizontal (for rotation)
        horizontalTop: hTop,
        horizontalEndPoint: hEnd,
        horizontalTopTemp,
        horizontalSpacing,
        rotationAngle,
        // Vertical
        verticalLine1Top: v1Top,
        verticalLine1Bottom: v1Bottom,
        verticalLine1Hour: formatTime(verticalLine1Hour, verticalLine1Minute),
        centerY,
        curvature,
        verticalSpacing,
        // Image
        imageWidth,
        imageHeight,
      });

      if (result.success) {
        await loadGridCalibration(templateId);
        // Switch to grid view after calibration
        setViewMode("original");
        closeModal();
      } else {
        setError(result.error || "Failed to save calibration");
      }
    } catch (err) {
      setError(String(err));
    } finally {
      setIsSaving(false);
    }
  }, [
    templateId, imageWidth, imageHeight,
    horizontalTop, horizontalEndPoint, horizontalTopTemp, horizontalSpacing, rotationAngle,
    verticalLine1Top, verticalLine1Bottom, verticalLine1Hour, verticalLine1Minute,
    centerY, curvature, verticalSpacing,
    closeModal, loadGridCalibration, setViewMode
  ]);

  const [isRotating, setIsRotating] = useState(false);

  const handleNext = useCallback(async () => {
    if (currentStep === 7 && canProceed()) {
      handleSave();
    } else if (canProceed()) {
      // Step 2 -> Step 3: Rotate image before proceeding to vertical calibration
      if (currentStep === 2 && horizontalTop && rotationAngle !== 0 && originalImage) {
        setIsRotating(true);
        try {
          const result = await rotateImage(
            originalImage,
            rotationAngle,
            horizontalTop.x,
            horizontalTop.y
          );
          setOriginalImage(result.rotatedImage);
        } catch (err) {
          console.error("Failed to rotate image:", err);
        } finally {
          setIsRotating(false);
        }
      }
      nextStep();
    }
  }, [currentStep, canProceed, nextStep, handleSave, horizontalTop, rotationAngle, originalImage, setOriginalImage]);

  const handleZoomIn = useCallback(() => setZoom(zoom + 0.25), [zoom, setZoom]);
  const handleZoomOut = useCallback(() => setZoom(zoom - 0.25), [zoom, setZoom]);

  // Keyboard shortcuts
  useEffect(() => {
    if (!isOpen) return;

    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === "Escape") {
        closeModal();
      } else if (e.key === "Enter" && canProceed()) {
        handleNext();
      } else if (e.key === "+" || e.key === "=") {
        handleZoomIn();
      } else if (e.key === "-") {
        handleZoomOut();
      }
    };

    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [isOpen, closeModal, canProceed, handleNext, handleZoomIn, handleZoomOut]);

  if (!isOpen) return null;

  // Alignment phase - mark 2 points to apply existing calibration
  if (phase === "alignment" && savedCalibration) {
    const refTime = formatTimeDisplay(savedCalibration.referenceHour, savedCalibration.referenceMinute);
    const refTemp = savedCalibration.referenceTemp;
    const alignRotation = alignmentPoint && alignmentEndPoint ? calculateAlignmentRotation() : 0;

    return (
      <div className="calibration-modal-overlay">
        <div className="calibration-modal">
          {/* Header */}
          <div className="calibration-header">
            <div className="calibration-title">
              <h2>Align Grid</h2>
              <span className="template-badge">{templateId}</span>
              <span className="phase-badge alignment">Alignment</span>
            </div>
            <button className="close-btn" onClick={closeModal} title="Close (Esc)">
              ×
            </button>
          </div>

          {/* Progress */}
          <div className="calibration-progress">
            <div className="progress-bar">
              <div
                className="progress-fill"
                style={{ width: `${(alignmentStep / 2) * 100}%` }}
              />
            </div>
            <span className="progress-text">Step {alignmentStep} of 2</span>
          </div>

          {/* Instructions */}
          <div className="calibration-instructions alignment-instructions">
            <div className="alignment-info">
              {alignmentStep === 1 ? (
                <>
                  <span className="alignment-label">Step 1: Click the anchor point</span>
                  <div className="alignment-hint">({refTemp}°C at {refTime})</div>
                </>
              ) : (
                <>
                  <span className="alignment-label">Step 2: Click the RIGHT end of the same horizontal line</span>
                  <div className="alignment-hint">(for rotation alignment)</div>
                </>
              )}
            </div>
            {alignmentPoint && (
              <div className="alignment-status">
                Anchor: ({Math.round(alignmentPoint.x)}, {Math.round(alignmentPoint.y)})
                {alignmentEndPoint && (
                  <> | End: ({Math.round(alignmentEndPoint.x)}, {Math.round(alignmentEndPoint.y)})
                  | Rotation: {radToDeg(alignRotation)}°</>
                )}
              </div>
            )}
          </div>

          {/* Canvas */}
          <div className="calibration-canvas-container">
            {originalImage && (
              <CalibrationCanvas
                imageData={originalImage}
                width={imageWidth}
                height={imageHeight}
              />
            )}
          </div>

          {/* Footer */}
          <div className="calibration-footer">
            <div className="zoom-controls">
              <button className="btn btn-small" onClick={() => setZoom(zoom - 0.25)} disabled={zoom <= 0.1}>
                −
              </button>
              <span className="zoom-level">{Math.round(zoom * 100)}%</span>
              <button className="btn btn-small" onClick={() => setZoom(zoom + 0.25)} disabled={zoom >= 3.0}>
                +
              </button>
            </div>

            <div className="action-buttons">
              <button className="btn btn-small" onClick={startFullCalibration}>
                Re-calibrate
              </button>
              <button
                className="btn btn-secondary"
                onClick={handleAlignmentBack}
                disabled={!alignmentPoint}
              >
                Back
              </button>
              <button className="btn btn-secondary" onClick={closeModal}>
                Cancel
              </button>
              <button
                className="btn btn-primary"
                onClick={handleApplyAlignment}
                disabled={!alignmentPoint || !alignmentEndPoint || isApplyingAlignment}
              >
                Apply Grid
              </button>
            </div>
          </div>
        </div>
      </div>
    );
  }

  // Prompt phase - show simple popup
  if (phase === "prompt") {
    return (
      <div className="calibration-modal-overlay">
        <div className="calibration-prompt">
          <div className="prompt-icon">⚠</div>
          <h2>Calibration Required</h2>
          <p>
            This template needs to be calibrated before grid lines can be displayed.
          </p>
          <div className="template-selector">
            <label>Template:</label>
            <select
              value={templateId || ""}
              onChange={(e) => setTemplateId(e.target.value)}
              className="template-select"
            >
              {Object.entries(TEMPLATES).map(([id, meta]) => (
                <option key={id} value={id}>
                  {id} ({meta.chartType} · {meta.period})
                </option>
              ))}
            </select>
          </div>
          <div className="prompt-buttons">
            <button className="btn btn-secondary" onClick={closeModal}>
              Cancel
            </button>
            <button className="btn btn-primary" onClick={startCalibration}>
              Start Calibration
            </button>
          </div>
        </div>
      </div>
    );
  }

  const stepInfo = CALIBRATION_STEPS[currentStep];
  const isHorizontalSpacingStep = currentStep === 3;
  const isCurvatureSliderStep = currentStep === 6;
  const isVerticalSpacingStep = currentStep === 7;

  // Slider ranges
  const centerYMin = -imageHeight;
  const centerYMax = imageHeight * 2;
  const curvatureMin = -200;
  const curvatureMax = 200;
  const spacingMin = 5;
  const spacingMax = 100;

  return (
    <div className="calibration-modal-overlay">
      <div className="calibration-modal">
        {/* Header */}
        <div className="calibration-header">
          <div className="calibration-title">
            <h2>Grid Calibration</h2>
            <span className="template-badge">{templateId}</span>
            <span className={`phase-badge ${phase}`}>
              {phase === "horizontal" ? "Horizontal" : phase === "vertical" ? "Vertical" : "Complete"}
            </span>
          </div>
          <button className="close-btn" onClick={closeModal} title="Close (Esc)">
            ×
          </button>
        </div>

        {/* Progress */}
        <div className="calibration-progress">
          <div className="progress-bar">
            <div
              className="progress-fill"
              style={{ width: `${(currentStep / 7) * 100}%` }}
            />
          </div>
          <span className="progress-text">Step {currentStep} of 7</span>
        </div>

        {/* Instructions */}
        <div className="calibration-instructions">
          <div className="step-info">
            <span className="step-number">Step {currentStep}:</span>
            <span className="step-text">{stepInfo?.instruction}</span>
          </div>

          {/* Temperature input for step 1 */}
          {currentStep === 1 && (
            <div className="step-input">
              <label>Temp °C:</label>
              <input
                type="number"
                value={horizontalTopTemp}
                onChange={(e) => setHorizontalTopTemp(Number(e.target.value) || 0)}
                className="input-field"
              />
            </div>
          )}

          {/* Rotation info for step 2 */}
          {currentStep === 2 && horizontalTop && (
            <div className="step-input">
              <span className="rotation-info">
                Start: ({Math.round(horizontalTop.x)}, {Math.round(horizontalTop.y)})
                {horizontalEndPoint && (
                  <> | End: ({Math.round(horizontalEndPoint.x)}, {Math.round(horizontalEndPoint.y)})
                  | Rotation: {radToDeg(rotationAngle)}°</>
                )}
              </span>
            </div>
          )}

          {/* Time input for step 4 */}
          {currentStep === 4 && (
            <div className="step-input time-input">
              <label>Time:</label>
              <input
                type="number"
                min={0}
                max={23}
                value={verticalLine1Hour}
                onChange={(e) => setVerticalLine1Hour(Number(e.target.value) || 0)}
                className="input-field input-hour"
              />
              <span className="time-separator">:</span>
              <input
                type="number"
                min={0}
                max={59}
                value={verticalLine1Minute}
                onChange={(e) => setVerticalLine1Minute(Number(e.target.value) || 0)}
                className="input-field input-minute"
              />
            </div>
          )}
        </div>

        {/* Horizontal Spacing Slider - step 3 */}
        {isHorizontalSpacingStep && (
          <div className="calibration-sliders">
            <div className="slider-group">
              <label>
                Horizontal Spacing:
                <input
                  type="number"
                  min={spacingMin}
                  max={spacingMax}
                  step={0.01}
                  value={horizontalSpacing.toFixed(2)}
                  onChange={(e) => setHorizontalSpacing(Number(e.target.value))}
                  onWheel={(e) => {
                    e.preventDefault();
                    const delta = e.deltaY > 0 ? -0.01 : 0.01;
                    setHorizontalSpacing(Math.max(spacingMin, Math.min(spacingMax, horizontalSpacing + delta)));
                  }}
                  className="slider-input"
                />
                <span className="slider-unit">px</span>
              </label>
              <input
                type="range"
                min={spacingMin}
                max={spacingMax}
                step={0.01}
                value={horizontalSpacing}
                onChange={(e) => setHorizontalSpacing(Number(e.target.value))}
                className="slider"
              />
              <div className="slider-hints">
                <span>5 px</span>
                <span>50 px</span>
                <span>100 px</span>
              </div>
            </div>
            {rotationAngle !== 0 && (
              <div className="rotation-applied">
                Rotation applied: {radToDeg(rotationAngle)}°
              </div>
            )}
          </div>
        )}

        {/* Curvature Sliders - step 6 */}
        {isCurvatureSliderStep && (
          <div className="calibration-sliders">
            <div className="slider-group">
              <label>
                Bend Center (Y):
                <input
                  type="number"
                  min={centerYMin}
                  max={centerYMax}
                  step={1}
                  value={Math.round(centerY)}
                  onChange={(e) => setCenterY(Number(e.target.value))}
                  onWheel={(e) => {
                    e.preventDefault();
                    const delta = e.deltaY > 0 ? -1 : 1;
                    setCenterY(Math.max(centerYMin, Math.min(centerYMax, centerY + delta)));
                  }}
                  className="slider-input"
                />
              </label>
              <input
                type="range"
                min={centerYMin}
                max={centerYMax}
                step={1}
                value={centerY}
                onChange={(e) => setCenterY(Number(e.target.value))}
                className="slider"
              />
              <div className="slider-hints">
                <span>Above image</span>
                <span>Below image</span>
              </div>
            </div>

            <div className="slider-group">
              <label>
                Curvature:
                <input
                  type="number"
                  min={curvatureMin}
                  max={curvatureMax}
                  step={0.01}
                  value={curvature.toFixed(2)}
                  onChange={(e) => setCurvature(Number(e.target.value))}
                  onWheel={(e) => {
                    e.preventDefault();
                    const delta = e.deltaY > 0 ? -0.01 : 0.01;
                    setCurvature(Math.max(curvatureMin, Math.min(curvatureMax, curvature + delta)));
                  }}
                  className="slider-input"
                />
                <span className="slider-unit">px</span>
              </label>
              <input
                type="range"
                min={curvatureMin}
                max={curvatureMax}
                step={0.01}
                value={curvature}
                onChange={(e) => setCurvature(Number(e.target.value))}
                className="slider"
              />
              <div className="slider-hints">
                <span>Curve left</span>
                <span>Straight</span>
                <span>Curve right</span>
              </div>
            </div>
          </div>
        )}

        {/* Vertical Spacing Slider - step 7 */}
        {isVerticalSpacingStep && (
          <div className="calibration-sliders">
            <div className="slider-group">
              <label>
                Vertical Spacing:
                <input
                  type="number"
                  min={spacingMin}
                  max={spacingMax}
                  step={0.01}
                  value={verticalSpacing.toFixed(2)}
                  onChange={(e) => setVerticalSpacing(Number(e.target.value))}
                  onWheel={(e) => {
                    e.preventDefault();
                    const delta = e.deltaY > 0 ? -0.01 : 0.01;
                    setVerticalSpacing(Math.max(spacingMin, Math.min(spacingMax, verticalSpacing + delta)));
                  }}
                  className="slider-input"
                />
                <span className="slider-unit">px</span>
              </label>
              <input
                type="range"
                min={spacingMin}
                max={spacingMax}
                step={0.01}
                value={verticalSpacing}
                onChange={(e) => setVerticalSpacing(Number(e.target.value))}
                className="slider"
              />
              <div className="slider-hints">
                <span>5 px</span>
                <span>50 px</span>
                <span>100 px</span>
              </div>
            </div>
          </div>
        )}

        {/* Canvas */}
        <div className="calibration-canvas-container">
          {originalImage && (
            <CalibrationCanvas
              imageData={originalImage}
              width={imageWidth}
              height={imageHeight}
            />
          )}
        </div>

        {/* Footer */}
        <div className="calibration-footer">
          <div className="zoom-controls">
            <button className="btn btn-small" onClick={handleZoomOut} disabled={zoom <= 0.1}>
              −
            </button>
            <span className="zoom-level">{Math.round(zoom * 100)}%</span>
            <button className="btn btn-small" onClick={handleZoomIn} disabled={zoom >= 3.0}>
              +
            </button>
          </div>

          {error && <span className="error-message">{error}</span>}

          <div className="action-buttons">
            <button className="btn btn-small" onClick={resetCalibration}>
              Reset
            </button>
            <button
              className="btn btn-secondary"
              onClick={prevStep}
              disabled={currentStep === 1}
            >
              Back
            </button>
            <button
              className="btn btn-primary"
              onClick={handleNext}
              disabled={!canProceed() || isSaving || isRotating}
            >
              {currentStep === 7
                ? (isSaving ? "Saving..." : "Finish")
                : (isRotating ? "Rotating..." : "Next")}
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}

export default CalibrationModal;
