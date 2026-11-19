// Resolve native CLI for Git-installed OpenCode plugins; bundled release remains unchanged.
import { access } from 'node:fs/promises';
import { spawn } from 'node:child_process';
import { join } from 'node:path';
import { homedir, platform, arch } from 'node:os';

const VERSION = 'v0.5.6';
let pending;
async function exists(path) { try { await access(path); return true; } catch { return false; } }

function runtimeCache() {
  const parent = process.env.TOKENSAVER_DOCS_RUNTIME_HOME ||
    (platform() === 'win32'
      ? join(process.env.LOCALAPPDATA || join(homedir(), 'AppData', 'Local'), 'tokensaver-docs', 'marketplace-runtime')
      : join(homedir(), 'Library', 'Application Support', 'tokensaver-docs', 'marketplace-runtime'));
  const machine = platform() === 'win32' ? 'win32-x64' : 'darwin-' + (arch() === 'arm64' ? 'arm64' : 'x64');
  return join(parent, VERSION, machine, 'bin', platform() === 'win32' ? 'tokensaver-docs.exe' : 'tokensaver-docs');
}

function bootstrap(pluginRoot) {
  return new Promise((resolve, reject) => {
    if (!['darwin', 'win32'].includes(platform()) || !['arm64', 'x64'].includes(arch())) {
      reject(new Error('No native TokenSaver Docs marketplace release for this OS/CPU'));
      return;
    }
    const isWindows = platform() === 'win32';
    const script = join(pluginRoot, 'scripts', isWindows ? 'run.ps1' : 'run.sh');
    const command = isWindows ? 'powershell.exe' : '/bin/sh';
    const args = isWindows ? ['-NoProfile', '-File', script, '--help'] : [script, '--help'];
    const child = spawn(command, args, { shell: false, windowsHide: true, stdio: ['ignore', 'pipe', 'pipe'] });
    let stderr = '';
    child.stderr.on('data', chunk => { stderr += chunk.toString().slice(0, 1000); });
    child.on('error', reject);
    child.on('close', code => code === 0 ? resolve() : reject(new Error('TokenSaver Docs runtime download failed (' + code + '): ' + stderr.slice(-1500))));
  });
}

// Resolve an already installed runtime without any network access.
// OpenCode V2 calls this during plugin setup so that loading plugins never
// starts a large download or blocks activation.
export async function findTokenSaverExecutable(pluginRoot) {
  const bundled = join(pluginRoot, 'bin', platform() === 'win32' ? 'tokensaver-docs.exe' : 'tokensaver-docs');
  if (await exists(bundled)) return bundled;
  const cached = runtimeCache();
  return (await exists(cached)) ? cached : null;
}

// First-use CLI operations can bootstrap the native runtime on demand.
export async function ensureTokenSaverExecutable(pluginRoot) {
  const installed = await findTokenSaverExecutable(pluginRoot);
  if (installed) return installed;
  const cached = runtimeCache();
  if (!pending) pending = bootstrap(pluginRoot).catch(err => { pending = null; throw err; });
  await pending;
  if (!(await exists(cached))) throw new Error('Native runtime not found after bootstrap');
  return cached;
}
