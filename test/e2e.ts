// End-to-end pipeline test — deterministic only (no LLM)
// Tests: auditor, binding-planner, docx-renderer, validator
// against the real format_template.docx

import { plan } from "../src/render/binding-planner.js";
import { render } from "../src/render/docx-renderer.js";
import { validate } from "../src/validate/validator.js";
import { officecli } from "../src/render/officecli.js";
import type { Manifest, Content } from "../src/manifest/schema.js";

const TEMPLATE = "templates/format_template.docx";

// Manual manifest matching the real format_template.docx from its manifest
const manifest: Manifest = {
  template_id: "format_template",
  mode: "legacy-anchor",
  locale: "vi-VN",
  fields: {
    gioi_thieu: {
      sdt_tag: "gioi_thieu",
      resolved_path: "/body/p[@paraId=47DD4FDA]",
      type: "scalar",
      heading: "GIỚI THIỆU",
      heading_path: "/body/p[@paraId=04C2E2D0]",
    },
    tam_quan_trong: {
      sdt_tag: "tam_quan_trong_du_lieu_anh_huan_luyen_tr",
      resolved_path: "/body/p[@paraId=3B91656F]",
      type: "scalar",
      heading: "Tầm quan trọng dữ liệu ảnh huấn luyện trong thị giác máy tính",
      heading_path: "/body/p[@paraId=05E2D782]",
    },
    thu_thap: {
      sdt_tag: "thu_thap_du_lieu_anh_thu_cong",
      resolved_path: "/body/p[@paraId=4C9C80FE]",
      type: "scalar",
      heading: "Thu thập dữ liệu ảnh thủ công",
      heading_path: "/body/p[@paraId=15D7D3CD]",
    },
    ket_luan: {
      sdt_tag: "ket_luan",
      resolved_path: "/body/p[@paraId=7AFAB967]",
      type: "scalar",
      heading: "KẾT LUẬN",
      heading_path: "/body/p[@paraId=37D21BE6]",
    },
  },
  repeaters: {},
  tables: {},
  structural_invariants: {
    required_sections: ["GIỚI THIỆU", "KẾT LUẬN"],
  },
};

const content: Content = {
  template_id: "format_template",
  locale: "vi-VN",
  fields: {
    gioi_thieu: "MỞ ĐẦU",
    tam_quan_trong: "NỀN TẢNG LÝ THUYẾT",
    thu_thap: "THU THẬP DỮ LIỆU",
    ket_luan: "TỔNG KẾT",
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
  const outPath = await render(ops, TEMPLATE, "out/test_output.docx", manifest);
  console.log(`   Output: ${outPath}`);

  // Step 3: Verify output exists and is valid docx
  console.log("3. Verifying output...");
  const verify = officecli(["validate", outPath]);
  console.log(`   Validate: ${verify.success ? "OK" : "FAILED"}`);

  // Step 4: Check content was written
  const gioiThieu = officecli(["query", outPath, 'p[@paraId=47DD4FDA]']);
  const newTitle = gioiThieu.success ? gioiThieu.data?.results?.[0]?.text : "N/A";
  console.log(`   Title at paraId=47DD4FDA: "${newTitle}" (expected "MỞ ĐẦU")`);

  const ketLuan = officecli(["query", outPath, 'p[@paraId=7AFAB967]']);
  const ketLuanTitle = ketLuan.success ? ketLuan.data?.results?.[0]?.text : "N/A";
  console.log(`   Title at paraId=7AFAB967: "${ketLuanTitle}" (expected "TỔNG KẾT")`);

  // Step 5: Validation
  console.log("4. Running L4 validation...");
  const validation = await validate(outPath, manifest);
  console.log(`   Schema OK: ${validation.schema?.ok ?? false}`);
  console.log(`   Issues: ${validation.issues.length}`);
  console.log(`   Leftover placeholders: ${validation.leftover.length}`);
  console.log(`   Invariants OK: ${validation.invariants.ok}`);

  // Step 6: Check batch log was written with timestamp
  console.log("5. Audit log...");
  const { existsSync, readdirSync } = await import("node:fs");
  const outFiles = readdirSync("out").filter(f => f.startsWith("batch-"));
  const batchLog = outFiles.length > 0;
  console.log(`   Batch log files found: ${outFiles.length}`);

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
