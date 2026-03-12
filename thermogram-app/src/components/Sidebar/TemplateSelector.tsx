/**
 * TemplateSelector - Dropdown for manual template selection.
 */

import { useState, useRef, useEffect } from "react";
import { useImageStore } from "../../stores/imageStore";
import "./TemplateSelector.css";

// Template metadata (from template_detector.py)
export const TEMPLATES = {
  "gunluk-1": { chartType: "daily", period: "1990s", gridColor: "yellow/cream" },
  "gunluk-2": { chartType: "daily", period: "1980", gridColor: "green/olive" },
  "gunluk-3": { chartType: "daily", period: "1980s", gridColor: "orange" },
  "haftalik-1": { chartType: "weekly", period: "1940s", gridColor: "orange" },
  "haftalik-2": { chartType: "weekly", period: "1970s", gridColor: "orange/pink" },
  "4_gunluk-1": { chartType: "4day", period: "1940s", gridColor: "orange" },
  "4_gunluk-2": { chartType: "4day", period: "1955", gridColor: "orange" },
  "4_gunluk-3": { chartType: "4day", period: "1945-1950s", gridColor: "orange" },
  "4_gunluk-4": { chartType: "4day", period: "1950s", gridColor: "orange/red" },
} as const;

type TemplateId = keyof typeof TEMPLATES;

export function TemplateSelector() {
  const { detectedTemplate, setDetectedTemplate } = useImageStore();
  const [isOpen, setIsOpen] = useState(false);
  const dropdownRef = useRef<HTMLDivElement>(null);

  // Close dropdown when clicking outside
  useEffect(() => {
    function handleClickOutside(event: MouseEvent) {
      if (dropdownRef.current && !dropdownRef.current.contains(event.target as Node)) {
        setIsOpen(false);
      }
    }

    if (isOpen) {
      document.addEventListener("mousedown", handleClickOutside);
      return () => document.removeEventListener("mousedown", handleClickOutside);
    }
  }, [isOpen]);

  // Close on Escape key
  useEffect(() => {
    function handleEscape(event: KeyboardEvent) {
      if (event.key === "Escape") {
        setIsOpen(false);
      }
    }

    if (isOpen) {
      document.addEventListener("keydown", handleEscape);
      return () => document.removeEventListener("keydown", handleEscape);
    }
  }, [isOpen]);

  const handleSelect = (templateId: TemplateId) => {
    const meta = TEMPLATES[templateId];
    setDetectedTemplate({
      templateId,
      chartType: meta.chartType,
      confidence: 1.0, // Manual selection = 100% confidence
      period: meta.period,
      gridColor: meta.gridColor,
    });
    setIsOpen(false);
  };

  if (!detectedTemplate) {
    return null;
  }

  return (
    <div className="panel template-panel" ref={dropdownRef}>
      <h2>Template</h2>

      <div
        className="template-selector-trigger"
        onClick={() => setIsOpen(!isOpen)}
        title="Click to change template"
      >
        <div className="template-info">
          <span className="template-id">{detectedTemplate.templateId}</span>
          <span className="template-confidence">
            {detectedTemplate.confidence === 1.0 ? "Manual" : `${(detectedTemplate.confidence * 100).toFixed(0)}%`}
          </span>
        </div>
        <div className="template-details">
          <small>
            {detectedTemplate.chartType} · {detectedTemplate.period} · {detectedTemplate.gridColor}
          </small>
        </div>
        <span className="dropdown-arrow">{isOpen ? "▲" : "▼"}</span>
      </div>

      {isOpen && (
        <div className="template-dropdown">
          {(Object.keys(TEMPLATES) as TemplateId[]).map((templateId) => {
            const meta = TEMPLATES[templateId];
            const isSelected = detectedTemplate.templateId === templateId;

            return (
              <div
                key={templateId}
                className={`template-option ${isSelected ? "selected" : ""}`}
                onClick={() => handleSelect(templateId)}
              >
                <span className="option-id">{templateId}</span>
                <span className="option-details">
                  {meta.chartType} · {meta.period}
                </span>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}

export default TemplateSelector;
