## “””
FigureAwarePipeline

Augments Azure Document Intelligence layout extraction with proper
figure handling via GPT-4o vision.

Flow:

1. Run ADI prebuilt-layout → get text + figure bounding regions
1. Crop each figure from the PDF using PyMuPDF
1. Self-classify each figure via a cheap GPT-4o call (no caption assumed)
1. Route to diagram extractor (JSON + summary) or screenshot describer
1. Filter OCR text spans that overlap with figure regions from main content
1. Return a unified structured document result

Dependencies:
pip install azure-ai-documentintelligence azure-core openai pymupdf
“””

from **future** import annotations

import base64
import json
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import fitz  # PyMuPDF
from azure.ai.documentintelligence import DocumentIntelligenceClient
from azure.ai.documentintelligence.models import AnalyzeDocumentRequest
from azure.core.credentials import AzureKeyCredential
from openai import AzureOpenAI

logger = logging.getLogger(**name**)

# —————————————————————————

# Data models

# —————————————————————————

@dataclass
class BoundingBox:
page: int          # 1-indexed
x0: float          # points (72 pts = 1 inch)
y0: float
x1: float
y1: float

@dataclass
class FigureResult:
element_id: str
bbox: BoundingBox
figure_type: str                    # “diagram” | “screenshot” | “unknown”
classification_reasoning: str       # from self-classify call
description: str                    # always present — natural language
structured: dict | None = None      # present for diagrams; may be partial
structured_confidence: str = “low”  # “high” | “medium” | “low”

@dataclass
class PipelineResult:
text_paragraphs: list[str] = field(default_factory=list)
figures: list[FigureResult] = field(default_factory=list)
raw_adi_result: Any = None

# —————————————————————————

# Prompts

# —————————————————————————

CLASSIFY_PROMPT = “””  
Look at this image and classify it. Answer ONLY with a valid JSON object —   
no markdown, no explanation:

{
“figure_type”: “<diagram|screenshot>”,
“reasoning”: “<one sentence explaining your choice>”
}

Guidelines:

- “diagram”: flowcharts, process flows, architecture diagrams, sequence diagrams,   
  network graphs, UML, ER diagrams, decision trees, mind maps — anything with   
  nodes, edges, boxes, arrows conveying a structured process or relationship.
- “screenshot”: photos, UI screenshots, charts (bar/line/pie), scanned images,   
  tables rendered as images, natural scene photos, infographics without graph structure.
  “””

DIAGRAM_PROMPT = “””  
This is a structured diagram (flowchart, process flow, architecture, etc.).

Extract its content and return ONLY a valid JSON object — no markdown fences:

{
“summary”: “<one to two sentence plain-English description of what this diagram shows>”,
“confidence”: “<high|medium|low — your confidence in the structural extraction>”,
“nodes”: [
{“id”: “<short_id>”, “label”: “<node text>”, “type”: “<start|end|process|decision|data|external|unknown>”}
],
“edges”: [
{“from”: “<id>”, “to”: “<id>”, “label”: “<edge label or empty string>”}
],
“notes”: “<anything important that didn’t fit the node/edge model, or empty string>”
}

Rules:

- Every node referenced in edges MUST exist in the nodes list.
- If a label is unreadable, use null.
- If you cannot reliably extract structure, still return the schema but set   
  confidence to “low” and leave nodes/edges as empty lists.
- NEVER omit the summary — it must always be present.
  “””

SCREENSHOT_PROMPT = “””  
Describe this image in detail as it would appear in a document intelligence pipeline.

Focus on:

- What information it conveys (not visual style)
- Any visible text, labels, or numbers
- The type of image (chart, photo, table-as-image, UI screenshot, etc.)
- Key takeaways a reader would get from this figure

Be concise but complete. Plain prose, no bullet points.
“””

# —————————————————————————

# Pipeline

# —————————————————————————

class FigureAwarePipeline:
“””
Parameters
–––––
adi_endpoint : str
Azure Document Intelligence endpoint URL.
adi_key : str
ADI API key.
aoai_endpoint : str
Azure OpenAI endpoint URL.
aoai_key : str
Azure OpenAI API key.
aoai_deployment : str
GPT-4o deployment name (default: “gpt-4o”).
aoai_api_version : str
Azure OpenAI API version.
dpi : int
Resolution for figure crops (default 150 — good balance of quality/tokens).
overlap_tolerance : float
Fraction of paragraph area that must overlap a figure bbox to be filtered (0–1).
“””

