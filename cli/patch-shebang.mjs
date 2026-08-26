import { access, chmod, readFile, writeFile } from "node:fs/promises";
import path from "node:path";
import { fileURLToPath } from "node:url";

const cliDirectory = path.dirname(fileURLToPath(import.meta.url));
const packageRoot = path.dirname(cliDirectory);
const sourceCheckout = path.join(packageRoot, ".git");
const launcher = path.join(cliDirectory, "xultron.mjs");

try {
  await access(sourceCheckout);
  process.exit(0);
} catch {
  // Installed npm packages do not contain .git and need a platform-native shebang.
}

const content = await readFile(launcher, "utf8");
const patched = content.replace(/^#![^\n]*/, `#!${process.execPath}`);
if (patched === content && !content.startsWith(`#!${process.execPath}`)) {
  throw new Error("Xultron CLI launcher shebang could not be patched safely.");
}
await writeFile(launcher, patched, "utf8");
await chmod(launcher, 0o755);
