/**
 * CalibrationPanel - User-editable calibration settings for each chart.
 */

import { useState } from "react";
import { useImageStore } from "../../stores/imageStore";
import type { ChartFormat } from "../../types";
import "./CalibrationPanel.css";

const CHART_TYPE_LABELS: Record<ChartFormat, string> = {
  daily: "Daily (24h)",
  four_day: "4-Day (96h)",
  weekly: "Weekly (168h)",
};

export function CalibrationPanel() {
  const [isExpanded, setIsExpanded] = useState(true);

  const {
    imagePath,
    chartType,
    calibration,
    setChartType,
    setCalibration,
    resetCalibrationToDefaults,
  } = useImageStore();

  // Only show when an image is loaded
  if (!imagePath) {
    return null;
  }

  const toggleExpanded = () => setIsExpanded(!isExpanded);

  const handleChartTypeChange = (e: React.ChangeEvent<HTMLSelectElement>) => {
    setChartType(e.target.value as ChartFormat);
  };

  const handleTempMinChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const value = parseFloat(e.target.value);
    if (!isNaN(value)) {
      setCalibration({ tempMin: value });
    }
  };

  const handleTempMaxChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const value = parseFloat(e.target.value);
    if (!isNaN(value)) {
      setCalibration({ tempMax: value });
    }
  };

  const handleStartHourChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const value = parseInt(e.target.value, 10);
    if (!isNaN(value) && value >= 0 && value <= 23) {
      setCalibration({ startHour: value });
    }
  };

  return (
    <div className={`panel calibration-panel ${isExpanded ? "expanded" : "collapsed"}`}>
      <h2 className="panel-header" onClick={toggleExpanded}>
        <span className="collapse-icon">{isExpanded ? "▼" : "▶"}</span>
        Calibration
        {!isExpanded && (
          <span className="collapsed-summary">
            {calibration.tempMin}° - {calibration.tempMax}°C
          </span>
        )}
      </h2>

      {isExpanded && (
        <div className="panel-content">
          <div className="calibration-field">
            <label htmlFor="chart-type">Chart Type</label>
            <select
              id="chart-type"
              value={chartType}
              onChange={handleChartTypeChange}
              className="calibration-select"
            >
              {Object.entries(CHART_TYPE_LABELS).map(([value, label]) => (
                <option key={value} value={value}>
                  {label}
                </option>
              ))}
            </select>
          </div>

          <div className="calibration-row">
            <div className="calibration-field">
              <label htmlFor="temp-max">Max Temp</label>
              <div className="input-with-unit">
                <input
                  id="temp-max"
                  type="number"
                  value={calibration.tempMax}
                  onChange={handleTempMaxChange}
                  step="1"
                  className="calibration-input"
                />
                <span className="unit">°C</span>
              </div>
            </div>

            <div className="calibration-field">
              <label htmlFor="temp-min">Min Temp</label>
              <div className="input-with-unit">
                <input
                  id="temp-min"
                  type="number"
                  value={calibration.tempMin}
                  onChange={handleTempMinChange}
                  step="1"
                  className="calibration-input"
                />
                <span className="unit">°C</span>
              </div>
            </div>
          </div>

          <div className="calibration-field">
            <label htmlFor="start-hour">Start Hour</label>
            <div className="input-with-unit">
              <input
                id="start-hour"
                type="number"
                value={calibration.startHour}
                onChange={handleStartHourChange}
                min="0"
                max="23"
                step="1"
                className="calibration-input"
              />
              <span className="unit">:00</span>
            </div>
            <span className="field-hint">Leftmost grid line hour</span>
          </div>

          <button
            onClick={resetCalibrationToDefaults}
            className="btn btn-secondary btn-small"
            title="Reset to default values for this chart type"
          >
            Reset to Defaults
          </button>
        </div>
      )}
    </div>
  );
}

export default CalibrationPanel;
