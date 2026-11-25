import fs from "node:fs";
import path from "node:path";

const GITHUB_EMOJI_API = "https://api.github.com/emojis";
const OUTPUT_FILE = path.join(
  process.cwd(),
  "docs/tutorial-basics",
  "github-emojis.mdx",
);

async function run() {
  try {
    console.log("📡 Fetching emoji icons...");
    const response = await fetch(GITHUB_EMOJI_API);
    if (!response.ok) throw new Error(`HTTP error! status: ${response.status}`);

    const emojis = await response.json();
    const names = Object.keys(emojis).sort();

    const header = [
      "---",
      "title: GitHub Emoji Reference",
      "sidebar_label: 🎭 GitHub Emoji List",
      "---",
      "",
      "import EmojiTable from '@site/src/components/shared/EmojiTable.tsx';",
      "",
      "# 🎭 GitHub Emoji Reference",
      "",
      ":::info",
      "Click any shortcode or icon to copy it to your clipboard!",
      ":::",
      "",
      "<EmojiTable>",
      "",
      "| Icon | Shortcode |",
      "| :---: | :--- |",
    ].join("\n");

    const rows = names
      .map((name) => `| :${name}: | \`:${name}:\` |`)
      .join("\n");

    fs.writeFileSync(OUTPUT_FILE, header + "\n" + rows + "\n\n</EmojiTable>");

    console.log(`✅ Success! Created ${names.length} emojis in ${OUTPUT_FILE}`);
  } catch (err) {
    console.error("❌ Failed:", err.message);
  }
}

run();
