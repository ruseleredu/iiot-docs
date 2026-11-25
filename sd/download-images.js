#!/usr/bin/env node

const fs = require("fs");
const path = require("path");
const crypto = require("crypto");
const axios = require("axios");
const fg = require("fast-glob");

const ROOT = process.cwd();
const STATIC_DIR = path.join(ROOT, "static", "img", "imported");

fs.mkdirSync(STATIC_DIR, { recursive: true });

const targetDir = process.argv[2];

if (!targetDir) {
    console.log("Usage:");
    console.log("  node scripts/download-images.js <folder>");
    console.log("");
    console.log("Example:");
    console.log("  node scripts/download-images.js docs/tutorials");
    process.exit(1);
}

const absoluteTarget = path.resolve(ROOT, targetDir);

if (!fs.existsSync(absoluteTarget)) {
    console.error(`Folder not found: ${absoluteTarget}`);
    process.exit(1);
}

const IMG_REGEX = /<img\b([^>]*?)src=['"]([^'"]+)['"]([^>]*)>/gi;

function getExtension(url, contentType) {

    try {
        const pathname = new URL(url).pathname;
        const ext = path.extname(pathname);

        if (ext)
            return ext.toLowerCase();
    } catch { }

    if (contentType) {

        if (contentType.includes("png")) return ".png";
        if (contentType.includes("jpeg")) return ".jpg";
        if (contentType.includes("jpg")) return ".jpg";
        if (contentType.includes("gif")) return ".gif";
        if (contentType.includes("svg")) return ".svg";
        if (contentType.includes("webp")) return ".webp";
        if (contentType.includes("bmp")) return ".bmp";
    }

    return ".bin";
}

async function download(url) {

    const hash = crypto
        .createHash("sha1")
        .update(url)
        .digest("hex");

    try {

        const response = await axios.get(url, {
            responseType: "arraybuffer",
            timeout: 30000,
            headers: {
                "User-Agent": "Mozilla/5.0"
            }
        });

        const ext = getExtension(url, response.headers["content-type"]);

        const filename = hash + ext;

        const outfile = path.join(STATIC_DIR, filename);

        if (!fs.existsSync(outfile)) {
            fs.writeFileSync(outfile, response.data);
            console.log(`      saved ${filename}`);
        } else {
            console.log(`      exists ${filename}`);
        }

        return `/img/imported/${filename}`;

    } catch (err) {

        console.log(`      FAILED (${err.message})`);

        return null;
    }
}
async function processFile(file) {

    let text = fs.readFileSync(file, "utf8");

    const matches = [...text.matchAll(IMG_REGEX)];

    if (!matches.length)
        return;

    console.log(`\n${file}`);

    let modified = false;

    for (const match of matches) {

        const fullTag = match[0];
        const url = match[2];

        if (!/^https?:\/\//i.test(url))
            continue;

        // Extract alt text
        const altMatch = fullTag.match(/alt=['"]([^'"]*)['"]/i);
        const alt = altMatch ? altMatch[1] : "";

        console.log(`  ↓ ${url}`);

        const localPath = await download(url);

        if (!localPath)
            continue;

        // Replace the entire <img ...> tag
        const markdownImage = `![${alt}](${localPath})`;

        text = text.replace(fullTag, markdownImage);

        modified = true;
    }

    if (modified) {
        fs.writeFileSync(file, text);
        console.log("  updated");
    }
}

async function main() {

    console.log(`Scanning ${absoluteTarget}`);
    console.log("");

    const files = await fg("**/*.mdx", {
        cwd: absoluteTarget,
        absolute: true
    });

    console.log(`Found ${files.length} MDX files`);

    for (const file of files) {
        await processFile(file);
    }

    console.log("");
    console.log("Done.");
}

main().catch(console.error);
