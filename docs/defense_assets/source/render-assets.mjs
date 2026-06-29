import fs from "node:fs/promises";
import path from "node:path";
import os from "node:os";
import { execFile } from "node:child_process";
import { promisify } from "node:util";
import { fileURLToPath, pathToFileURL } from "node:url";

const sourceDir = path.dirname(fileURLToPath(import.meta.url));
const outputDir = path.resolve(sourceDir, "..");
const htmlPath = path.join(sourceDir, "xueban-task-assets.html");
const names = [
  "01_本轮任务成果总览.png",
  "02_三学段模式切换架构.png",
  "03_专注提醒MCP闭环.png",
  "04_软硬件技术路线.png",
  "05_知识库与智能体配置.png",
  "06_工程成果数据看板.png",
  "07_完成度与下一阶段路线.png",
  "08_答辩数据表.png",
];

await fs.mkdir(outputDir, { recursive: true });
const browserCandidates = [
  process.env.CHROME_PATH,
  "C:\\Program Files (x86)\\Microsoft\\Edge\\Application\\msedge.exe",
  "C:\\Program Files\\Microsoft\\Edge\\Application\\msedge.exe",
  "C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe",
].filter(Boolean);
let browserPath;
for (const candidate of browserCandidates) {
  try {
    await fs.access(candidate);
    browserPath = candidate;
    break;
  } catch {
    // Try the next installed Chromium browser.
  }
}
if (!browserPath) throw new Error("No Chromium browser was found. Set CHROME_PATH.");

const run = promisify(execFile);
const profileDir = await fs.mkdtemp(path.join(os.tmpdir(), "xueban-defense-"));
for (let index = 0; index < names.length; index += 1) {
  const outputPath = path.join(outputDir, names[index]);
  const url = `${pathToFileURL(htmlPath).href}?slide=${index + 1}`;
  await run(browserPath, [
    "--headless=new",
    "--disable-gpu",
    "--hide-scrollbars",
    "--force-device-scale-factor=1",
    "--window-size=1920,1080",
    `--user-data-dir=${profileDir}`,
    `--screenshot=${outputPath}`,
    url,
  ], { windowsHide: true, timeout: 30000 });
}
await fs.rm(profileDir, { recursive: true, force: true });
console.log(`Rendered ${names.length} defense assets to ${outputDir}`);