```
def __init__(
    self,
    adi_endpoint: str,
    adi_key: str,
    aoai_endpoint: str,
    aoai_key: str,
    aoai_deployment: str = "gpt-4o",
    aoai_api_version: str = "2024-02-01",
    dpi: int = 150,
    overlap_tolerance: float = 0.5,
):
    self.adi_client = DocumentIntelligenceClient(
        endpoint=adi_endpoint,
        credential=AzureKeyCredential(adi_key),
    )
    self.aoai_client = AzureOpenAI(
        azure_endpoint=aoai_endpoint,
        api_key=aoai_key,
        api_version=aoai_api_version,
    )
    self.deployment = aoai_deployment
    self.dpi = dpi
    self.overlap_tolerance = overlap_tolerance

# ------------------------------------------------------------------
# Public API
# ------------------------------------------------------------------

def process(self, pdf_path: str | Path) -> PipelineResult:
    """Full pipeline: ADI → crop → classify → extract → filter."""
    pdf_path = Path(pdf_path)
    logger.info("Starting ADI analysis: %s", pdf_path.name)

    with open(pdf_path, "rb") as f:
        pdf_bytes = f.read()

    poller = self.adi_client.begin_analyze_document(
        "prebuilt-layout",
        body=AnalyzeDocumentRequest(bytes_source=pdf_bytes),
    )
    result = poller.result()
    logger.info("ADI analysis complete.")

    # Step 1: crop figures
    raw_figures = self._crop_figures(result, pdf_bytes)
    logger.info("Cropped %d figure(s).", len(raw_figures))

    # Step 2: classify + extract
    figure_results: list[FigureResult] = []
    for fig in raw_figures:
        try:
            fr = self._process_figure(fig)
            figure_results.append(fr)
        except Exception as e:
            logger.warning("Failed to process figure %s: %s", fig["element_id"], e)

    # Step 3: filter OCR text overlapping figures
    figure_bboxes = [fr.bbox for fr in figure_results]
    clean_paragraphs = self._filter_paragraphs(result, figure_bboxes)

    return PipelineResult(
        text_paragraphs=clean_paragraphs,
        figures=figure_results,
        raw_adi_result=result,
    )

# ------------------------------------------------------------------
# Step 1: Crop figures from PDF bytes
# ------------------------------------------------------------------

def _crop_figures(self, result, pdf_bytes: bytes) -> list[dict]:
    """
    Extract figure image crops using ADI bounding regions.

    ADI polygon format (prebuilt-layout 2024+):
        [x0, y0, x1, y1, x2, y2, x3, y3] in inches
    We take the axis-aligned bounding box of all 4 corners.
    """
    doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    crops = []

    for fig in getattr(result, "figures", []):
        for region in fig.bounding_regions:
            poly = region.polygon  # 8 floats, inches
            xs = [poly[i] for i in range(0, 8, 2)]
            ys = [poly[i] for i in range(1, 8, 2)]

            # Convert inches → PDF points (1 inch = 72 pts)
            x0, y0 = min(xs) * 72, min(ys) * 72
            x1, y1 = max(xs) * 72, max(ys) * 72

            page = doc[region.page_number - 1]
            rect = fitz.Rect(x0, y0, x1, y1)

            # Scale matrix for desired DPI (base PDF unit = 72 dpi)
            scale = self.dpi / 72
            mat = fitz.Matrix(scale, scale)
            pixmap = page.get_pixmap(matrix=mat, clip=rect)
            img_bytes = pixmap.tobytes("png")

            crops.append({
                "element_id": str(fig.id),
                "image_bytes": img_bytes,
                "bbox": BoundingBox(
                    page=region.page_number,
                    x0=x0, y0=y0, x1=x1, y1=y1,
                ),
            })

    doc.close()
    return crops

# ------------------------------------------------------------------
# Step 2: Classify + extract
# ------------------------------------------------------------------

def _process_figure(self, fig: dict) -> FigureResult:
    b64 = base64.b64encode(fig["image_bytes"]).decode()
    image_block = {
        "type": "image_url",
        "image_url": {"url": f"data:image/png;base64,{b64}", "detail": "high"},
    }

    # --- 2a. Self-classify (cheap call, low max_tokens) ---
    figure_type, reasoning = self._classify(image_block)
    logger.info("Figure %s classified as '%s'.", fig["element_id"], figure_type)

    # --- 2b. Route ---
    if figure_type == "diagram":
        description, structured, confidence = self._extract_diagram(image_block)
    else:
        description = self._describe_screenshot(image_block)
        structured, confidence = None, "n/a"

    return FigureResult(
        element_id=fig["element_id"],
        bbox=fig["bbox"],
        figure_type=figure_type,
        classification_reasoning=reasoning,
        description=description,
        structured=structured,
        structured_confidence=confidence,
    )

def _classify(self, image_block: dict) -> tuple[str, str]:
    response = self.aoai_client.chat.completions.create(
        model=self.deployment,
        messages=[{
            "role": "user",
            "content": [
                {"type": "text", "text": CLASSIFY_PROMPT},
                image_block,
            ],
        }],
        max_tokens=100,
        temperature=0,
    )
    raw = response.choices[0].message.content.strip()
    try:
        parsed = json.loads(raw)
        figure_type = parsed.get("figure_type", "screenshot")
        reasoning = parsed.get("reasoning", "")
        if figure_type not in ("diagram", "screenshot"):
            figure_type = "screenshot"
    except json.JSONDecodeError:
        logger.warning("Classify parse failed, defaulting to screenshot. Raw: %s", raw)
        figure_type, reasoning = "screenshot", "parse failed"
    return figure_type, reasoning

def _extract_diagram(self, image_block: dict) -> tuple[str, dict | None, str]:
    response = self.aoai_client.chat.completions.create(
        model=self.deployment,
        messages=[{
            "role": "user",
            "content": [
                {"type": "text", "text": DIAGRAM_PROMPT},
                image_block,
            ],
        }],
        max_tokens=1500,
        temperature=0,
    )
    raw = response.choices[0].message.content.strip()

    # Strip accidental markdown fences
    if raw.startswith("```"):
        raw = raw.split("```")[1]
        if raw.startswith("json"):
            raw = raw[4:]

    try:
        parsed = json.loads(raw)
        summary = parsed.get("summary", "")
        confidence = parsed.get("confidence", "low")
        # Validate required keys exist
        structured = {
            "nodes": parsed.get("nodes", []),
            "edges": parsed.get("edges", []),
            "notes": parsed.get("notes", ""),
        }
        return summary, structured, confidence
    except json.JSONDecodeError:
        # Graceful fallback: return raw as description, no structured data
        logger.warning("Diagram JSON parse failed, falling back to description.")
        return raw, None, "low"

