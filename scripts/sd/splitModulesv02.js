const fs = require("fs");
const path = require("path");
const prettier = require("prettier");

// =============================
// CONFIG
// =============================
const INPUT = "circuits-compiled.js";
const MODULES_DIR = "modules";
const SVG_DIR = "svgs";

fs.mkdirSync(MODULES_DIR, { recursive: true });
fs.mkdirSync(SVG_DIR, { recursive: true });

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
// DETECT SVG EXPORT
// =============================
function extractSVG(code) {
    // Matches: e.exports = '<svg ... </svg>';
    const svgRegex = /e\.exports\s*=\s*(['"`])(<svg[\s\S]*?<\/svg>)\1/;

    const match = code.match(svgRegex);
    if (!match) return null;

    let svg = match[2];

    // Unescape common escaped chars
    svg = svg
        .replace(/\\n/g, "")
        .replace(/\\"/g, '"')
        .replace(/\\'/g, "'");

    return svg;
}

// =============================
// MAIN
// =============================
async function run() {
    const jsText = fs.readFileSync(INPUT, "utf8");
    const modules = extractModules(jsText);

    console.log(`📦 Found ${modules.length} modules`);

    let svgCount = 0;

    for (const m of modules) {
        const svg = extractSVG(m.code);

        if (svg) {
            const filePath = path.join(SVG_DIR, `${m.id}.svg`);
            fs.writeFileSync(filePath, svg);
            svgCount++;
            continue;
        }

        // Otherwise: normal JS module
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

    console.log(`✅ Saved ${svgCount} SVG files`);
    console.log("✅ Modules split complete");
}

run();