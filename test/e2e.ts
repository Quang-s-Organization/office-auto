// End-to-end pipeline test — deterministic only (no LLM)
// Tests: auditor, binding-planner, docx-renderer, validator
// against the real format_template.docx

import { plan } from "../src/render/binding-planner.js";
import { render } from "../src/render/docx-renderer.js";
import { validate } from "../src/validate/validator.js";
import { officecli } from "../src/render/officecli.js";
import type { Manifest, Content } from "../src/manifest/schema.js";

const TEMPLATE = "templates/format_template.docx";

// Manual manifest matching the real format_template.docx
const manifest: Manifest = {
  template_id: "format_template",
  mode: "legacy-anchor",
  locale: "vi-VN",
  fields: {
    gioi_thieu_title: {
      sdt_tag: "title_gioi_thieu",
      resolved_path: "/body/p[@paraId=04C2E2D0]",
      type: "scalar",
    },
    co_so_ly_thuyet_title: {
      sdt_tag: "title_co_so",
      resolved_path: "/body/p[@paraId=051169A1]",
      type: "scalar",
    },
    ket_luan_title: {
      sdt_tag: "title_ket_luan",
      resolved_path: "/body/p[@paraId=37D21BE6]",
      type: "scalar",
    },
    tai_lieu_title: {
      sdt_tag: "title_tai_lieu",
      resolved_path: "/body/p[@paraId=7FA7A178]",
      type: "scalar",
    },
  },
  repeaters: {},
  tables: {},
  structural_invariants: {
    required_sections: ["GIỚI THIỆU", "KẾT LUẬN", "TÀI LIỆU THAM KHẢO"],
  },
};

const content: Content = {
  template_id: "format_template",
  locale: "vi-VN",
  fields: {
    gioi_thieu_title: "MỞ ĐẦU",
    co_so_ly_thuyet_title: "NỀN TẢNG LÝ THUYẾT",
    ket_luan_title: "TỔNG KẾT",
    tai_lieu_title: "NGUỒN THAM KHẢO",
  },
  blocks: {},
  tables: {},
};

async function main() {
  console.log("=== E2E PIPELINE TEST ===\n");

  // Step 1: Plan
  console.log("1. Planning operations...");
  const ops = plan(content, manifest);
  console.log(`   Generated ${ops.length} ops`);

  // Step 2: Render
  console.log("2. Rendering to output.docx...");
  const outPath = await render(ops, TEMPLATE, "out/test_output.docx");
  console.log(`   Output: ${outPath}`);

  // Step 3: Verify output exists and is valid docx
  console.log("3. Verifying output...");
  const verify = officecli(["validate", outPath]);
  console.log(`   Validate: ${verify.success ? "OK" : "FAILED"}`);

  // Step 4: Check content was written
  const gioiThieu = officecli(["query", outPath, 'p[@paraId=04C2E2D0]']);
  const newTitle = gioiThieu.success ? gioiThieu.data?.results?.[0]?.text : "N/A";
  console.log(`   Title at paraId=04C2E2D0: "${newTitle}" (expected "MỞ ĐẦU")`);

  const ketLuan = officecli(["query", outPath, 'p[@paraId=37D21BE6]']);
  const ketLuanTitle = ketLuan.success ? ketLuan.data?.results?.[0]?.text : "N/A";
  console.log(`   Title at paraId=37D21BE6: "${ketLuanTitle}" (expected "TỔNG KẾT")`);

  // Step 5: Validation
  console.log("4. Running L4 validation...");
  const validation = await validate(outPath, manifest);
  console.log(`   Schema OK: ${validation.schema?.ok ?? false}`);
  console.log(`   Issues: ${validation.issues.length}`);
  console.log(`   Leftover placeholders: ${validation.leftover.length}`);
  console.log(`   Invariants OK: ${validation.invariants.ok}`);

  // Step 6: Check batch.json was logged
  console.log("5. Audit log...");
  const { existsSync, readFileSync } = await import("node:fs");
  const batchLog = existsSync("out/batch.json");
  console.log(`   out/batch.json logged: ${batchLog}`);

  // Final verdict
  const allPass =
    verify.success &&
    newTitle === "MỞ ĐẦU" &&
    ketLuanTitle === "TỔNG KẾT" &&
    batchLog;

  console.log(`\n${allPass ? "✅ PASS" : "❌ FAIL"}: end-to-end pipeline test`);
  process.exit(allPass ? 0 : 1);
}

main().catch((err) => {
  console.error("Fatal:", err);
  process.exit(1);
});
