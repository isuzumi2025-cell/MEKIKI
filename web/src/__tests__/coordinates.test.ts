/**
 * Coordinate conversion tests (TypeScript reference implementation).
 *
 * Mirrors the Python pytest suite to ensure the TypeScript helpers
 * produce identical results.  Uses simple assertion helpers since
 * the project does not include a TS test runner for this module.
 */

import type {
  CanonicalPoint,
  PageMetadata,
  WebPoint,
} from "../types/Coordinates";

import {
  compareCanonicalPoints,
  effectivePageSize,
  pdfToWebBBox,
  pdfToWebPoint,
  roundTripCheck,
  webToPdfBBox,
  webToPdfPoint,
} from "../utils/coordinates";

/* ------------------------------------------------------------------ */
/*  Test helpers                                                       */
/* ------------------------------------------------------------------ */

const TOLERANCE = 0.5; // PDF points

const PAGE_SIZES: Record<string, [number, number]> = {
  A4_portrait: [595.28, 841.89],
  A4_landscape: [841.89, 595.28],
  Letter: [612.0, 792.0],
  custom_small: [300.0, 400.0],
};

const ROTATIONS: (0 | 90 | 180 | 270)[] = [0, 90, 180, 270];
const ZOOMS = [0.25, 0.5, 1.0, 1.5, 2.0, 4.0];
const DPI_SCALES = [1.0, 1.5, 2.0];

function assertApprox(actual: number, expected: number, eps = 1e-8): void {
  if (Math.abs(actual - expected) > eps) {
    throw new Error(
      `Assertion failed: ${actual} !== ${expected} (diff=${Math.abs(actual - expected)})`,
    );
  }
}

function assert(condition: boolean, msg: string): void {
  if (!condition) throw new Error(`Assertion failed: ${msg}`);
}

/* ------------------------------------------------------------------ */
/*  Tests                                                              */
/* ------------------------------------------------------------------ */

// --- effectivePageSize ---

function testEffectivePageSize(): void {
  const meta0: PageMetadata = { width: 595.28, height: 841.89, rotation: 0 };
  const eff0 = effectivePageSize(meta0);
  assertApprox(eff0.width, 595.28);
  assertApprox(eff0.height, 841.89);

  const meta90: PageMetadata = { width: 595.28, height: 841.89, rotation: 90 };
  const eff90 = effectivePageSize(meta90);
  assertApprox(eff90.width, 841.89);
  assertApprox(eff90.height, 595.28);

  const meta180: PageMetadata = {
    width: 595.28,
    height: 841.89,
    rotation: 180,
  };
  const eff180 = effectivePageSize(meta180);
  assertApprox(eff180.width, 595.28);
  assertApprox(eff180.height, 841.89);

  const meta270: PageMetadata = {
    width: 595.28,
    height: 841.89,
    rotation: 270,
  };
  const eff270 = effectivePageSize(meta270);
  assertApprox(eff270.width, 841.89);
  assertApprox(eff270.height, 595.28);
}

// --- Round-trip: PDF -> Web -> PDF ---

function testRoundTripAllCombinations(): void {
  let passed = 0;
  let total = 0;

  for (const [name, [w, h]] of Object.entries(PAGE_SIZES)) {
    for (const rotation of ROTATIONS) {
      for (const zoom of ZOOMS) {
        for (const dpi of DPI_SCALES) {
          const meta: PageMetadata = { width: w, height: h, rotation };
          const original: CanonicalPoint = {
            x: w * 0.3,
            y: h * 0.7,
            page: 1,
          };
          const result = roundTripCheck(original, meta, zoom, dpi, TOLERANCE);
          total++;
          if (result.passed) {
            passed++;
          } else {
            console.error(
              `FAIL: page=${name} rot=${rotation} zoom=${zoom} dpi=${dpi} ` +
                `distance=${result.distance.toFixed(6)}`,
            );
          }
        }
      }
    }
  }

  assert(
    passed === total,
    `Round-trip: ${passed}/${total} passed (${total - passed} failures)`,
  );
  console.log(`Round-trip: ${passed}/${total} passed`);
}

// --- Y-axis flip ---

