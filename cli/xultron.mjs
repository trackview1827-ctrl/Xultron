#!/usr/bin/env node

import { runCli } from "./xultron-lib.mjs";

try {
  await runCli(process.argv.slice(2));
} catch (error) {
  process.stderr.write(`Xultron CLI hatası: ${error.message}\n`);
  process.exitCode = 1;
}
