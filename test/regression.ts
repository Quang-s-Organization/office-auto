// Regression test: dump replayable batch from a rendered .docx
import { officecli } from "../src/render/officecli.js";

async function main() {
  const outputPath = process.argv[2] || "out/test_output.docx";

  console.log(`Dumping replayable batch from: ${outputPath}`);
  const dump = officecli(["dump", outputPath]);

  if (!dump.success) {
    console.error("Dump failed:", dump.error);
    process.exit(1);
  }

  console.log(JSON.stringify(dump.data, null, 2));
  console.log("\n✅ Dump successful — can replay with: officecli batch <template> --input dump.json");
}

main().catch((err) => {
  console.error(err);
  process.exit(1);
});
