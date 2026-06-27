import { spawn, spawnSync } from "node:child_process";
import { existsSync } from "node:fs";
import { join } from "node:path";
import process from "node:process";

const port = process.env.LOCAL_API_PORT || "8765";
const venvPython = join(process.cwd(), ".venv", "bin", "python");
const hasUv = spawnSync("uv", ["--version"], { stdio: "ignore" }).status === 0;
const pythonCommand = existsSync(venvPython) ? venvPython : hasUv ? "uv" : "python3";
const pythonArgs = existsSync(venvPython)
  ? ["scripts/local_api.py", port]
  : hasUv
    ? ["run", "--with-requirements", "requirements.txt", "python", "scripts/local_api.py", port]
    : ["scripts/local_api.py", port];

const children = [];

function start(name, command, args, env = {}) {
  const child = spawn(command, args, {
    cwd: process.cwd(),
    env: { ...process.env, UV_CACHE_DIR: "/tmp/portfoliocheck-uv-cache", ...env },
    stdio: "inherit"
  });

  child.on("exit", (code, signal) => {
    if (signal) {
      return;
    }
    console.error(`[${name}] exited with code ${code}`);
    shutdown(code ?? 1);
  });

  children.push(child);
  return child;
}

function shutdown(code = 0) {
  for (const child of children) {
    if (!child.killed) {
      child.kill("SIGTERM");
    }
  }
  process.exit(code);
}

process.on("SIGINT", () => shutdown(0));
process.on("SIGTERM", () => shutdown(0));

start("local-api", pythonCommand, pythonArgs);
start("next", "npx", ["next", "dev", "-H", "127.0.0.1"], { LOCAL_API_PORT: port });