def _describe_screenshot(self, image_block: dict) -> str:
    response = self.aoai_client.chat.completions.create(
        model=self.deployment,
        messages=[{
            "role": "user",
            "content": [
                {"type": "text", "text": SCREENSHOT_PROMPT},
                image_block,
            ],
        }],
        max_tokens=500,
        temperature=0,
    )
    return response.choices[0].message.content.strip()

# ------------------------------------------------------------------
# Step 3: Filter paragraphs overlapping figure regions
# ------------------------------------------------------------------

def _filter_paragraphs(self, result, figure_bboxes: list[BoundingBox]) -> list[str]:
    """
    Remove paragraphs whose bounding box significantly overlaps any figure region.
    Uses a simple area-overlap fraction check.
    """
    clean = []
    for para in getattr(result, "paragraphs", []):
        if not para.bounding_regions:
            clean.append(para.content)
            continue

        para_region = para.bounding_regions[0]
        para_poly = para_region.polygon
        para_page = para_region.page_number

        p_xs = [para_poly[i] * 72 for i in range(0, 8, 2)]
        p_ys = [para_poly[i] * 72 for i in range(1, 8, 2)]
        p_box = BoundingBox(
            page=para_page,
            x0=min(p_xs), y0=min(p_ys),
            x1=max(p_xs), y1=max(p_ys),
        )

        if not self._overlaps_any_figure(p_box, figure_bboxes):
            clean.append(para.content)
        else:
            logger.debug("Filtered overlapping paragraph: '%s...'", para.content[:40])

    return clean

def _overlaps_any_figure(
    self, para: BoundingBox, figures: list[BoundingBox]
) -> bool:
    for fig in figures:
        if para.page != fig.page:
            continue
        # Intersection area
        ix0 = max(para.x0, fig.x0)
        iy0 = max(para.y0, fig.y0)
        ix1 = min(para.x1, fig.x1)
        iy1 = min(para.y1, fig.y1)

        if ix1 <= ix0 or iy1 <= iy0:
            continue  # no intersection

        intersection = (ix1 - ix0) * (iy1 - iy0)
        para_area = (para.x1 - para.x0) * (para.y1 - para.y0)

        if para_area == 0:
            continue

        overlap_fraction = intersection / para_area
        if overlap_fraction >= self.overlap_tolerance:
            return True
    return False
```

# —————————————————————————

# Example usage

# —————————————————————————

if **name** == “**main**”:
import os

```
logging.basicConfig(level=logging.INFO)

pipeline = FigureAwarePipeline(
    adi_endpoint=os.environ["ADI_ENDPOINT"],
    adi_key=os.environ["ADI_KEY"],
    aoai_endpoint=os.environ["AOAI_ENDPOINT"],
    aoai_key=os.environ["AOAI_KEY"],
    aoai_deployment="gpt-4o",          # your Azure deployment name
)

result = pipeline.process("your_document.pdf")

print(f"\n=== Text paragraphs ({len(result.text_paragraphs)}) ===")
for p in result.text_paragraphs[:5]:
    print(" •", p[:120])

print(f"\n=== Figures ({len(result.figures)}) ===")
for fig in result.figures:
    print(f"\n[{fig.element_id}] type={fig.figure_type} confidence={fig.structured_confidence}")
    print(f"  Reasoning : {fig.classification_reasoning}")
    print(f"  Description: {fig.description[:200]}")
    if fig.structured:
        print(f"  Nodes : {len(fig.structured['nodes'])}")
        print(f"  Edges : {len(fig.structured['edges'])}")
        print(f"  Notes : {fig.structured['notes']}")
```