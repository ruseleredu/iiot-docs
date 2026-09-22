const fs = require("fs");
const path = require("path");

// 1. Identify the project root (one level up from this script)
const projectRoot = path.resolve(__dirname, "..");

// 2. Define target directories relative to the project root
// Directories to scan (Docusaurus defaults)
// const dirs = ['./docs', './blog', './labs', './quiz', './projects', './tpls'];
const targetDirs = [
  path.join(projectRoot, "docs"),
  path.join(projectRoot, "blog"),
  path.join(projectRoot, "utfpr"),
];

const renameFiles = (dir) => {
  if (!fs.existsSync(dir)) {
    console.log(
      `\x1b[33mℹ Directory not found (skipping):\x1b[0m ${path.relative(projectRoot, dir)}`,
    );
    return;
  }

  const files = fs.readdirSync(dir);

  files.forEach((file) => {
    const oldPath = path.join(dir, file);
    const stat = fs.statSync(oldPath);

    if (stat.isDirectory()) {
      renameFiles(oldPath); // Recursive
    } else if (path.extname(file) === ".md") {
      const newPath = oldPath.replace(/\.md$/, ".mdx");

      if (!fs.existsSync(newPath)) {
        fs.renameSync(oldPath, newPath);
        // Log relative path for cleaner output
        console.log(
          `✅ Renamed: ${path.relative(projectRoot, oldPath)} -> ${path.basename(newPath)}`,
        );
      } else {
        console.warn(
          `⚠️ Collision: ${path.basename(newPath)} already exists. Skipped ${file}`,
        );
      }
    }
  });
};

console.log(`🚀 Starting rename in: ${projectRoot}`);
targetDirs.forEach(renameFiles);
console.log("✨ Done!");
