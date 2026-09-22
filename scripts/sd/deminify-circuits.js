// scripts/deminify.js
const fs = require("fs");
const prettier = require("prettier");
const path = require("path");

const ROOT = path.resolve(__dirname, "..");
const DEFAULT_OUTPUT_DIR = path.join(ROOT, "src", "data");

const input = "circuits-compiled.js";
const output = path.join(DEFAULT_OUTPUT_DIR, "circuits-pretty.js");

async function run() {
    const code = fs.readFileSync(input, "utf8");

    const formatted = await prettier.format(code, {
        parser: "babel",
        printWidth: 100,
        tabWidth: 2,
        semi: true,
        singleQuote: false,
    });

    fs.writeFileSync(output, formatted);
    console.log("✅ Pretty file generated:", output);
}

run();