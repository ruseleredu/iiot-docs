// scripts/splitModules.js
const fs = require("fs");
const path = require("path");
const prettier = require("prettier");

const input = "circuits-compiled.js";
const OUT_DIR = "modules";

fs.mkdirSync(OUT_DIR, { recursive: true });

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

async function run() {
    const jsText = fs.readFileSync(input, "utf8");
    const modules = extractModules(jsText);

    console.log(`📦 Found ${modules.length} modules`);

    for (const m of modules) {
        try {
            const formatted = await prettier.format(m.code, {
                parser: "babel",
            });

            const filePath = path.join(OUT_DIR, `${m.id}.js`);
            fs.writeFileSync(filePath, formatted);

        } catch {
            // fallback if formatting fails
            fs.writeFileSync(
                path.join(OUT_DIR, `${m.id}.js`),
                m.code
            );
        }
    }

    console.log("✅ Modules split into /modules folder");
}

run();
