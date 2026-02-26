/**
 * Coordinate conversion helpers between PDF point space and Web (CSS pixel) space.
 *
 * The canonical coordinate system uses PDF points (1/72 inch) with origin at
 * bottom-left.  Web coordinates use CSS pixels with origin at top-left.
 *
 * Conversion must account for:
 *   - Page rotation (0, 90, 180, 270 degrees)
 *   - Viewport scale (zoom level)
 *   - Device pixel ratio (DPI scale)
 */

import type {
  CanonicalBBox,
  CanonicalPoint,
  CoordinateComparisonResult,
  PageMetadata,
  WebBBox,
  WebPoint,
} from "../types/Coordinates";

/* ------------------------------------------------------------------ */
/*  Rotation helpers                                                   */
/* ------------------------------------------------------------------ */

/**
 * Apply page rotation to a canonical (PDF-space) point, returning the
 * point in the **rotated** PDF coordinate system (still in PDF points,
 * origin bottom-left of the *rotated* page).
 */
function applyPageRotation(
  point: CanonicalPoint,
  metadata: PageMetadata,
): { x: number; y: number } {
  const { x, y } = point;
  const { width: w, height: h, rotation } = metadata;

  switch (rotation) {
    case 0:
      return { x, y };
    case 90:
      return { x: y, y: w - x };
    case 180:
      return { x: w - x, y: h - y };
    case 270:
      return { x: h - y, y: x };
    default:
      return { x, y };
  }
}

/**
 * Reverse page rotation: convert from the *rotated* coordinate system
 * back to the unrotated canonical system.
 */
function reversePageRotation(
  point: { x: number; y: number },
  metadata: PageMetadata,
): { x: number; y: number } {
  const { x, y } = point;
  const { width: w, height: h, rotation } = metadata;

  switch (rotation) {
    case 0:
      return { x, y };
    case 90:
      return { x: w - y, y: x };
    case 180:
      return { x: w - x, y: h - y };
    case 270:
      return { x: y, y: h - x };
    default:
      return { x, y };
  }
}

/**
 * Return the effective page dimensions after rotation.
 * For 90/270 rotations the width and height are swapped.
 */
export function effectivePageSize(metadata: PageMetadata): {
  width: number;
  height: number;
} {
  if (metadata.rotation === 90 || metadata.rotation === 270) {
    return { width: metadata.height, height: metadata.width };
  }
  return { width: metadata.width, height: metadata.height };
}

/* ------------------------------------------------------------------ */
/*  Point conversion                                                   */
/* ------------------------------------------------------------------ */

/**
 * Convert a canonical (PDF-space) point to a Web (CSS-pixel) point.
 *
 * @param canonical  - Point in PDF coordinate space.
 * @param metadata   - Page geometry from the PDF.
 * @param viewportScale - Current zoom / viewport scale factor.
 * @param dpiScale   - Device pixel ratio (window.devicePixelRatio).
 */
export function pdfToWebPoint(
  canonical: CanonicalPoint,
  metadata: PageMetadata,
  viewportScale: number,
  dpiScale: number,
): WebPoint {
  const rotated = applyPageRotation(canonical, metadata);
  const eff = effectivePageSize(metadata);

  return {
    page: canonical.page,
    x: rotated.x * viewportScale * dpiScale,
    // PDF origin is bottom-left; Web origin is top-left -> flip Y
    y: (eff.height - rotated.y) * viewportScale * dpiScale,
  };
}

/**
 * Convert a Web (CSS-pixel) point back to canonical (PDF-space) point.
 *
 * @param web        - Point in CSS pixel space.
 * @param metadata   - Page geometry from the PDF.
 * @param viewportScale - Current zoom / viewport scale factor.
 * @param dpiScale   - Device pixel ratio.
 */