function testYAxisFlip(): void {
  const meta: PageMetadata = { width: 595.28, height: 841.89, rotation: 0 };

  // Bottom of PDF (y=0) should be bottom of Web (y = height * scale)
  const bottom: CanonicalPoint = { x: 297.64, y: 0, page: 1 };
  const webBottom = pdfToWebPoint(bottom, meta, 1.0, 1.0);
  assertApprox(webBottom.y, 841.89, TOLERANCE);

  // Top of PDF (y=height) should be top of Web (y=0)
  const top: CanonicalPoint = { x: 297.64, y: 841.89, page: 1 };
  const webTop = pdfToWebPoint(top, meta, 1.0, 1.0);
  assertApprox(webTop.y, 0, TOLERANCE);
}

// --- Zoom linearity ---

function testZoomLinearity(): void {
  const meta: PageMetadata = { width: 595.28, height: 841.89, rotation: 0 };
  const point: CanonicalPoint = { x: 100, y: 200, page: 1 };

  const web1x = pdfToWebPoint(point, meta, 1.0, 1.0);
  const web2x = pdfToWebPoint(point, meta, 2.0, 1.0);

  assertApprox(web2x.x, 2.0 * web1x.x);
  assertApprox(web2x.y, 2.0 * web1x.y);
}

// --- BBox conversion ---

function testBBoxRoundTrip(): void {
  const meta: PageMetadata = { width: 595.28, height: 841.89, rotation: 0 };
  const original = { x1: 100, y1: 200, x2: 300, y2: 400, page: 1 };

  const webBBox = pdfToWebBBox(original, meta, 1.5, 2.0);
  const recovered = webToPdfBBox(webBBox, meta, 1.5, 2.0);

  assertApprox(recovered.x1, original.x1, TOLERANCE);
  assertApprox(recovered.y1, original.y1, TOLERANCE);
  assertApprox(recovered.x2, original.x2, TOLERANCE);
  assertApprox(recovered.y2, original.y2, TOLERANCE);
}

// --- compareCanonicalPoints ---

function testComparePoints(): void {
  const a: CanonicalPoint = { x: 100, y: 200, page: 1 };
  const b: CanonicalPoint = { x: 100.1, y: 200.1, page: 1 };

  const result = compareCanonicalPoints(a, b, TOLERANCE);
  assert(result.passed, `Expected pass, got distance=${result.distance}`);

  const far: CanonicalPoint = { x: 110, y: 220, page: 1 };
  const resultFail = compareCanonicalPoints(a, far, TOLERANCE);
  assert(!resultFail.passed, "Expected fail for distant points");
}

// --- Zoom/DPI compose multiplicatively ---

function testZoomDpiComposition(): void {
  const meta: PageMetadata = { width: 595.28, height: 841.89, rotation: 0 };
  const point: CanonicalPoint = { x: 200, y: 400, page: 1 };

  for (const zoom of [0.5, 1.0, 2.0]) {
    for (const dpi of [1.0, 2.0, 3.0]) {
      const webSeparate = pdfToWebPoint(point, meta, zoom, dpi);
      const webCombined = pdfToWebPoint(point, meta, zoom * dpi, 1.0);
      assertApprox(webSeparate.x, webCombined.x);
      assertApprox(webSeparate.y, webCombined.y);
    }
  }
}

/* ------------------------------------------------------------------ */
/*  Runner                                                             */
/* ------------------------------------------------------------------ */

function runAll(): void {
  const tests = [
    ["effectivePageSize", testEffectivePageSize],
    ["roundTripAllCombinations", testRoundTripAllCombinations],
    ["yAxisFlip", testYAxisFlip],
    ["zoomLinearity", testZoomLinearity],
    ["bboxRoundTrip", testBBoxRoundTrip],
    ["comparePoints", testComparePoints],
    ["zoomDpiComposition", testZoomDpiComposition],
  ] as const;

  let passed = 0;
  for (const [name, fn] of tests) {
    try {
      fn();
      console.log(`  PASS: ${name}`);
      passed++;
    } catch (e) {
      console.error(`  FAIL: ${name} — ${(e as Error).message}`);
    }
  }

  console.log(`\n${passed}/${tests.length} test groups passed`);
  if (passed < tests.length) {
    process.exit(1);
  }
}

runAll();
