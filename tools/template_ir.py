"""Data classes for Template IR (Intermediate Representation).

Represents structured knowledge extracted from a DOCX template at runtime.
Produced by template_inspector.py, consumed by doc_composer.py.
"""

from __future__ import annotations
from dataclasses import dataclass, field, asdict
from typing import Optional


@dataclass
class StylePrototype:
    """A single candidate paragraph in the template that can be cloned."""
    style_name: str               # "Heading1", "Heading2", "Heading3", "Normal"
    para_id: str                  # Stable OOXML identifier for clone operations
    text: str                     # Paragraph text (for context matching)
    effective_size: Optional[str]  # e.g. "16pt", "14pt", "12pt"
    effective_font: Optional[str]  # e.g. "Calibri", "Times New Roman"
    bold: Optional[bool]
    outline_level: Optional[int]   # 1, 2, 3 for headings; None for Normal
    ind_first_line: Optional[str]  # e.g. "1.27cm"
    section_context: str           # "CHAPTER", "ACKNOWLEDGEMENTS", "APPENDIX", etc.
    space_before: Optional[str]    # e.g. "24pt"
    space_after: Optional[str]     # e.g. "6pt"
    alignment: Optional[str]       # e.g. "center", "left"
    line_spacing: Optional[str]    # e.g. "1.5x"
    explicit_size: Optional[str]   # markRPr.size if set (preferred over effective)
    explicit_font: Optional[str]   # font.ea (east-asia font) if explicitly set


@dataclass
class TemplateIR:
    """Complete intermediate representation of a DOCX template.

    Contains all discovered style prototypes, the document outline,
    and pre-selected best prototypes for each heading/body style.
    """
    file_path: str
    prototypes: dict[str, list[StylePrototype]]  # style_name -> candidates
    outline: list[dict]                           # ordered list of {level, text, paraId}
    best_prototypes: dict[str, StylePrototype]    # style_name -> best match
    all_heading_ids: list[str]                    # paraIds of ALL heading paragraphs
    preserve_contexts: list[str] = field(
        default_factory=lambda: [
            "ACKNOWLEDGEMENTS", "ABSTRACT", "TABLE OF CONTENTS",
            "LIST OF ABBREVIATIONS", "LIST OF TABLES", "REFERENCES",
            "APPENDIX", "SUPERVISOR"
        ]
    )
    replace_contexts: list[str] = field(
        default_factory=lambda: [
            "CHAPTER", "INTRODUCTION"
        ]
    )

    def to_json(self) -> dict:
        return {
            "file_path": self.file_path,
            "prototypes": {
                style: [asdict(p) for p in protos]
                for style, protos in self.prototypes.items()
            },
            "outline": self.outline,
            "best_prototypes": {
                style: asdict(p) for style, p in self.best_prototypes.items()
            },
            "all_heading_ids": self.all_heading_ids,
            "preserve_contexts": self.preserve_contexts,
            "replace_contexts": self.replace_contexts,
        }

    @classmethod
    def from_json(cls, data: dict) -> TemplateIR:
        protos = {
            style: [StylePrototype(**p) for p in plist]
            for style, plist in data.get("prototypes", {}).items()
        }
        best = {
            style: StylePrototype(**p)
            for style, p in data.get("best_prototypes", {}).items()
        }
        return cls(
            file_path=data["file_path"],
            prototypes=protos,
            outline=data.get("outline", []),
            best_prototypes=best,
            all_heading_ids=data.get("all_heading_ids", []),
            preserve_contexts=data.get(
                "preserve_contexts",
                ["ACKNOWLEDGEMENTS", "ABSTRACT", "TABLE OF CONTENTS",
                 "LIST OF ABBREVIATIONS", "LIST OF TABLES", "REFERENCES",
                 "APPENDIX", "SUPERVISOR"]
            ),
            replace_contexts=data.get(
                "replace_contexts",
                ["CHAPTER", "INTRODUCTION"]
            ),
        )
