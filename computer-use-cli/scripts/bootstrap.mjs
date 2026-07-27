import fs from "node:fs/promises";
import os from "node:os";
import path from "node:path";
import { pathToFileURL } from "node:url";

const WRAPPER = path.join("scripts", "computer-use-client.mjs");
const PLUGIN_RELATIVE = path.join(
  "plugins",
  "cache",
  "openai-bundled",
  "computer-use",
);

async function isFile(file) {
  try {
    return (await fs.stat(file)).isFile();
  } catch {
    return false;
  }
}

function versionParts(name) {
  return name.split(/[^0-9]+/).filter(Boolean).map(Number);
}

function compareVersionsDescending(a, b) {
  const aa = versionParts(a.version);
  const bb = versionParts(b.version);
  const length = Math.max(aa.length, bb.length);
  for (let index = 0; index < length; index += 1) {
    const difference = (bb[index] ?? 0) - (aa[index] ?? 0);
    if (difference !== 0) return difference;
  }
  return b.mtimeMs - a.mtimeMs;
}

function candidateCodexHomes(env) {
  const homes = [];
  if (env.CODEX_HOME) homes.push(path.resolve(env.CODEX_HOME));
  homes.push(path.join(os.homedir(), ".codex"));
  return [...new Set(homes)];
}

export async function findComputerUsePlugin({ env = process.env } = {}) {
  const explicitRoot = env.CODEX_COMPUTER_USE_PLUGIN_ROOT;
  if (explicitRoot) {
    const root = path.resolve(explicitRoot);
    if (!(await isFile(path.join(root, WRAPPER)))) {
      throw new Error(
        `CODEX_COMPUTER_USE_PLUGIN_ROOT does not contain ${WRAPPER}: ${root}`,
      );
    }
    return root;
  }

  const candidates = [];
  const searched = [];
  for (const codexHome of candidateCodexHomes(env)) {
    const versionsRoot = path.join(codexHome, PLUGIN_RELATIVE);
    searched.push(versionsRoot);
    let entries;
    try {
      entries = await fs.readdir(versionsRoot, { withFileTypes: true });
    } catch {
      continue;
    }

    for (const entry of entries) {
      if (!entry.isDirectory() && !entry.isSymbolicLink()) continue;
      const root = path.join(versionsRoot, entry.name);
      if (!(await isFile(path.join(root, WRAPPER)))) continue;
      const stat = await fs.stat(root);
      candidates.push({ root, version: entry.name, mtimeMs: stat.mtimeMs });
    }
  }

  candidates.sort(compareVersionsDescending);
  if (candidates.length === 0) {
    throw new Error(
      [
        "Could not find the Computer Use plugin installed by Codex App.",
        `Searched: ${searched.join(", ")}`,
        "Install or update Codex App, or set CODEX_COMPUTER_USE_PLUGIN_ROOT to the plugin version directory.",
      ].join(" "),
    );
  }
  return candidates[0].root;
}

export async function setupPortableComputerUse({ globals = globalThis, env = process.env } = {}) {
  if (globalThis.sky) {
    Reflect.set(globals, "sky", globalThis.sky);
    return globalThis.sky;
  }

  const pluginRoot = await findComputerUsePlugin({ env });
  const wrapper = path.join(pluginRoot, WRAPPER);
  const module = await import(pathToFileURL(wrapper).href);
  if (typeof module.setupComputerUseRuntime !== "function") {
    throw new Error(`Installed plugin has no setupComputerUseRuntime export: ${wrapper}`);
  }
  return module.setupComputerUseRuntime({ globals });
}

async function check() {
  const pluginRoot = await findComputerUsePlugin();
  const nativeClient = path.join(
    pluginRoot,
    "Codex Computer Use.app",
    "Contents",
    "SharedSupport",
    "SkyComputerUseClient.app",
    "Contents",
    "MacOS",
    "SkyComputerUseClient",
  );
  const result = {
    ok: true,
    pluginRoot,
    wrapper: path.join(pluginRoot, WRAPPER),
    nativeClient,
    nativeClientPresent: await isFile(nativeClient),
    nodeReplEnvironmentPresent: Boolean(globalThis.nodeRepl?.env),
    note: "The nodeRepl environment is normally present only inside Codex node_repl.",
  };
  process.stdout.write(`${JSON.stringify(result, null, 2)}\n`);
}

if (process.argv[1] && import.meta.url === pathToFileURL(path.resolve(process.argv[1])).href) {
  if (process.argv.includes("--check")) {
    check().catch((error) => {
      process.stderr.write(`${error.stack ?? error}\n`);
      process.exitCode = 1;
    });
  } else {
    process.stderr.write("Usage: node bootstrap.mjs --check\n");
    process.exitCode = 2;
  }
}
