/**
 * Canonical coordinate system types for PDF/Web coordinate consistency.
 *
 * All internal coordinates are stored in **PDF point space** (1 pt = 1/72 inch),
 * with the origin at the bottom-left of each page.  Web (CSS pixel) coordinates
 * use a top-left origin and must be converted before comparison.
 */

/** A point in canonical PDF coordinate space (origin: bottom-left). */
export type CanonicalPoint = {
  /** Horizontal offset in PDF points from the left edge. */
  x: number;
  /** Vertical offset in PDF points from the **bottom** edge. */
  y: number;
  /** 1-based page number. */
  page: number;
};

/** A point in CSS pixel coordinate space (origin: top-left). */
export type WebPoint = {
  /** Horizontal offset in CSS pixels from the left edge. */
  x: number;
  /** Vertical offset in CSS pixels from the **top** edge. */
  y: number;
  /** 1-based page number. */
  page: number;
};

/** Geometry metadata for a single PDF page. */
export type PageMetadata = {
  /** Page width in PDF points. */
  width: number;
  /** Page height in PDF points. */
  height: number;
  /** Clockwise rotation applied to the page (degrees). */
  rotation: 0 | 90 | 180 | 270;
};

/** A bounding box in canonical PDF coordinate space. */
export type CanonicalBBox = {
  x1: number;
  y1: number;
  x2: number;
  y2: number;
  page: number;
};

/** A bounding box in CSS pixel coordinate space. */
export type WebBBox = {
  x1: number;
  y1: number;
  x2: number;
  y2: number;
  page: number;
};

/** Result of comparing two coordinate sets. */
export type CoordinateComparisonResult = {
  /** Absolute difference on x-axis in PDF points. */
  deltaX: number;
  /** Absolute difference on y-axis in PDF points. */
  deltaY: number;
  /** Euclidean distance between the two points in PDF points. */
  distance: number;
  /** Whether the comparison passed within the given tolerance. */
  passed: boolean;
  /** The tolerance that was used (PDF points). */
  tolerance: number;
};
