import { constants as fsConstants } from "node:fs";
import { access, mkdir, readdir, stat } from "node:fs/promises";
import { homedir } from "node:os";
import path from "node:path";
import { spawn } from "node:child_process";

export const PACKAGE_VERSION = "1.0.0";
export const DEFAULT_REPOSITORY = "https://github.com/trackview1827-ctrl/Xultron.git";
export const DEFAULT_BRANCH = "main";

const HELP = `Xultron CLI ${PACKAGE_VERSION}

Kullanım:
  xultron install [--dir <klasör>]   Xultron'u klonlar ve bağımlılıkları kurar
  xultron update  [--dir <klasör>]   Temiz kurulumu main dalına günceller
  xultron start   [--dir <klasör>]   Tek-origin üretim önizlemesini başlatır
  xultron dev     [--dir <klasör>]   API ve Vite geliştirme sunucularını başlatır
  xultron doctor                       Git, Node.js, npm ve Python'u kontrol eder
  xultron help                         Bu yardımı gösterir

Varsayılan kurulum klasörü:
  ~/.xultron/app

GitHub üzerinden çalıştırma:
  npx --yes github:trackview1827-ctrl/Xultron install
  npx --yes github:trackview1827-ctrl/Xultron start
`;

function parseVersion(value) {
  const match = String(value).match(/(\d+)(?:\.(\d+))?(?:\.(\d+))?/);
  if (!match) return null;
  return [Number(match[1]), Number(match[2] || 0), Number(match[3] || 0)];
}

function versionAtLeast(actual, required) {
  for (let index = 0; index < required.length; index += 1) {
    if (actual[index] > required[index]) return true;
    if (actual[index] < required[index]) return false;
  }
  return true;
}

function defaultIo() {
  return {
    stdout: (message) => process.stdout.write(`${message}\n`),
    stderr: (message) => process.stderr.write(`${message}\n`),
  };
}

export function parseArgs(argv) {
  const args = [...argv];
  let command = "help";
  let commandAssigned = false;
  let directory;
  let skipBootstrap = false;

  while (args.length) {
    const token = args.shift();
    if (token === "--help" || token === "-h") {
      command = "help";
      commandAssigned = true;
    } else if (token === "--version" || token === "-v") {
      command = "version";
      commandAssigned = true;
    } else if (token === "--dir" || token === "-d") {
      directory = args.shift();
      if (!directory) throw new Error(`${token} bir klasör değeri gerektirir.`);
    } else if (token === "--skip-bootstrap") {
      skipBootstrap = true;
    } else if (token.startsWith("-")) {
      throw new Error(`Bilinmeyen seçenek: ${token}`);
    } else if (!commandAssigned) {
      command = token;
      commandAssigned = true;
    } else if (!directory) {
      directory = token;
    } else {
      throw new Error(`Beklenmeyen argüman: ${token}`);
    }
  }

  return { command, directory, skipBootstrap };
}

export function resolveInstallDir(directory, env = process.env, home = homedir()) {
  const configured = directory || env.XULTRON_HOME || path.join(home, ".xultron", "app");
  return path.resolve(configured.replace(/^~(?=$|[\\/])/, home));
}

export function repositoriesEqual(left, right) {
  const normalize = (value) => {
    const raw = String(value).trim().replace(/\\/g, "/").replace(/\/$/, "");
    const ssh = raw.match(/^git@github\.com:(.+)$/i);
    if (ssh) return `github:${ssh[1].replace(/\.git$/i, "").toLowerCase()}`;
    const https = raw.match(/^https?:\/\/github\.com\/(.+)$/i);
    if (https) return `github:${https[1].replace(/\.git$/i, "").toLowerCase()}`;
    if (raw.startsWith("file://")) return path.resolve(new URL(raw).pathname).replace(/\.git$/i, "");
    return path.resolve(raw).replace(/\.git$/i, "");
  };
  return normalize(left) === normalize(right);
}

