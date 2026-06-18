export type DocumentCapability =
  | "scalar_merge"
  | "repeating_blocks"
  | "tables"
  | "multi_section"
  | "conditional"
  | "rich_text";

export interface DocumentType {
  id: string;
  displayName: string;
  templateFile: string;
  locale: string;
  description: string;
  capabilities: DocumentCapability[];
}

export interface RegistryEntry extends DocumentType {
  manifestPath: string;
}
