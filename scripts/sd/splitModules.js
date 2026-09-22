const fs = require("fs");
const path = require("path");
const prettier = require("prettier");

// =============================
// CONFIG
// =============================
const INPUT = "circuits-compiled.js";
const MODULES_DIR = "modules";
const SVG_DIR = "svgs";
const HTML_DIR = "html";

fs.mkdirSync(MODULES_DIR, { recursive: true });
fs.mkdirSync(SVG_DIR, { recursive: true });
fs.mkdirSync(HTML_DIR, { recursive: true });

// =============================
// EXTRACT MODULES
// =============================
function extractModules(jsText) {
    const modules = [];

    const regex = /(\d+)\s*\(\w+\)\s*{([\s\S]*?)}\s*,/g;
    let match;

    while ((match = regex.exec(jsText)) !== null) {
        modules.push({
            id: match[1],
            code: match[2],
        });
    }

    return modules;
}

// =============================
// GENERIC STRING EXPORT EXTRACTOR
// =============================
function extractExportString(code) {
    const regex = /e\.exports\s*=\s*(['"`])([\s\S]*?)\1/;
    const match = code.match(regex);
    if (!match) return null;

    let content = match[2];

    // Unescape
    content = content
        .replace(/\\n/g, "\n")
        .replace(/\\"/g, '"')
        .replace(/\\'/g, "'");

    return content.trim();
}

// =============================
// DETECT TYPE
// =============================
function detectType(content) {
    if (!content) return null;

    if (content.startsWith("<svg")) return "svg";

    if (
        content.startsWith("<div") ||
        content.startsWith("<span") ||
        content.startsWith("<html") ||
        content.startsWith("<!DOCTYPE")
    ) {
        return "html";
    }

    return null;
}

// =============================
// MAIN
// =============================
async function run() {
    const jsText = fs.readFileSync(INPUT, "utf8");
    const modules = extractModules(jsText);

    console.log(`📦 Found ${modules.length} modules`);

    let svgCount = 0;
    let htmlCount = 0;

    for (const m of modules) {
        const content = extractExportString(m.code);
        const type = detectType(content);

        if (type === "svg") {
            fs.writeFileSync(path.join(SVG_DIR, `${m.id}.svg`), content);
            svgCount++;
            continue;
        }

        if (type === "html") {
            fs.writeFileSync(path.join(HTML_DIR, `${m.id}.html`), content);
            htmlCount++;
            continue;
        }

        // fallback → JS module
        try {
            const formatted = await prettier.format(m.code, {
                parser: "babel",
            });

            fs.writeFileSync(
                path.join(MODULES_DIR, `${m.id}.js`),
                formatted
            );

        } catch {
            fs.writeFileSync(
                path.join(MODULES_DIR, `${m.id}.js`),
                m.code
            );
        }
    }

    console.log(`🖼️ SVG files: ${svgCount}`);
    console.log(`📄 HTML files: ${htmlCount}`);
    console.log("✅ Done");
}

run();
