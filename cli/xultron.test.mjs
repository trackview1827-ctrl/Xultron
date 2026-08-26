import assert from "node:assert/strict";
import { execFileSync } from "node:child_process";
import { mkdir, mkdtemp, readFile, rm, writeFile } from "node:fs/promises";
import os from "node:os";
import path from "node:path";
import test from "node:test";

import {
  parseArgs,
  repositoriesEqual,
  resolveInstallDir,
  runCli,
} from "./xultron-lib.mjs";

function git(cwd, ...args) {
  return execFileSync("git", args, { cwd, encoding: "utf8", stdio: ["ignore", "pipe", "pipe"] }).trim();
}

function bufferedIo() {
  const stdout = [];
  const stderr = [];
  return {
    stdout,
    stderr,
    io: {
      stdout: (message) => stdout.push(String(message)),
      stderr: (message) => stderr.push(String(message)),
    },
  };
}

test("argument parsing and repository normalization stay deterministic", () => {
  assert.deepEqual(parseArgs(["install", "--dir", "~/apps/Xultron", "--skip-bootstrap"]), {
    command: "install",
    directory: "~/apps/Xultron",
    skipBootstrap: true,
  });
  assert.equal(resolveInstallDir(undefined, {}, "/home/example"), "/home/example/.xultron/app");
  assert.equal(resolveInstallDir("~/apps/Xultron", {}, "/home/example"), "/home/example/apps/Xultron");
  assert.equal(
    repositoriesEqual("git@github.com:trackview1827-ctrl/Xultron.git", "https://github.com/trackview1827-ctrl/Xultron"),
    true,
  );
  assert.throws(() => parseArgs(["install", "--unknown"]), /Bilinmeyen seçenek/);
});

test("help and doctor exercise the public CLI without changing files", async () => {
  const help = bufferedIo();
  await runCli(["help"], { io: help.io });
  assert.match(help.stdout.join("\n"), /npx --yes github:trackview1827-ctrl\/Xultron install/);

  const doctor = bufferedIo();
  await runCli(["doctor"], { io: doctor.io, stdio: "ignore" });
  const output = doctor.stdout.join("\n");
  assert.match(output, /✓ Git:/);
  assert.match(output, /✓ Node\.js:/);
  assert.match(output, /✓ npm:/);
  assert.match(output, /✓ Python:/);
});

test("install clones, update fast-forwards, and dirty or unrelated targets fail closed", async () => {
  const scratchBase = process.env.JCODE_SCRATCH_DIR || os.tmpdir();
  await mkdir(scratchBase, { recursive: true });
  const workspace = await mkdtemp(path.join(scratchBase, "xultron-cli-test-"));
  const remote = path.join(workspace, "remote.git");
  const seed = path.join(workspace, "seed");
  const target = path.join(workspace, "installed", "app");
  const unrelated = path.join(workspace, "unrelated");

  try {
    await mkdir(remote, { recursive: true });
    git(workspace, "init", "--bare", remote);
    await mkdir(path.join(seed, "scripts"), { recursive: true });
    await mkdir(path.join(seed, "backend"), { recursive: true });
    await mkdir(path.join(seed, "frontend"), { recursive: true });
    git(workspace, "init", seed);
    git(seed, "config", "user.name", "Xultron CLI Test");
    git(seed, "config", "user.email", "xultron-cli@example.invalid");
    await writeFile(path.join(seed, "README.md"), "fixture-v1\n", "utf8");
    await writeFile(path.join(seed, "scripts", "bootstrap.sh"), "#!/usr/bin/env bash\nexit 0\n", "utf8");
    await writeFile(path.join(seed, "backend", "run.py"), "print('fixture')\n", "utf8");
    await writeFile(path.join(seed, "frontend", "package.json"), "{}\n", "utf8");
    git(seed, "add", ".");
    git(seed, "commit", "-m", "fixture v1");
    git(seed, "branch", "-M", "main");
    git(seed, "remote", "add", "origin", remote);
    git(seed, "push", "-u", "origin", "main");

    const testEnv = { ...process.env, XULTRON_REPOSITORY: remote };
    const installOutput = bufferedIo();
    await runCli(["install", "--dir", target, "--skip-bootstrap"], {
      io: installOutput.io,
      env: testEnv,
      stdio: "ignore",
    });
    assert.equal(await readFile(path.join(target, "README.md"), "utf8"), "fixture-v1\n");
    assert.match(installOutput.stdout.join("\n"), /Xultron hazır/);

    await writeFile(path.join(seed, "README.md"), "fixture-v2\n", "utf8");
    git(seed, "add", "README.md");
    git(seed, "commit", "-m", "fixture v2");
    git(seed, "push", "origin", "main");

    await runCli(["update", "--dir", target, "--skip-bootstrap"], {
      io: bufferedIo().io,
      env: testEnv,
      stdio: "ignore",
    });
    assert.equal(await readFile(path.join(target, "README.md"), "utf8"), "fixture-v2\n");

    await writeFile(path.join(target, "README.md"), "dirty\n", "utf8");
    await assert.rejects(
      runCli(["update", "--dir", target, "--skip-bootstrap"], {
        io: bufferedIo().io,
        env: testEnv,
        stdio: "ignore",
      }),
      /commit edilmemiş yerel değişiklikler/,
    );

    git(target, "restore", "README.md");
    git(target, "checkout", "-b", "feature-test");
    await assert.rejects(
      runCli(["update", "--dir", target, "--skip-bootstrap"], {
        io: bufferedIo().io,
        env: testEnv,
        stdio: "ignore",
      }),
      /etkin dal feature-test, beklenen dal main/,
    );

    await mkdir(unrelated, { recursive: true });
    await writeFile(path.join(unrelated, "keep.txt"), "do not overwrite\n", "utf8");
    await assert.rejects(
      runCli(["install", "--dir", unrelated, "--skip-bootstrap"], {
        io: bufferedIo().io,
        env: testEnv,
        stdio: "ignore",
      }),
      /geçerli bir Xultron Git kurulumu değil/,
    );
    assert.equal(await readFile(path.join(unrelated, "keep.txt"), "utf8"), "do not overwrite\n");
  } finally {
    await rm(workspace, { recursive: true, force: true });
  }
});
