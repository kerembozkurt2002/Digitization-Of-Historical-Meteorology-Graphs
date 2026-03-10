"""
Template Detector Module v2

Automatically detects which template type a thermogram image belongs to.
Uses enhanced feature extraction with aspect ratio, text region analysis,
and grid density detection.
"""

import json
import numpy as np
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
import cv2


@dataclass
class TemplateMatch:
    """Result of template detection."""
    template_id: str          # e.g., "gunluk-1", "haftalik-2"
    chart_type: str           # "daily", "weekly", "4day"
    confidence: float         # 0.0 - 1.0
    all_scores: Dict[str, float]  # Scores for all templates


class TemplateDetector:
    """
    Detects thermogram template type using feature matching.

    Uses pre-computed template signatures to classify new images.
    """

    # Template metadata
    TEMPLATES = {
        "gunluk-1": {"chart_type": "daily", "period": "1990s", "grid_color": "yellow/cream"},
        "gunluk-2": {"chart_type": "daily", "period": "1980", "grid_color": "green/olive"},
        "gunluk-3": {"chart_type": "daily", "period": "1980s", "grid_color": "orange"},
        "haftalik-1": {"chart_type": "weekly", "period": "1940s", "grid_color": "orange"},
        "haftalik-2": {"chart_type": "weekly", "period": "1970s", "grid_color": "orange/pink"},
        "4_gunluk-1": {"chart_type": "4day", "period": "1940s", "grid_color": "orange"},
        "4_gunluk-2": {"chart_type": "4day", "period": "1955", "grid_color": "orange"},
        "4_gunluk-3": {"chart_type": "4day", "period": "1945-1950s", "grid_color": "orange"},
        "4_gunluk-4": {"chart_type": "4day", "period": "1950s", "grid_color": "orange/red"},
    }

    def __init__(self, signatures_path: Optional[Path] = None):
        """
        Initialize detector with template signatures.

        Args:
            signatures_path: Path to signatures JSON file.
                           If None, uses default path.
        """
        if signatures_path is None:
            signatures_path = Path(__file__).parent.parent / "configs" / "template_signatures.json"

        self.signatures_path = signatures_path
        self.signatures: Dict[str, np.ndarray] = {}

        if signatures_path.exists():
            self._load_signatures()

    def _load_signatures(self) -> None:
        """Load pre-computed template signatures."""
        with open(self.signatures_path, 'r') as f:
            data = json.load(f)

        self.signatures = {
            template_id: np.array(features)
            for template_id, features in data.items()
        }

    def _save_signatures(self) -> None:
        """Save template signatures to file."""
        data = {
            template_id: features.tolist()
            for template_id, features in self.signatures.items()
        }

        self.signatures_path.parent.mkdir(parents=True, exist_ok=True)
        with open(self.signatures_path, 'w') as f:
            json.dump(data, f, indent=2)

    def extract_features(self, image: np.ndarray) -> np.ndarray:
        """
        Extract enhanced feature vector from an image.

        Args:
            image: BGR image (numpy array)

        Returns:
            Feature vector (numpy array)
        """
        # Ensure image is in correct format
        if len(image.shape) == 2:
            image = cv2.cvtColor(image, cv2.COLOR_GRAY2BGR)

        orig_h, orig_w = image.shape[:2]
        features = []

        # ============================================================
        # 1. ASPECT RATIO (critical for distinguishing weekly vs 4-day)
        # ============================================================
        aspect_ratio = orig_w / orig_h
        features.append(aspect_ratio)
        # Normalized aspect ratio categories
        features.append(1.0 if aspect_ratio > 3.5 else 0.0)  # Very wide (weekly)
        features.append(1.0 if 3.0 < aspect_ratio <= 3.5 else 0.0)  # Medium wide
        features.append(1.0 if aspect_ratio <= 3.0 else 0.0)  # Narrower

        # Resize for consistent analysis
        img_resized = cv2.resize(image, (400, 120))
        h, w = img_resized.shape[:2]

        # ============================================================
        # 2. VERTICAL LINE DENSITY (weekly has more divisions)
        # ============================================================
        gray = cv2.cvtColor(img_resized, cv2.COLOR_BGR2GRAY)

        # Detect vertical edges
        sobelx = cv2.Sobel(gray, cv2.CV_64F, 1, 0, ksize=3)
        sobelx_abs = np.abs(sobelx)

        # Count strong vertical lines by analyzing columns
        col_sums = np.sum(sobelx_abs, axis=0)
        col_threshold = np.mean(col_sums) + np.std(col_sums)
        strong_vertical_cols = np.sum(col_sums > col_threshold)
        features.append(strong_vertical_cols / w)  # Normalized

        # Vertical line periodicity (FFT of column sums)
        fft_cols = np.abs(np.fft.fft(col_sums))
        fft_cols = fft_cols[:len(fft_cols)//2]  # Take first half
        # Find dominant frequency
        if len(fft_cols) > 10:
            dominant_freq_idx = np.argmax(fft_cols[5:50]) + 5  # Skip DC and very low freq
            features.append(dominant_freq_idx / 50.0)
        else:
            features.append(0.0)

        # ============================================================
        # 3. LEFT EDGE TEXT DETECTION (Turkish, German, French text)
        # ============================================================
        left_edge = img_resized[:, :30, :]
        left_gray = cv2.cvtColor(left_edge, cv2.COLOR_BGR2GRAY)

        # Text presence indicated by high variance and edge density
        left_variance = np.var(left_gray) / 1000.0
        features.append(min(left_variance, 5.0))

        # Edge density in left region
        left_edges = cv2.Canny(left_gray, 50, 150)
        left_edge_density = np.sum(left_edges > 0) / left_edges.size
        features.append(left_edge_density)

        # Mean color of left edge
        features.extend(np.mean(left_edge, axis=(0, 1)) / 255.0)

        # ============================================================
        # 4. RIGHT EDGE TEXT DETECTION
        # ============================================================
        right_edge = img_resized[:, -30:, :]
        right_gray = cv2.cvtColor(right_edge, cv2.COLOR_BGR2GRAY)

        right_variance = np.var(right_gray) / 1000.0
        features.append(min(right_variance, 5.0))

        right_edges = cv2.Canny(right_gray, 50, 150)
        right_edge_density = np.sum(right_edges > 0) / right_edges.size
        features.append(right_edge_density)

        features.extend(np.mean(right_edge, axis=(0, 1)) / 255.0)

        # ============================================================
        # 5. TOP HEADER ANALYSIS (day names, dates)
        # ============================================================
        top_header = img_resized[:20, :, :]
        top_gray = cv2.cvtColor(top_header, cv2.COLOR_BGR2GRAY)

        # Text complexity in header
        top_edges = cv2.Canny(top_gray, 50, 150)
        top_edge_density = np.sum(top_edges > 0) / top_edges.size
        features.append(top_edge_density)

        # Variance (text has higher variance)
        top_variance = np.var(top_gray) / 1000.0
        features.append(min(top_variance, 5.0))

        # Color features
        features.extend(np.mean(top_header, axis=(0, 1)) / 255.0)

        # ============================================================
        # 6. GRID CENTER COLOR ANALYSIS
        # ============================================================
        center = img_resized[30:90, 50:350, :]
        center_hsv = cv2.cvtColor(center, cv2.COLOR_BGR2HSV)

        # Hue histogram (for distinguishing orange vs green vs yellow)
        hue_hist, _ = np.histogram(center_hsv[:, :, 0], bins=18, range=(0, 180))
        hue_hist = hue_hist.astype(float) / (hue_hist.sum() + 1e-6)
        features.extend(hue_hist)

        # Saturation and Value
        features.append(np.mean(center_hsv[:, :, 1]) / 255.0)
        features.append(np.std(center_hsv[:, :, 1]) / 255.0)
        features.append(np.mean(center_hsv[:, :, 2]) / 255.0)
        features.append(np.std(center_hsv[:, :, 2]) / 255.0)

        # BGR means
        features.extend(np.mean(center, axis=(0, 1)) / 255.0)

        # ============================================================
        # 7. OVERALL COLOR HISTOGRAMS (more bins)
        # ============================================================
        for channel in range(3):
            hist, _ = np.histogram(img_resized[:, :, channel], bins=24, range=(0, 256))
            hist = hist.astype(float) / (hist.sum() + 1e-6)
            features.extend(hist)

        # ============================================================
        # 8. TEXTURE FEATURES (grid density)
        # ============================================================
        # Horizontal edges
        sobely = cv2.Sobel(gray, cv2.CV_64F, 0, 1, ksize=3)
        sobely_abs = np.abs(sobely)

        # Row-wise sum for horizontal line detection
        row_sums = np.sum(sobely_abs, axis=1)
        row_threshold = np.mean(row_sums) + np.std(row_sums)
        strong_horizontal_rows = np.sum(row_sums > row_threshold)
        features.append(strong_horizontal_rows / h)

        # Overall edge density
        edges = cv2.Canny(gray, 50, 150)
        overall_edge_density = np.sum(edges > 0) / edges.size
        features.append(overall_edge_density)

        # ============================================================
        # 9. CORNER ANALYSIS (often have specific markers)
        # ============================================================
        corners = [
            img_resized[:15, :30, :],      # top-left
            img_resized[:15, -30:, :],     # top-right
            img_resized[-15:, :30, :],     # bottom-left
            img_resized[-15:, -30:, :]     # bottom-right
        ]

        for corner in corners:
            corner_gray = cv2.cvtColor(corner, cv2.COLOR_BGR2GRAY)
            features.append(np.mean(corner_gray) / 255.0)
            features.append(np.var(corner_gray) / 1000.0)

        # ============================================================
        # 10. BRIGHTNESS DISTRIBUTION
        # ============================================================
        features.append(np.mean(gray) / 255.0)
        features.append(np.std(gray) / 255.0)
        features.append(np.median(gray) / 255.0)

        # Brightness histogram
        bright_hist, _ = np.histogram(gray, bins=16, range=(0, 256))
        bright_hist = bright_hist.astype(float) / (bright_hist.sum() + 1e-6)
        features.extend(bright_hist)

        return np.array(features)

    def compute_similarity(self, features1: np.ndarray, features2: np.ndarray) -> float:
        """
        Compute weighted similarity between two feature vectors.

        Uses a combination of cosine similarity and euclidean distance.
        """
        # Cosine similarity
        norm1 = np.linalg.norm(features1)
        norm2 = np.linalg.norm(features2)

        if norm1 == 0 or norm2 == 0:
            return 0.0

        cosine_sim = np.dot(features1, features2) / (norm1 * norm2)

        # Euclidean distance (normalized)
        euclidean_dist = np.linalg.norm(features1 - features2)
        max_dist = np.sqrt(len(features1))  # Max possible distance
        euclidean_sim = 1.0 - (euclidean_dist / max_dist)

        # Weighted combination (favor cosine for overall similarity)
        similarity = 0.7 * cosine_sim + 0.3 * euclidean_sim

        return float(max(0.0, similarity))

    def detect(self, image: np.ndarray) -> TemplateMatch:
        """
        Detect template type for an image.

        Args:
            image: BGR image (numpy array)

        Returns:
            TemplateMatch with detected template and confidence
        """
        if not self.signatures:
            raise ValueError("No template signatures loaded. Run build_signatures() first.")

        # Extract features from input image
        features = self.extract_features(image)

        # Compare with all templates
        scores = {}
        for template_id, signature in self.signatures.items():
            scores[template_id] = self.compute_similarity(features, signature)

        # Find best match
        best_template = max(scores, key=scores.get)
        best_score = scores[best_template]

        # Calculate confidence as ratio of best to second best
        sorted_scores = sorted(scores.values(), reverse=True)
        if len(sorted_scores) > 1 and sorted_scores[1] > 0:
            confidence_ratio = sorted_scores[0] / sorted_scores[1]
            # Adjust confidence based on margin
            adjusted_confidence = best_score * min(confidence_ratio, 1.2) / 1.2
        else:
            adjusted_confidence = best_score

        # Get chart type
        chart_type = self.TEMPLATES.get(best_template, {}).get("chart_type", "unknown")

        return TemplateMatch(
            template_id=best_template,
            chart_type=chart_type,
            confidence=adjusted_confidence,
            all_scores=scores
        )

    def build_signatures(self, data_path: Path, samples_per_template: int = 50) -> None:
        """
        Build template signatures from classified data.

        Args:
            data_path: Path to data-final or data-classified folder
            samples_per_template: Number of samples to use per template
        """
        print("Building template signatures...")

        for chart_folder in ["gunluk", "haftalik", "4_gunluk"]:
            chart_path = data_path / chart_folder
            if not chart_path.exists():
                continue

            for template_folder in sorted(chart_path.iterdir()):
                if not template_folder.is_dir():
                    continue

                template_id = template_folder.name
                print(f"  Processing {template_id}...")

                # Get image files
                image_files = list(template_folder.glob("*.tif")) + \
                              list(template_folder.glob("*.jpg")) + \
                              list(template_folder.glob("*.png"))

                if not image_files:
                    print(f"    No images found, skipping")
                    continue

                # Sample images (use more samples for better signatures)
                num_samples = min(samples_per_template, len(image_files))
                if len(image_files) > samples_per_template:
                    indices = np.random.choice(len(image_files), samples_per_template, replace=False)
                    image_files = [image_files[i] for i in indices]

                # Extract features from all samples
                all_features = []
                for img_path in image_files:
                    try:
                        img = cv2.imread(str(img_path))
                        if img is None:
                            continue
                        features = self.extract_features(img)
                        all_features.append(features)
                    except Exception as e:
                        print(f"    Error processing {img_path.name}: {e}")

                if all_features:
                    # Compute mean signature
                    self.signatures[template_id] = np.mean(all_features, axis=0)
                    print(f"    Created signature from {len(all_features)} images")

        # Save signatures
        self._save_signatures()
        print(f"Signatures saved to {self.signatures_path}")


def detect_template(image: np.ndarray) -> TemplateMatch:
    """
    Convenience function to detect template type.

    Args:
        image: BGR image (numpy array)

    Returns:
        TemplateMatch with detected template
    """
    detector = TemplateDetector()
    return detector.detect(image)


__all__ = ['TemplateDetector', 'TemplateMatch', 'detect_template']
