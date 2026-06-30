const fs = require("fs");
const path = require("path");
const { chromium } = require("playwright");

async function main() {
  const edgePath = "C:\\Program Files (x86)\\Microsoft\\Edge\\Application\\msedge.exe";
  const browser = await chromium.launch({
    headless: true,
    executablePath: fs.existsSync(edgePath) ? edgePath : undefined,
  });
  const page = await browser.newPage({
    viewport: { width: 1600, height: 900 },
    deviceScaleFactor: 1,
  });
  await page.goto("http://127.0.0.1:8000/local-agent", {
    waitUntil: "networkidle",
  });
  await page.screenshot({
    path: path.join(__dirname, "08_本地智能体运行中心.png"),
    fullPage: false,
  });
  await browser.close();
}

main().catch((error) => {
  console.error(error);
  process.exitCode = 1;
});
