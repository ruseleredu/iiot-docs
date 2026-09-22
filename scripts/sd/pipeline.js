// pipeline.js
const fs = require("fs");
const path = require("path");
const https = require("https");

// =============================
// CONFIG
// =============================
const URL = "https://editor.tinkercad.com/assets_cc_a20t0v/js/circuits-compiled.js";

const ROOT = __dirname;
const JS_FILE = path.join(ROOT, "circuits-compiled.js");
const JSON_FILE = path.join(ROOT, "components.json");
const DOCS_DIR = path.join(ROOT, "docs/components");

// =============================
// STEP 1 — DOWNLOAD
// =============================
function downloadFile(url, output) {
    return new Promise((resolve, reject) => {
        const file = fs.createWriteStream(output);

        https.get(url, (res) => {
            if (res.statusCode !== 200) {
                reject(new Error(`HTTP ${res.statusCode}`));
                return;
            }

            res.pipe(file);

            file.on("finish", () => {
                file.close(resolve);
            });

        }).on("error", (err) => {
            fs.unlink(output, () => { });
            reject(err);
        });
    });
}

// =============================
// STEP 2 — EXTRACT (ROBUST)
// =============================
function extractComponents(jsText) {
    const components = [];
    const seenIds = new Set();

    const keyword = "e.exports";
    let i = 0;

    while ((i = jsText.indexOf(keyword, i)) !== -1) {
        const start = jsText.indexOf("{", i);
        if (start === -1) break;

        let braceCount = 0;
        let end = start;

        for (; end < jsText.length; end++) {
            const char = jsText[end];

            if (char === "{") braceCount++;
            else if (char === "}") braceCount--;

            if (braceCount === 0) {
                end++;
                break;
            }
        }

        const objStr = jsText.slice(start, end);

        try {
            const obj = eval("(" + objStr + ")");

            if (
                obj &&
                typeof obj === "object" &&
                obj.name &&
                obj.id &&
                !seenIds.has(obj.id)
            ) {
                seenIds.add(obj.id);
                components.push(obj);
            }

        } catch {
            // ignore invalid blocks
        }

        i = end;
    }

    return components;
}

// =============================
// STEP 3 — HELPERS
// =============================
function slugify(name) {
    return name
        .toLowerCase()
        .replace(/[^\w\s-]/g, "")
        .replace(/\s+/g, "-");
}

function extractLinks(detailRefs = {}) {
    return Object.values(detailRefs)
        .filter(r => r && r.type === "link" && r.url)
        .map(r => r.url);
}

function extractImages(detailRefs = {}) {
    return Object.values(detailRefs)
        .filter(r => r && r.type === "image" && r.url)
        .flatMap(r => Array.isArray(r.url) ? r.url : [r.url]);
}

// =============================
// STEP 4 — MDX GENERATION
// =============================
function generateMDX(components) {
    fs.mkdirSync(DOCS_DIR, { recursive: true });

    components.forEach(c => {
        const slug = slugify(c.name);

        const links = extractLinks(c.detailRefs);
        const images = extractImages(c.detailRefs);

        const mdx = `---
id: ${slug}
title: ${c.name}
sidebar_label: ${c.name}
---

# ${c.name}

${c.description || ""}

## 🧾 Info

- **ID:** ${c.id}
- **Tags:** ${(c.tags || []).join(", ")}
- **Footprint:** ${c.footprint?.name || "N/A"}

## 🖼️ Preview

<img src="${c.thumbUrl}" alt="${c.name}" width="200"/>

## 📚 Resources

${links.length ? links.map(l => `- ${l}`).join("\n") : "No links available."}

## 🧪 Media

${images.length ? images.map(img => `<img src="/img/components/${img}" width="300" />`).join("\n") : "No media available."}

---
`;

        fs.writeFileSync(path.join(DOCS_DIR, `${slug}.mdx`), mdx);
    });
}

// =============================
// STEP 5 — INDEX
// =============================
function generateIndex(components) {
    const content = `# Tinkercad Components

Total components: ${components.length}

Browse components using the sidebar.
`;

    fs.mkdirSync(path.join(ROOT, "docs"), { recursive: true });
    fs.writeFileSync(path.join(ROOT, "docs/index.md"), content);
}

// =============================
// RUN PIPELINE
// =============================
(async () => {
    try {
        console.log("⬇️ Downloading JS...");
        await downloadFile(URL, JS_FILE);

        console.log("📦 Extracting components...");
        const jsText = fs.readFileSync(JS_FILE, "utf8");
        const components = extractComponents(jsText);

        console.log(`✅ Found ${components.length} components`);

        fs.writeFileSync(JSON_FILE, JSON.stringify(components, null, 2));

        console.log("📝 Generating MDX docs...");
        generateMDX(components);

        console.log("📚 Creating index...");
        generateIndex(components);

        console.log("🎉 DONE! Docs ready.");

    } catch (err) {
        console.error("❌ Pipeline failed:", err.message);
    }
})();
