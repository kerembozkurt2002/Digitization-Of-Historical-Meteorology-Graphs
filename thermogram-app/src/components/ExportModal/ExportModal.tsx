/**
 * Export Modal - UI for configuring and confirming curve data export.
 *
 * Shows:
 * - Chart info and settings
 * - Start date (parsed from filename) and time inputs
 * - Live CSV preview
 * - Export confirmation
 */

import { useState, useCallback, useMemo, useEffect } from "react";
import { useImageStore } from "../../stores/imageStore";
import { useCurveStore } from "../../stores/curveStore";
import {
  exportCurveData,
  generateExportData,
  exportToCSV,
  type ExportConfig,
} from "../../utils/exportCurve";
import { getTimeConfigForTemplate } from "../../utils/chartTimeConfig";
import type { GridCalibrationData } from "../../utils/gridLineData";
import "./ExportModal.css";

/**
 * Normalize Turkish characters to ASCII equivalents for matching.
 */
function normalizeTurkish(str: string): string {
  return str
    .toUpperCase()
    .replace(/Ğ/g, "G")
    .replace(/Ü/g, "U")
    .replace(/Ş/g, "S")
    .replace(/İ/g, "I")
    .replace(/Ö/g, "O")
    .replace(/Ç/g, "C")
    .replace(/I/g, "I") // Turkish dotless I
    .normalize("NFD")
    .replace(/[\u0300-\u036f]/g, ""); // Remove diacritics
}

/**
 * Turkish month name to month number (1-12) mapping.
 * Keys are normalized (ASCII only).
 */
const TURKISH_MONTHS: Record<string, number> = {
  "OCAK": 1,
  "SUBAT": 2,
  "MART": 3,
  "NISAN": 4,
  "MAYIS": 5,
  "HAZIRAN": 6,
  "TEMMUZ": 7,
  "AGUSTOS": 8,
  "EYLUL": 9,
  "EKIM": 10,
  "KASIM": 11,
  "ARALIK": 12,
};

/**
 * Parse date from filename in format: YYYY_MONTH-DD.tif
 */
function parseDateFromFilename(filepath: string | null): string | null {
  if (!filepath) {
    console.log("[ExportModal] No filepath provided");
    return null;
  }

  const filename = filepath.split("/").pop()?.split("\\").pop() ?? "";
  console.log("[ExportModal] Parsing filename:", filename);

  const match = filename.match(/(\d{4})_([^-]+)-(\d{1,2})/);
  if (!match) {
    console.log("[ExportModal] No match for date pattern");
    return null;
  }

  const [, yearStr, monthStr, dayStr] = match;
  console.log("[ExportModal] Parsed:", { yearStr, monthStr, dayStr });

  const year = parseInt(yearStr, 10);
  const normalizedMonth = normalizeTurkish(monthStr);
  const monthNum = TURKISH_MONTHS[normalizedMonth];
  const day = parseInt(dayStr, 10);

  console.log("[ExportModal] Month lookup:", monthStr, "->", normalizedMonth, "->", monthNum);

  if (!monthNum || isNaN(year) || isNaN(day)) {
    console.log("[ExportModal] Invalid parsed values");
    return null;
  }

  const month = monthNum.toString().padStart(2, "0");
  const dayPadded = day.toString().padStart(2, "0");
  const result = `${year}-${month}-${dayPadded}`;
  console.log("[ExportModal] Parsed date:", result);
  return result;
}

interface ExportModalProps {
  isOpen: boolean;
  onClose: () => void;
  onExportSuccess?: () => void;
}

