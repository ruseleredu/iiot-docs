// download-circuits.js
const https = require("https");
const fs = require("fs");
const path = require("path");

const url = "https://editor.tinkercad.com/assets_cc_a20t0v/js/circuits-compiled.js";
const outputPath = path.join(__dirname, "circuits-compiled.js");

const file = fs.createWriteStream(outputPath);

https.get(url, (response) => {
    if (response.statusCode !== 200) {
        console.error(`❌ Failed: ${response.statusCode}`);
        return;
    }

    const total = parseInt(response.headers["content-length"] || "0", 10);
    let downloaded = 0;

    response.on("data", (chunk) => {
        downloaded += chunk.length;
        if (total) {
            process.stdout.write(
                `\r⬇️  Downloading... ${((downloaded / total) * 100).toFixed(2)}%`
            );
        }
    });

    response.pipe(file);

    file.on("finish", () => {
        file.close();
        console.log("\n✅ Download complete:", outputPath);
    });

}).on("error", (err) => {
    fs.unlink(outputPath, () => { });
    console.error("❌ Error:", err.message);
});
