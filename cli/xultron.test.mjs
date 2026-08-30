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

async function createCliCheckout(target, { runnable = true } = {}) {
  await mkdir(path.join(target, ".git"), { recursive: true });
  await mkdir(path.join(target, "scripts"), { recursive: true });
  await mkdir(path.join(target, "backend"), { recursive: true });
  await mkdir(path.join(target, "frontend"), { recursive: true });
  await writeFile(path.join(target, "scripts", "bootstrap.sh"), "#!/usr/bin/env bash\n", "utf8");
  await writeFile(path.join(target, "backend", "run.py"), "print('fixture')\n", "utf8");
  await writeFile(path.join(target, "frontend", "package.json"), "{}\n", "utf8");
  if (runnable) {
    await mkdir(path.join(target, "backend", ".venv", "bin"), { recursive: true });
    await writeFile(path.join(target, "backend", ".venv", "bin", "python"), "", "utf8");
    await mkdir(path.join(target, "frontend", "node_modules"), { recursive: true });
  }
}

function cliProcessRunner({ target, repository, accountExists, calls }) {
  return async (command, args, options = {}) => {
    calls.push({ command, args: [...args], options: { ...options } });
    if (args[0] === "--version") {
      const versions = {
        git: "git version 2.45.0",
        node: "v20.0.0",
        npm: "10.0.0",
        python: "Python 3.11.0",
      };
      return { stdout: versions[command], stderr: "" };
    }
    if (command === "git" && args[0] === "clone") {
      await createCliCheckout(target, { runnable: false });
      return { stdout: "", stderr: "" };
    }
    if (command === "git" && args.join(" ") === "remote get-url origin") {
      return { stdout: repository, stderr: "" };
    }
    if (command === "bash" && args[0] === path.join(target, "scripts", "bootstrap.sh")) {
      await mkdir(path.join(target, "backend", ".venv", "bin"), { recursive: true });
      await writeFile(path.join(target, "backend", ".venv", "bin", "python"), "", "utf8");
      await mkdir(path.join(target, "frontend", "node_modules"), { recursive: true });
      return { stdout: "", stderr: "" };
    }
    if (args.includes("provision-local-account")) {
      const request = JSON.parse(options.input);
      return {
        stdout: JSON.stringify(request.action === "status" ? { accountExists } : { created: true }),
        stderr: "",
      };
    }
    return { stdout: "", stderr: "" };
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

test("public version output stays synchronized with package.json", async () => {
  const packageMetadata = JSON.parse(await readFile(new URL("../package.json", import.meta.url), "utf8"));
  const output = bufferedIo();

  await runCli(["--version"], { io: output.io });

  assert.deepEqual(output.stdout, [packageMetadata.version]);
});

test("doctor accepts Ubuntu-style python3 when python is unavailable", async () => {
  const calls = [];
  const processRunner = async (command, args) => {
    calls.push({ command, args });
    if (command === "python") throw new Error("spawn python ENOENT");
    const versions = {
      git: "git version 2.45.0",
      node: "v20.0.0",
      npm: "10.0.0",
      python3: "Python 3.12.3",
    };
    return { stdout: versions[command], stderr: "" };
  };
  const output = bufferedIo();

  await runCli(["doctor"], { io: output.io, processRunner, stdio: "ignore" });

  assert.ok(calls.some(({ command }) => command === "python"));
  assert.ok(calls.some(({ command }) => command === "python3"));
  assert.match(output.stdout.join("\n"), /✓ Python: Python 3\.12\.3/);
});

test("doctor falls back from an old python and reports both missing commands", async () => {
  const baseVersions = {
    git: "git version 2.45.0",
    node: "v20.0.0",
    npm: "10.0.0",
  };
  const fallbackOutput = bufferedIo();
  await runCli(["doctor"], {
    io: fallbackOutput.io,
    processRunner: async (command) => ({
      stdout: command === "python" ? "Python 3.10.12" : command === "python3" ? "Python 3.12.3" : baseVersions[command],
      stderr: "",
    }),
    stdio: "ignore",
  });
  assert.match(fallbackOutput.stdout.join("\n"), /✓ Python: Python 3\.12\.3/);

  const missingOutput = bufferedIo();
  await assert.rejects(
    runCli(["doctor"], {
      io: missingOutput.io,
      processRunner: async (command) => {
        if (command === "python" || command === "python3") throw new Error(`spawn ${command} ENOENT`);
        return { stdout: baseVersions[command], stderr: "" };
      },
      stdio: "ignore",
    }),
    /Python >= 3\.11\.0/,
  );
  assert.match(missingOutput.stdout.join("\n"), /python: spawn python ENOENT; python3: spawn python3 ENOENT/);
});

test("no arguments install a missing checkout, bootstrap it, provision status, and start", async () => {
  const scratchBase = process.env.JCODE_SCRATCH_DIR || os.tmpdir();
  const workspace = await mkdtemp(path.join(scratchBase, "xultron-cli-launch-"));
  const target = path.join(workspace, ".xultron", "app");
  const repository = "https://github.com/trackview1827-ctrl/Xultron.git";
  const calls = [];

  try {
    await runCli([], {
      env: { XULTRON_HOME: target, XULTRON_REPOSITORY: repository },
      io: bufferedIo().io,
      interactive: false,
      processRunner: cliProcessRunner({ target, repository, accountExists: true, calls }),
      stdio: "ignore",
    });

    assert.ok(calls.some(({ command, args }) => command === "git" && args[0] === "clone"));
    assert.ok(calls.some(({ command, args }) => command === "bash" && args[0].endsWith("bootstrap.sh")));
    assert.ok(calls.some(({ args, options }) => (
      args.includes("provision-local-account") && JSON.parse(options.input).action === "status"
    )));
    assert.ok(calls.some(({ command, args }) => command.endsWith("/python") && args[0] === "run.py"));
  } finally {
    await rm(workspace, { recursive: true, force: true });
  }
});

test("no arguments reuse a runnable installation without bootstrap or credential prompts", async () => {
  const scratchBase = process.env.JCODE_SCRATCH_DIR || os.tmpdir();
  const workspace = await mkdtemp(path.join(scratchBase, "xultron-cli-existing-"));
  const target = path.join(workspace, "app");
  const repository = "https://github.com/trackview1827-ctrl/Xultron.git";
  const calls = [];
  let prompted = false;

  try {
    await createCliCheckout(target);
    const output = bufferedIo();
    await runCli([], {
      env: { XULTRON_HOME: target, XULTRON_REPOSITORY: repository },
      io: output.io,
      interactive: true,
      prompt: async () => {
        prompted = true;
        throw new Error("prompt must not run for an existing account");
      },
      processRunner: cliProcessRunner({ target, repository, accountExists: true, calls }),
      stdio: "ignore",
    });

    assert.equal(prompted, false);
    assert.match(output.stdout.join("\n"), /Mevcut Xultron kurulumu kullanılacak/);
    assert.equal(calls.some(({ command, args }) => command === "git" && args[0] === "clone"), false);
    assert.equal(calls.some(({ command, args }) => command === "bash" && args[0].endsWith("bootstrap.sh")), false);
  } finally {
    await rm(workspace, { recursive: true, force: true });
  }
});

test("first account credentials use hidden prompts and stdin without argv or environment leakage", async () => {
  const scratchBase = process.env.JCODE_SCRATCH_DIR || os.tmpdir();
  const workspace = await mkdtemp(path.join(scratchBase, "xultron-cli-credentials-"));
  const target = path.join(workspace, "app");
  const repository = "https://github.com/trackview1827-ctrl/Xultron.git";
  const username = "secure-user-fixture";
  const password = "correct horse battery staple fixture";
  const answers = [username, password, password];
  const prompts = [];
  const calls = [];

  try {
    await createCliCheckout(target);
    await runCli([], {
      env: { XULTRON_HOME: target, XULTRON_REPOSITORY: repository },
      io: bufferedIo().io,
      interactive: true,
      prompt: async (question) => {
        prompts.push(question);
        return answers.shift();
      },
      processRunner: cliProcessRunner({ target, repository, accountExists: false, calls }),
      stdio: "ignore",
    });

    assert.deepEqual(prompts.map(({ hidden }) => hidden), [false, true, true]);
    const provisioningCalls = calls.filter(({ args }) => args.includes("provision-local-account"));
    assert.equal(provisioningCalls.length, 2);
    assert.deepEqual(JSON.parse(provisioningCalls[0].options.input), { action: "status" });
    assert.deepEqual(JSON.parse(provisioningCalls[1].options.input), {
      action: "create",
      username,
      password,
    });
    for (const call of calls) {
      assert.doesNotMatch(JSON.stringify(call.args), new RegExp(`${username}|${password}`));
      assert.doesNotMatch(JSON.stringify(call.options.env || {}), new RegExp(`${username}|${password}`));
    }
  } finally {
    await rm(workspace, { recursive: true, force: true });
  }
});

test("non-interactive first-account setup fails with an actionable terminal instruction", async () => {
  const scratchBase = process.env.JCODE_SCRATCH_DIR || os.tmpdir();
  const workspace = await mkdtemp(path.join(scratchBase, "xultron-cli-noninteractive-"));
  const target = path.join(workspace, "app");
  const repository = "https://github.com/trackview1827-ctrl/Xultron.git";
  const calls = [];

  try {
    await createCliCheckout(target);
    await assert.rejects(
      runCli([], {
        env: { XULTRON_HOME: target, XULTRON_REPOSITORY: repository },
        io: bufferedIo().io,
        interactive: false,
        processRunner: cliProcessRunner({ target, repository, accountExists: false, calls }),
        stdio: "ignore",
      }),
      /etkileşimli bir terminal gerekli.*doğrudan bir terminalde çalıştırın/,
    );
    assert.equal(calls.some(({ command, args }) => command.endsWith("/python") && args[0] === "run.py"), false);
  } finally {
    await rm(workspace, { recursive: true, force: true });
  }
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