function runProcess(command, args, options = {}) {
  const { cwd, env = process.env, stdio = "inherit", capture = false } = options;
  return new Promise((resolve, reject) => {
    const child = spawn(command, args, {
      cwd,
      env,
      stdio: capture ? ["ignore", "pipe", "pipe"] : stdio,
    });
    let stdout = "";
    let stderr = "";
    if (capture) {
      child.stdout.setEncoding("utf8");
      child.stderr.setEncoding("utf8");
      child.stdout.on("data", (chunk) => { stdout += chunk; });
      child.stderr.on("data", (chunk) => { stderr += chunk; });
    }
    child.on("error", (error) => {
      if (error.code === "ENOENT") reject(new Error(`${command} bulunamadı.`));
      else reject(error);
    });
    child.on("close", (code, signal) => {
      if (code === 0) {
        resolve({ stdout: stdout.trim(), stderr: stderr.trim() });
        return;
      }
      const detail = capture && stderr.trim() ? `: ${stderr.trim()}` : "";
      reject(new Error(`${command} ${args.join(" ")} başarısız oldu (${signal || code})${detail}`));
    });
  });
}

async function pathExists(target) {
  try {
    await access(target, fsConstants.F_OK);
    return true;
  } catch {
    return false;
  }
}

async function isEmptyDirectory(target) {
  try {
    return (await readdir(target)).length === 0;
  } catch {
    return false;
  }
}

async function assertXultronCheckout(target, repository) {
  const gitDir = path.join(target, ".git");
  if (!(await pathExists(gitDir))) {
    throw new Error(`${target} geçerli bir Xultron Git kurulumu değil.`);
  }
  const { stdout: origin } = await runProcess("git", ["remote", "get-url", "origin"], {
    cwd: target,
    capture: true,
  });
  if (!repositoriesEqual(origin, repository)) {
    throw new Error(`${target} farklı bir Git deposuna bağlı: ${origin}`);
  }
}

async function toolVersion(command, args, minimum, label) {
  try {
    const { stdout, stderr } = await runProcess(command, args, { capture: true });
    const output = stdout || stderr;
    const parsed = parseVersion(output);
    if (!parsed || !versionAtLeast(parsed, minimum)) {
      return { ok: false, label, output: output || "sürüm okunamadı", minimum: minimum.join(".") };
    }
    return { ok: true, label, output };
  } catch (error) {
    return { ok: false, label, output: error.message, minimum: minimum.join(".") };
  }
}

export async function doctor(options = {}) {
  const io = options.io || defaultIo();
  const checks = await Promise.all([
    toolVersion("git", ["--version"], [2, 20, 0], "Git"),
    toolVersion("node", ["--version"], [20, 0, 0], "Node.js"),
    toolVersion("npm", ["--version"], [9, 0, 0], "npm"),
    toolVersion("python", ["--version"], [3, 11, 0], "Python"),
  ]);
  for (const check of checks) {
    io.stdout(`${check.ok ? "✓" : "✗"} ${check.label}: ${check.output}`);
  }
  const failures = checks.filter((check) => !check.ok);
  if (failures.length) {
    throw new Error(`Eksik veya eski araçlar var: ${failures.map((item) => `${item.label} >= ${item.minimum}`).join(", ")}`);
  }
  return checks;
}

async function bootstrap(target, options) {
  if (options.skipBootstrap || options.env.XULTRON_SKIP_BOOTSTRAP === "1") {
    options.io.stdout("Bootstrap atlandı. Bu seçenek yalnızca test ve ileri düzey kullanım içindir.");
    return;
  }
  await runProcess("bash", [path.join(target, "scripts", "bootstrap.sh")], {
    cwd: target,
    env: options.env,
    stdio: options.stdio,
  });
}

export async function install(options) {
  const { target, repository, io } = options;
  await doctor({ io });
  const exists = await pathExists(target);
  if (!exists) {
    await mkdir(path.dirname(target), { recursive: true });
    io.stdout(`Xultron klonlanıyor: ${target}`);
    await runProcess("git", ["clone", "--depth", "1", "--branch", DEFAULT_BRANCH, repository, target], {
      env: options.env,
      stdio: options.stdio,
    });
  } else if (await isEmptyDirectory(target)) {
    io.stdout(`Xultron boş klasöre klonlanıyor: ${target}`);
    await runProcess("git", ["clone", "--depth", "1", "--branch", DEFAULT_BRANCH, repository, target], {
      env: options.env,
      stdio: options.stdio,
    });
  } else {
    await assertXultronCheckout(target, repository);
    io.stdout(`Mevcut Xultron kurulumu kullanılacak: ${target}`);
  }
  await assertXultronCheckout(target, repository);
  await bootstrap(target, options);
  io.stdout("Xultron hazır.");
  io.stdout(`Başlat: xultron start --dir ${JSON.stringify(target)}`);
}

