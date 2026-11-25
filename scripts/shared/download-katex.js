const fs = require("fs");
const path = require("path");
const https = require("https");

const LATEST_VERSION = "latest"; // You can specify a version like '0.16.8' if you want a specific one
const BASE_URL = `https://cdn.jsdelivr.net/npm/katex@${LATEST_VERSION}/dist/`;
const TARGET_DIR = path.join(__dirname, "..", "static", "katex");
const FONTS_DIR = path.join(TARGET_DIR, "fonts");

// Helper to fetch data as a string
const fetchText = (url) => {
  return new Promise((resolve, reject) => {
    https
      .get(url, (res) => {
        let data = "";
        res.on("data", (chunk) => (data += chunk));
        res.on("end", () => resolve(data));
      })
      .on("error", reject);
  });
};

// Helper to download binary files
const downloadFile = (url, dest) => {
  return new Promise((resolve, reject) => {
    const file = fs.createWriteStream(dest);
    https
      .get(url, (res) => {
        if (res.statusCode !== 200) return reject(`Status: ${res.statusCode}`);
        res.pipe(file);
        file.on("finish", () => {
          file.close();
          resolve();
        });
      })
      .on("error", (err) => {
        if (fs.existsSync(dest)) fs.unlinkSync(dest);
        reject(err);
      });
  });
};

async function main() {
  try {
    console.log(`🔍 Fetching KaTeX ${LATEST_VERSION} manifest...`);

    if (!fs.existsSync(FONTS_DIR)) fs.mkdirSync(FONTS_DIR, { recursive: true });

    // 1. Download and save the CSS
    const cssUrl = `${BASE_URL}katex.min.css`;
    const cssContent = await fetchText(cssUrl);
    fs.writeFileSync(path.join(TARGET_DIR, "katex.min.css"), cssContent);
    console.log("✅ katex.min.css saved.");

    // 2. Parse CSS for font filenames
    // This regex looks for fonts/filename.woff2 (or .woff, .ttf)
    const fontRegex = /fonts\/([\w-]+\.(woff2|woff|ttf))/g;
    const matches = [...cssContent.matchAll(fontRegex)];
    const uniqueFonts = [...new Set(matches.map((m) => m[1]))];

    console.log(
      `found ${uniqueFonts.length} unique fonts. Starting download...`,
    );

    // 3. Download each font
    const downloads = uniqueFonts.map(async (fontName) => {
      try {
        await downloadFile(
          `${BASE_URL}fonts/${fontName}`,
          path.join(FONTS_DIR, fontName),
        );
        console.log(`  ✅ ${fontName}`);
      } catch (err) {
        console.error(`  ❌ Failed: ${fontName} (${err})`);
      }
    });

    await Promise.all(downloads);
    console.log("\n✨ All assets synchronized successfully.");
  } catch (error) {
    console.error("🚀 Fatal Error:", error);
    process.exit(1);
  }
}

main();
