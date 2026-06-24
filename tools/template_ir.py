"""Data classes for Template IR (Intermediate Representation).

Represents structured knowledge extracted from a DOCX template at runtime.
Produced by template_inspector.py, consumed by planner.py / doc_composer.py.

v5: adds `body_sequence` (ordered body paragraphs) and `body_style`
(discovered style used for body text) so the planner can compute the
removable content region and emit an officecli batch program without
any hardcoded assumptions.
"""

from __future__ import annotations
from dataclasses import dataclass, field, asdict
from typing import Optional


@dataclass
class StylePrototype:
    """A single candidate paragraph in the template, used to read style + props."""
    style_name: str               # "Heading1", "Heading2", "Heading3", "Normal", ...
    para_id: str                  # Stable OOXML identifier
    text: str                     # Paragraph text (for context matching)
    effective_size: Optional[str]  # e.g. "16pt"  (readback: effective.size)
    effective_font: Optional[str]  # e.g. "Calibri" (readback: effective.font.ascii)
    bold: Optional[bool]
    outline_level: Optional[int]
    ind_first_line: Optional[str]  # readback: ind.firstLine ; SET key: firstLineIndent
    section_context: str
    space_before: Optional[str]
    space_after: Optional[str]
    alignment: Optional[str]
    line_spacing: Optional[str]
    explicit_size: Optional[str]
    explicit_font: Optional[str]

    def build_props(self) -> dict:
        """Return officecli SET-keys for reconstructing a paragraph of this style.

        Maps discovered (readback) values to the correct SET property keys.
        Only includes keys that were actually discovered (no hardcoded defaults).
        """
        props: dict[str, str] = {}
        if self.style_name:
            props["style"] = self.style_name
        size = self.explicit_size or self.effective_size
        if size:
            props["size"] = size
        font = self.explicit_font or self.effective_font
        if font:
            props["font.ea"] = font
        if self.ind_first_line and self.ind_first_line not in ("0", "0pt", "0cm"):
            props["firstLineIndent"] = self.ind_first_line   # SET key (read back as ind.firstLine)
        if self.alignment:
            props["align"] = self.alignment
        if self.line_spacing:
            props["lineSpacing"] = self.line_spacing
        return props


@dataclass
class TemplateIR:
    """Complete intermediate representation of a DOCX template."""
    file_path: str
    prototypes: dict[str, list[StylePrototype]]   # style_name -> candidates
    outline: list[dict]                            # ordered headings {index,text,style,para_id}
    best_prototypes: dict[str, StylePrototype]     # style_name -> best match
    all_heading_ids: list[str]
    body_sequence: list[dict] = field(default_factory=list)
    # body_sequence: ordered [{para_id, style, has_text, is_heading, outline_level}]
    body_style: Optional[str] = None               # discovered style used for body text
    preserve_contexts: list[str] = field(
        default_factory=lambda: [
            "ACKNOWLEDGEMENTS", "ABSTRACT", "TABLE OF CONTENTS",
            "LIST OF ABBREVIATIONS", "LIST OF TABLES", "REFERENCES",
            "APPENDIX", "SUPERVISOR"
        ]
    )
    replace_contexts: list[str] = field(
        default_factory=lambda: ["CHAPTER", "INTRODUCTION"]
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
            "body_sequence": self.body_sequence,
            "body_style": self.body_style,
            "preserve_contexts": self.preserve_contexts,
            "replace_contexts": self.replace_contexts,
        }

    @classmethod
    def from_json(cls, data: dict) -> "TemplateIR":
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
            body_sequence=data.get("body_sequence", []),
            body_style=data.get("body_style"),
            preserve_contexts=data.get(
                "preserve_contexts",
                ["ACKNOWLEDGEMENTS", "ABSTRACT", "TABLE OF CONTENTS",
                 "LIST OF ABBREVIATIONS", "LIST OF TABLES", "REFERENCES",
                 "APPENDIX", "SUPERVISOR"]
            ),
            replace_contexts=data.get("replace_contexts", ["CHAPTER", "INTRODUCTION"]),
        )
