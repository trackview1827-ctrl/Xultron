import { constants as fsConstants, readFileSync } from "node:fs";
import { access, chmod, mkdir, readdir, stat } from "node:fs/promises";
import { homedir } from "node:os";
import path from "node:path";
import { spawn } from "node:child_process";
import readline from "node:readline";

export const PACKAGE_VERSION = JSON.parse(
  readFileSync(new URL("../package.json", import.meta.url), "utf8"),
).version;
export const DEFAULT_REPOSITORY = "https://github.com/trackview1827-ctrl/Xultron.git";
export const DEFAULT_BRANCH = "main";

const HELP = `Xultron CLI ${PACKAGE_VERSION}

Kullanım:
  xultron                             İlk kurulumu tamamlar, hesabı hazırlar ve Xultron'u başlatır
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

function defaultPrompt({ message, hidden = false }) {
  if (!process.stdin.isTTY || !process.stdout.isTTY) {
    throw new Error(
      "İlk hesabı oluşturmak için etkileşimli bir terminal gerekli. "
      + "Düzeltme: `xultron` komutunu doğrudan bir terminalde çalıştırın.",
    );
  }

  return new Promise((resolve) => {
    const terminal = readline.createInterface({
      input: process.stdin,
      output: process.stdout,
      terminal: true,
    });

    if (hidden) {
      const write = terminal._writeToOutput.bind(terminal);
      let muted = false;
      terminal._writeToOutput = (value) => {
        if (!muted) write(value);
      };
      terminal.question(message, (answer) => {
        process.stdout.write("\n");
        terminal.close();
        resolve(answer);
      });
      muted = true;
      return;
    }

    terminal.question(message, (answer) => {
      terminal.close();
      resolve(answer);
    });
  });
}

export function parseArgs(argv) {
  const args = [...argv];
  let command = "launch";
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
  const {
    cwd,
    env = process.env,
    stdio = "inherit",
    capture = false,
    input,
  } = options;
  return new Promise((resolve, reject) => {
    const pipeStdin = input !== undefined;
    const child = spawn(command, args, {
      cwd,
      env,
      stdio: capture || pipeStdin
        ? [pipeStdin ? "pipe" : "ignore", capture ? "pipe" : "inherit", capture ? "pipe" : "inherit"]
        : stdio,
    });
    let stdout = "";
    let stderr = "";
    if (capture) {
      child.stdout.setEncoding("utf8");
      child.stderr.setEncoding("utf8");
      child.stdout.on("data", (chunk) => { stdout += chunk; });
      child.stderr.on("data", (chunk) => { stderr += chunk; });
    }
    if (pipeStdin) child.stdin.end(input);
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

async function secureXultronParent(target) {
  const parent = path.dirname(path.resolve(target));
  if (path.basename(parent) !== ".xultron") return;
  await mkdir(parent, { recursive: true, mode: 0o700 });
  await chmod(parent, 0o700);
}

async function assertXultronCheckout(target, repository, processRunner = runProcess) {
  const gitDir = path.join(target, ".git");
  if (!(await pathExists(gitDir))) {
    throw new Error(`${target} geçerli bir Xultron Git kurulumu değil.`);
  }
  const { stdout: origin } = await processRunner("git", ["remote", "get-url", "origin"], {
    cwd: target,
    capture: true,
  });
  if (!repositoriesEqual(origin, repository)) {
    throw new Error(`${target} farklı bir Git deposuna bağlı: ${origin}`);
  }
}

async function toolVersion(command, args, minimum, label, processRunner) {
  try {
    const { stdout, stderr } = await processRunner(command, args, { capture: true });
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

async function firstAvailableToolVersion(commands, args, minimum, label, processRunner) {
  const failures = [];
  for (const command of commands) {
    const check = await toolVersion(command, args, minimum, label, processRunner);
    if (check.ok) return check;
    failures.push(`${command}: ${check.output}`);
  }
  return {
    ok: false,
    label,
    output: failures.join("; "),
    minimum: minimum.join("."),
  };
}

export async function doctor(options = {}) {
  const io = options.io || defaultIo();
  const processRunner = options.processRunner || runProcess;
  const checks = await Promise.all([
    toolVersion("git", ["--version"], [2, 20, 0], "Git", processRunner),
    toolVersion("node", ["--version"], [20, 0, 0], "Node.js", processRunner),
    toolVersion("npm", ["--version"], [9, 0, 0], "npm", processRunner),
    firstAvailableToolVersion(["python", "python3"], ["--version"], [3, 11, 0], "Python", processRunner),
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
  await options.processRunner("bash", [path.join(target, "scripts", "bootstrap.sh")], {
    cwd: target,
    env: options.env,
    stdio: options.stdio,
  });
}

export async function install(options) {
  const { target, repository, io } = options;
  await doctor({ io, processRunner: options.processRunner });
  await secureXultronParent(target);
  const exists = await pathExists(target);
  if (!exists) {
    await mkdir(path.dirname(target), { recursive: true });
    io.stdout(`Xultron klonlanıyor: ${target}`);
    await options.processRunner("git", ["clone", "--depth", "1", "--branch", DEFAULT_BRANCH, repository, target], {
      env: options.env,
      stdio: options.stdio,
    });
  } else if (await isEmptyDirectory(target)) {
    io.stdout(`Xultron boş klasöre klonlanıyor: ${target}`);
    await options.processRunner("git", ["clone", "--depth", "1", "--branch", DEFAULT_BRANCH, repository, target], {
      env: options.env,
      stdio: options.stdio,
    });
  } else {
    await assertXultronCheckout(target, repository, options.processRunner);
    io.stdout(`Mevcut Xultron kurulumu kullanılacak: ${target}`);
  }
  await assertXultronCheckout(target, repository, options.processRunner);
  await bootstrap(target, options);
  io.stdout("Xultron hazır.");
  io.stdout(`Başlat: xultron start --dir ${JSON.stringify(target)}`);
}

export async function update(options) {
  const { target, repository, io } = options;
  await doctor({ io, processRunner: options.processRunner });
  await assertXultronCheckout(target, repository, options.processRunner);
  const { stdout: currentBranch } = await options.processRunner("git", ["branch", "--show-current"], {
    cwd: target,
    capture: true,
  });
  if (currentBranch !== DEFAULT_BRANCH) {
    throw new Error(`Güncelleme durduruldu: etkin dal ${currentBranch || "detached HEAD"}, beklenen dal ${DEFAULT_BRANCH}.`);
  }
  const { stdout: statusOutput } = await options.processRunner("git", ["status", "--porcelain"], {
    cwd: target,
    capture: true,
  });
  if (statusOutput) {
    throw new Error("Güncelleme durduruldu: kurulumda commit edilmemiş yerel değişiklikler var.");
  }
  io.stdout("GitHub main dalı alınıyor...");
  await options.processRunner("git", ["fetch", "origin", DEFAULT_BRANCH], {
    cwd: target,
    env: options.env,
    stdio: options.stdio,
  });
  await options.processRunner("git", ["merge", "--ff-only", `origin/${DEFAULT_BRANCH}`], {
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
  await options.processRunner("npm", ["--prefix", path.join(target, "frontend"), "run", "build"], {
    cwd: target,
    env: options.env,
    stdio: options.stdio,
  });
  if (options.env.XULTRON_LOCAL_STT_AUTOSTART === "1") {
    io.stdout("Yerel whisper.cpp STT hazırlanıyor...");
    await options.processRunner("bash", [path.join(target, "scripts", "local-voice.sh"), "start"], {
      cwd: target,
      env: options.env,
      stdio: options.stdio,
    });
  }
  await options.processRunner(path.join(target, "backend", ".venv", "bin", "flask"), ["--app", "run.py", "db", "upgrade"], {
    cwd: path.join(target, "backend"),
    env: options.env,
    stdio: options.stdio,
  });
  io.stdout(`Xultron başlatılıyor: http://127.0.0.1:${options.env.PORT || "5000"}`);
  await options.processRunner(path.join(target, "backend", ".venv", "bin", "python"), ["run.py"], {
    cwd: path.join(target, "backend"),
    env: options.env,
    stdio: options.stdio,
  });
}