export function ExportModal({ isOpen, onClose, onExportSuccess }: ExportModalProps) {
  const { gridCalibration, detectedTemplate, imagePath } = useImageStore();
  const { points: curvePoints, rawPoints: curveRawPoints } = useCurveStore();

  // Debug: log imagePath whenever modal is open
  console.log("[ExportModal] isOpen:", isOpen, "imagePath:", imagePath);

  // Initialize date from filename or today's date (stored as YYYY-MM-DD)
  const [startDate, setStartDate] = useState<string>(() => {
    const parsedDate = parseDateFromFilename(imagePath);
    if (parsedDate) return parsedDate;
    return new Date().toISOString().slice(0, 10);
  });

  // Update date when imagePath changes
  useEffect(() => {
    console.log("[ExportModal] useEffect triggered, imagePath:", imagePath);
    const parsedDate = parseDateFromFilename(imagePath);
    console.log("[ExportModal] parsedDate result:", parsedDate);
    if (parsedDate) {
      setStartDate(parsedDate);
    }
  }, [imagePath]);

  // Initialize with calibration reference time or defaults
  const [startHour, setStartHour] = useState<number>(
    gridCalibration?.referenceHour ?? 12
  );
  const [startMinute, setStartMinute] = useState<number>(
    gridCalibration?.referenceMinute ?? 0
  );

  
  // Get time config for display
  const timeConfig = useMemo(() => {
    if (!detectedTemplate?.templateId) return null;
    return getTimeConfigForTemplate(detectedTemplate.templateId);
  }, [detectedTemplate?.templateId]);

  // Format the time interval for display
  const timeIntervalDisplay = useMemo(() => {
    if (!timeConfig) return "Unknown";
    const mins = timeConfig.minutesPerLine;
    if (mins >= 60) {
      const hours = mins / 60;
      return hours === 1 ? "1 hour" : `${hours} hours`;
    }
    return `${mins} minutes`;
  }, [timeConfig]);

  // Build calibration data object
  const getCalibrationData = useCallback((): GridCalibrationData | null => {
    if (!gridCalibration) return null;
    return {
      topPoint: gridCalibration.topPoint,
      bottomPoint: gridCalibration.bottomPoint,
      curveCenterY: gridCalibration.curveCenterY,
      curvature: gridCalibration.curvature,
      lineSpacing: gridCalibration.lineSpacing,
      linePositions: gridCalibration.linePositions,
      horizontalSpacing: gridCalibration.horizontalSpacing,
      horizontalPositions: gridCalibration.horizontalPositions,
      horizontalTopTemp: gridCalibration.horizontalTopTemp,
      referenceHour: gridCalibration.referenceHour,
      referenceMinute: gridCalibration.referenceMinute,
    };
  }, [gridCalibration]);

  // Build export config
  const getExportConfig = useCallback((): ExportConfig | null => {
    if (!detectedTemplate?.templateId) return null;
    return {
      startDate: new Date(startDate + "T00:00:00"),
      startHour,
      startMinute,
      templateId: detectedTemplate.templateId,
    };
  }, [startDate, startHour, startMinute, detectedTemplate?.templateId]);

  // Generate CSV preview
  const csvPreview = useMemo(() => {
    const calibrationData = getCalibrationData();
    const config = getExportConfig();
    if (!calibrationData || !config || curvePoints.length === 0) return "";

    const rows = generateExportData(curvePoints, curveRawPoints, calibrationData, config);
    return exportToCSV(rows);
  }, [getCalibrationData, getExportConfig, curvePoints, curveRawPoints]);

  // Handle export
  const handleExport = useCallback(() => {
    const calibrationData = getCalibrationData();
    const config = getExportConfig();
    if (!calibrationData || !config || curvePoints.length === 0) return;

    exportCurveData(curvePoints, curveRawPoints, calibrationData, config);
    onClose();
    onExportSuccess?.();
  }, [getCalibrationData, getExportConfig, curvePoints, curveRawPoints, onClose, onExportSuccess]);

  // Handle hour input with validation
  const handleHourChange = (value: string) => {
    const num = parseInt(value, 10);
    if (!isNaN(num) && num >= 0 && num <= 23) {
      setStartHour(num);
    } else if (value === "") {
      setStartHour(0);
    }
  };

  // Handle minute input with validation
  const handleMinuteChange = (value: string) => {
    const num = parseInt(value, 10);
    if (!isNaN(num) && num >= 0 && num <= 59) {
      setStartMinute(num);
    } else if (value === "") {
      setStartMinute(0);
    }
  };

  if (!isOpen) return null;

  return (
    <div className="export-modal-overlay" onClick={onClose}>
      <div className="export-modal" onClick={(e) => e.stopPropagation()}>
        <div className="export-modal-header">
          <h2>Export Curve Data</h2>
          <button className="close-btn" onClick={onClose}>
            &times;
          </button>
        </div>

        <div className="export-modal-body">
          {/* Chart info section */}
          <div className="export-section">
            <h3>Chart Information</h3>
            <div className="info-grid">
              <div className="info-item">
                <span className="info-label">Template:</span>
                <span className="info-value template-badge">
                  {detectedTemplate?.templateId ?? "Unknown"}
                </span>
              </div>
              <div className="info-item">
                <span className="info-label">Time per line:</span>
                <span className="info-value">{timeIntervalDisplay}</span>
              </div>
              <div className="info-item">
                <span className="info-label">Total points:</span>
                <span className="info-value">{curvePoints.length}</span>
              </div>
              <div className="info-item">
                <span className="info-label">Vertical lines:</span>
                <span className="info-value">
                  {gridCalibration?.linePositions.length ?? 0}
                </span>
              </div>
            </div>
          </div>

          {/* Date/Time input section */}
          <div className="export-section">
            <h3>Start Date & Time</h3>
            <p className="section-hint">
              Date and time of the first vertical line on the chart.
            </p>

            <div className="datetime-inputs">
              <div className="input-group">
                <label>Date:</label>
                <div className="date-picker-wrapper">
                  <span className="date-display">
                    {startDate.split("-").reverse().join("/")}
                  </span>
                  <input
                    type="date"
                    value={startDate}
                    onChange={(e) => setStartDate(e.target.value)}
                    className="date-input-hidden"
                  />
                </div>
              </div>

              <div className="input-group">
                <label>Time:</label>
                <div className="time-input">
                  <input
                    type="number"
                    min="0"
                    max="23"
                    value={startHour.toString().padStart(2, "0")}
                    onChange={(e) => handleHourChange(e.target.value)}
                    className="input-field input-hour"
                    placeholder="HH"
                  />
                  <span className="time-separator">:</span>
                  <input
                    type="number"
                    min="0"
                    max="59"
                    value={startMinute.toString().padStart(2, "0")}
                    onChange={(e) => handleMinuteChange(e.target.value)}
                    className="input-field input-minute"
                    placeholder="MM"
                  />
                </div>
              </div>
            </div>
          </div>

          {/* CSV Preview section */}
          <div className="export-section">
            <h3>Output Preview</h3>
            <div className="csv-preview-container">
              <pre className="csv-preview">{csvPreview}</pre>
            </div>
          </div>
        </div>

        <div className="export-modal-footer">
          <span className="footer-info">{curvePoints.length} rows</span>
          <div className="footer-buttons">
            <button className="btn btn-secondary" onClick={onClose}>
              Cancel
            </button>
            <button
              className="btn btn-primary"
              onClick={handleExport}
              disabled={!gridCalibration || curvePoints.length === 0}
            >
              Export CSV
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}

export default ExportModal;