export async function update(options) {
  const { target, repository, io } = options;
  await doctor({ io });
  await assertXultronCheckout(target, repository);
  const { stdout: currentBranch } = await runProcess("git", ["branch", "--show-current"], {
    cwd: target,
    capture: true,
  });
  if (currentBranch !== DEFAULT_BRANCH) {
    throw new Error(`Güncelleme durduruldu: etkin dal ${currentBranch || "detached HEAD"}, beklenen dal ${DEFAULT_BRANCH}.`);
  }
  const { stdout: statusOutput } = await runProcess("git", ["status", "--porcelain"], {
    cwd: target,
    capture: true,
  });
  if (statusOutput) {
    throw new Error("Güncelleme durduruldu: kurulumda commit edilmemiş yerel değişiklikler var.");
  }
  io.stdout("GitHub main dalı alınıyor...");
  await runProcess("git", ["fetch", "origin", DEFAULT_BRANCH], {
    cwd: target,
    env: options.env,
    stdio: options.stdio,
  });
  await runProcess("git", ["merge", "--ff-only", `origin/${DEFAULT_BRANCH}`], {
    cwd: target,
    env: options.env,
    stdio: options.stdio,
  });
  await bootstrap(target, options);
  io.stdout("Xultron güncellendi.");
}

async function ensureRunnable(target) {
  const expected = [
    path.join(target, "scripts", "bootstrap.sh"),
    path.join(target, "backend", "run.py"),
    path.join(target, "frontend", "package.json"),
  ];
  for (const item of expected) {
    if (!(await pathExists(item))) throw new Error(`Eksik Xultron dosyası: ${item}`);
  }
  const info = await stat(path.join(target, "backend", ".venv", "bin", "python")).catch(() => null);
  if (!info?.isFile()) throw new Error("Backend bağımlılıkları eksik. Önce `xultron install` çalıştır.");
  if (!(await pathExists(path.join(target, "frontend", "node_modules")))) {
    throw new Error("Frontend bağımlılıkları eksik. Önce `xultron install` çalıştır.");
  }
}

export async function start(options) {
  const { target, io } = options;
  await ensureRunnable(target);
  io.stdout("Xultron üretim arayüzü hazırlanıyor...");
  await runProcess("npm", ["--prefix", path.join(target, "frontend"), "run", "build"], {
    cwd: target,
    env: options.env,
    stdio: options.stdio,
  });
  if (options.env.XULTRON_LOCAL_STT_AUTOSTART === "1") {
    io.stdout("Yerel whisper.cpp STT hazırlanıyor...");
    await runProcess("bash", [path.join(target, "scripts", "local-voice.sh"), "start"], {
      cwd: target,
      env: options.env,
      stdio: options.stdio,
    });
  }
  await runProcess(path.join(target, "backend", ".venv", "bin", "flask"), ["--app", "run.py", "db", "upgrade"], {
    cwd: path.join(target, "backend"),
    env: options.env,
    stdio: options.stdio,
  });
  io.stdout(`Xultron başlatılıyor: http://127.0.0.1:${options.env.PORT || "5000"}`);
  await runProcess(path.join(target, "backend", ".venv", "bin", "python"), ["run.py"], {
    cwd: path.join(target, "backend"),
    env: options.env,
    stdio: options.stdio,
  });
}

export async function dev(options) {
  const { target, io } = options;
  await ensureRunnable(target);
  io.stdout("Xultron geliştirme sunucuları başlatılıyor...");
  await runProcess("bash", [path.join(target, "scripts", "dev.sh")], {
    cwd: target,
    env: options.env,
    stdio: options.stdio,
  });
}

export async function runCli(argv, context = {}) {
  const parsed = parseArgs(argv);
  const io = context.io || defaultIo();
  const env = context.env || process.env;
  const target = resolveInstallDir(parsed.directory, env, context.home || homedir());
  const repository = env.XULTRON_REPOSITORY || DEFAULT_REPOSITORY;
  const options = {
    ...parsed,
    target,
    repository,
    io,
    env,
    stdio: context.stdio || "inherit",
  };

  if (parsed.command === "help") {
    io.stdout(HELP.trimEnd());
    return;
  }
  if (parsed.command === "version") {
    io.stdout(PACKAGE_VERSION);
    return;
  }
  if (parsed.command === "doctor") return doctor(options);
  if (parsed.command === "install" || parsed.command === "setup") return install(options);
  if (parsed.command === "update") return update(options);
  if (parsed.command === "start" || parsed.command === "serve") return start(options);
  if (parsed.command === "dev") return dev(options);
  throw new Error(`Bilinmeyen komut: ${parsed.command}\n\n${HELP}`);
}
