/**
 * Chart Time Configuration - Time intervals per chart template type.
 *
 * Different chart types have different time resolutions:
 * - Daily (günlük): 2 vertical lines = 15 min, so 1 line = 7.5 min
 * - Weekly (haftalık): 2 vertical lines = 2 hours, so 1 line = 1 hour
 * - 4-day (4_günlük): 2 vertical lines = 1 hour, so 1 line = 30 min
 */

export interface ChartTimeConfig {
  minutesPerLine: number;
}

/**
 * Time configuration for each chart template type.
 * The key is the template ID prefix (before the hyphen in templates like "günlük-1").
 *
 * Line spacing represents the time between adjacent vertical lines:
 * - Daily: 15 minutes between lines
 * - Weekly: 2 hours between lines
 * - 4-day: 1 hour between lines
 */
export const CHART_TIME_CONFIG: Record<string, ChartTimeConfig> = {
  // Daily charts: 15 minutes per vertical line spacing
  "günlük": { minutesPerLine: 15 },
  "gunluk": { minutesPerLine: 15 },
  "daily": { minutesPerLine: 15 },

  // Weekly charts: 120 minutes (2 hours) per vertical line spacing
  "haftalık": { minutesPerLine: 120 },
  "haftalik": { minutesPerLine: 120 },
  "weekly": { minutesPerLine: 120 },

  // 4-day charts: 60 minutes (1 hour) per vertical line spacing
  "4_günlük": { minutesPerLine: 60 },
  "4_gunluk": { minutesPerLine: 60 },
  "4day": { minutesPerLine: 60 },
  "four_day": { minutesPerLine: 60 },
};

/**
 * Get the time configuration for a template ID.
 * Extracts the chart type from the template ID (e.g., "günlük-1" -> "günlük").
 */
export function getTimeConfigForTemplate(templateId: string): ChartTimeConfig {
  // Extract the base type (before the hyphen, if any)
  const baseType = templateId.split("-")[0].toLowerCase();

  // Look up in the config
  const config = CHART_TIME_CONFIG[baseType];

  if (config) {
    return config;
  }

  // Check if any key is contained in the template ID
  for (const [key, value] of Object.entries(CHART_TIME_CONFIG)) {
    if (templateId.toLowerCase().includes(key)) {
      return value;
    }
  }

  // Default to daily if not found
  return { minutesPerLine: 15 };
}

/**
 * Calculate the total duration covered by the chart in minutes.
 */
export function getChartDurationMinutes(templateId: string, numberOfLines: number): number {
  const config = getTimeConfigForTemplate(templateId);
  return config.minutesPerLine * numberOfLines;
}