export async function dev(options) {
  const { target, io } = options;
  await ensureRunnable(target);
  io.stdout("Xultron geliştirme sunucuları başlatılıyor...");
  await options.processRunner("bash", [path.join(target, "scripts", "dev.sh")], {
    cwd: target,
    env: options.env,
    stdio: options.stdio,
  });
}

function parseProvisionResponse(stdout) {
  try {
    return JSON.parse(stdout);
  } catch {
    throw new Error(
      "Yerel hesap durumu okunamadı. "
      + "Düzeltme: `xultron update` çalıştırıp yeniden deneyin.",
    );
  }
}

async function provisioningRequest(options, payload) {
  const backend = path.join(options.target, "backend");
  const flask = path.join(backend, ".venv", "bin", "flask");
  const result = await options.processRunner(
    flask,
    ["--app", "run.py", "provision-local-account"],
    {
      cwd: backend,
      env: options.env,
      capture: true,
      input: `${JSON.stringify(payload)}\n`,
    },
  );
  return parseProvisionResponse(result.stdout);
}

async function collectCredentials(options) {
  if (!options.interactive) {
    throw new Error(
      "İlk hesabı oluşturmak için etkileşimli bir terminal gerekli. "
      + "Düzeltme: `xultron` komutunu doğrudan bir terminalde çalıştırın.",
    );
  }

  const username = String(await options.prompt({
    message: "Kullanıcı adı: ",
    hidden: false,
  })).trim();
  if (!username) throw new Error("Kullanıcı adı boş olamaz. Xultron'u yeniden çalıştırıp bir kullanıcı adı girin.");

  const password = String(await options.prompt({
    message: "Parola: ",
    hidden: true,
  }));
  if (!password) throw new Error("Parola boş olamaz. Xultron'u yeniden çalıştırıp bir parola girin.");

  const confirmation = String(await options.prompt({
    message: "Parola tekrar: ",
    hidden: true,
  }));
  if (password !== confirmation) {
    throw new Error("Parolalar eşleşmedi. Xultron'u yeniden çalıştırıp aynı parolayı iki kez girin.");
  }
  return { username, password };
}