export function webToPdfPoint(
  web: WebPoint,
  metadata: PageMetadata,
  viewportScale: number,
  dpiScale: number,
): CanonicalPoint {
  const eff = effectivePageSize(metadata);
  const scaleFactor = viewportScale * dpiScale;

  // Undo scaling
  const rotatedX = web.x / scaleFactor;
  // Undo Y-flip and scaling
  const rotatedY = eff.height - web.y / scaleFactor;

  const unrotated = reversePageRotation({ x: rotatedX, y: rotatedY }, metadata);

  return {
    page: web.page,
    x: unrotated.x,
    y: unrotated.y,
  };
}

/* ------------------------------------------------------------------ */
/*  BBox conversion                                                    */
/* ------------------------------------------------------------------ */

/**
 * Convert a canonical bounding box to Web pixel space.
 */
export function pdfToWebBBox(
  bbox: CanonicalBBox,
  metadata: PageMetadata,
  viewportScale: number,
  dpiScale: number,
): WebBBox {
  const topLeft = pdfToWebPoint(
    { x: bbox.x1, y: bbox.y2, page: bbox.page },
    metadata,
    viewportScale,
    dpiScale,
  );
  const bottomRight = pdfToWebPoint(
    { x: bbox.x2, y: bbox.y1, page: bbox.page },
    metadata,
    viewportScale,
    dpiScale,
  );

  return {
    page: bbox.page,
    x1: Math.min(topLeft.x, bottomRight.x),
    y1: Math.min(topLeft.y, bottomRight.y),
    x2: Math.max(topLeft.x, bottomRight.x),
    y2: Math.max(topLeft.y, bottomRight.y),
  };
}

/**
 * Convert a Web pixel bounding box back to canonical PDF space.
 */
export function webToPdfBBox(
  bbox: WebBBox,
  metadata: PageMetadata,
  viewportScale: number,
  dpiScale: number,
): CanonicalBBox {
  const p1 = webToPdfPoint(
    { x: bbox.x1, y: bbox.y1, page: bbox.page },
    metadata,
    viewportScale,
    dpiScale,
  );
  const p2 = webToPdfPoint(
    { x: bbox.x2, y: bbox.y2, page: bbox.page },
    metadata,
    viewportScale,
    dpiScale,
  );

  return {
    page: bbox.page,
    x1: Math.min(p1.x, p2.x),
    y1: Math.min(p1.y, p2.y),
    x2: Math.max(p1.x, p2.x),
    y2: Math.max(p1.y, p2.y),
  };
}

/* ------------------------------------------------------------------ */
/*  Comparison utilities                                               */
/* ------------------------------------------------------------------ */

/**
 * Compare two canonical points and determine whether they are within
 * the given tolerance (in PDF points).
 *
 * @param a         - First point (canonical).
 * @param b         - Second point (canonical).
 * @param tolerance - Maximum allowed Euclidean distance in PDF points.
 */
export function compareCanonicalPoints(
  a: CanonicalPoint,
  b: CanonicalPoint,
  tolerance: number,
): CoordinateComparisonResult {
  const deltaX = Math.abs(a.x - b.x);
  const deltaY = Math.abs(a.y - b.y);
  const distance = Math.sqrt(deltaX * deltaX + deltaY * deltaY);

  return {
    deltaX,
    deltaY,
    distance,
    passed: distance <= tolerance,
    tolerance,
  };
}

/**
 * Round-trip a canonical point through Web space and back, then compare
 * with the original.  This validates that pdfToWeb -> webToPdf is lossless
 * (within floating-point tolerance).
 */
export function roundTripCheck(
  original: CanonicalPoint,
  metadata: PageMetadata,
  viewportScale: number,
  dpiScale: number,
  tolerance: number,
): CoordinateComparisonResult {
  const web = pdfToWebPoint(original, metadata, viewportScale, dpiScale);
  const backToPdf = webToPdfPoint(web, metadata, viewportScale, dpiScale);
  return compareCanonicalPoints(original, backToPdf, tolerance);
}
