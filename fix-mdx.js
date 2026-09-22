const fs = require('fs');
const path = require('path');

const dirs = ['./docs', './blog', './ead-docs', './lab-docs', './pjts-docs', './utfpr'];

const fixMdxComments = (dir) => {
    if (!fs.existsSync(dir)) return;

    const files = fs.readdirSync(dir);

    files.forEach((file) => {
        const filePath = path.join(dir, file);
        const stat = fs.statSync(filePath);

        if (stat.isDirectory()) {
            fixMdxComments(filePath); // Recursive search
        } else if (filePath.endsWith('.md') || filePath.endsWith('.mdx')) {
            let content = fs.readFileSync(filePath, 'utf8');

            // Regex to find and replace with {/* comment */}
            // It handles multi-line comments as well
            const newContent = content.replace(/<!--([\s\S]*?)-->/g, '{/*$1*/}');

            if (content !== newContent) {
                fs.writeFileSync(filePath, newContent, 'utf8');
                console.log(`✅ Fixed: ${filePath}`);
            }
        }
    });
};

console.log('🚀 Starting MDX comment fix...');
dirs.forEach(fixMdxComments);
console.log('✨ Done!');