export async function launch(options) {
  const exists = await pathExists(options.target);
  if (!exists || await isEmptyDirectory(options.target)) {
    await install(options);
  } else {
    await assertXultronCheckout(options.target, options.repository, options.processRunner);
    await ensureRunnable(options.target);
    options.io.stdout(`Mevcut Xultron kurulumu kullanılacak: ${options.target}`);
  }

  const status = await provisioningRequest(options, { action: "status" });
  if (typeof status.accountExists !== "boolean") {
    throw new Error(
      "Yerel hesap durumu geçersiz. Düzeltme: `xultron update` çalıştırıp yeniden deneyin.",
    );
  }
  if (!status.accountExists) {
    const credentials = await collectCredentials(options);
    await provisioningRequest(options, { action: "create", ...credentials });
    options.io.stdout(`Yerel hesap hazır: ${credentials.username}`);
  }

  return start(options);
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
    processRunner: context.processRunner || runProcess,
    prompt: context.prompt || defaultPrompt,
    interactive: context.interactive ?? Boolean(process.stdin.isTTY && process.stdout.isTTY),
  };

  if (parsed.command === "help") {
    io.stdout(HELP.trimEnd());
    return;
  }
  if (parsed.command === "version") {
    io.stdout(PACKAGE_VERSION);
    return;
  }
  if (parsed.command === "launch") return launch(options);
  if (parsed.command === "doctor") return doctor(options);
  if (parsed.command === "install" || parsed.command === "setup") return install(options);
  if (parsed.command === "update") return update(options);
  if (parsed.command === "start" || parsed.command === "serve") return start(options);
  if (parsed.command === "dev") return dev(options);
  throw new Error(`Bilinmeyen komut: ${parsed.command}\n\n${HELP}`);
}
