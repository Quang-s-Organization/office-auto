// Quick smoke test for binding-planner and docx-renderer
import { plan } from "../src/render/binding-planner.js";
import type { Manifest, Content } from "../src/manifest/schema.js";

const testManifest: Manifest = {
  template_id: "quyet-dinh-001",
  mode: "strict-sdt",
  locale: "vi-VN",
  fields: {
    agency_name: {
      sdt_tag: "agency_name",
      resolved_path: "/body/sdt[1]",
      type: "scalar",
      max_len: 120,
    },
    document_number: {
      sdt_tag: "doc_no",
      resolved_path: "/body/sdt[2]",
      type: "scalar",
      pattern: "^[0-9]+/[A-ZĐ-]+$",
    },
    issue_date: {
      sdt_tag: "issue_date",
      resolved_path: "/body/sdt[3]",
      type: "date",
    },
  },
  repeaters: {
    decision_items: {
      clone_from: "/body/p[@style='DieuKhoan'][1]",
      insert_anchor: {
        mode: "after",
        path: "/body/p[@style='DieuKhoan'][last()]",
      },
      item_fields: { title: "run[1]", content: "run[2]" },
    },
  },
  tables: {},
  structural_invariants: {},
};

const testContent: Content = {
  template_id: "quyet-dinh-001",
  locale: "vi-VN",
  fields: {
    agency_name: "UBND Quận 1",
    document_number: "15/QĐ-UBND",
    issue_date: "2026-06-17",
  },
  blocks: {
    decision_items: [
      { title: "Điều 1", content: "Nội dung điều 1" },
      { title: "Điều 2", content: "Nội dung điều 2" },
    ],
  },
  tables: {},
};

// Test binding-planner
const ops = plan(testContent, testManifest);
console.log("Ops generated:", JSON.stringify(ops, null, 2));

// Verify expected ops
const scalarOps = ops.filter((o) => o.kind === "set");
const cloneOps = ops.filter((o) => o.kind === "clone");

console.log(`\nScalar set ops: ${scalarOps.length} (expected 3)`);
console.log(`Clone ops: ${cloneOps.length} (expected 2)`);

for (const op of scalarOps) {
  console.log(`  set ${op.path} -> ${op.props.text}`);
}

const pass = scalarOps.length === 3 && cloneOps.length === 2;
console.log(`\n${pass ? "✅ PASS" : "❌ FAIL"}: binding-planner smoke test`);
process.exit(pass ? 0 : 1);
