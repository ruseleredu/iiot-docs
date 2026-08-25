const fs = require('fs');
const path = require('path');
const AdmZip = require('adm-zip');

const REPO_OWNER = 'thelastoutpostworkshop';
const REPO_NAME = 'ESPConnect';
const ASSET_NAME = 'dist.zip';
const TARGET_DIR = path.join(__dirname, '..', 'static', 'espconnect');

async function downloadAndExtract() {
    try {
        console.log(`[1/4] Querying latest release from ${REPO_OWNER}/${REPO_NAME}...`);

        const headers = {
            'User-Agent': 'Node.js-Release-Downloader',
            'Accept': 'application/vnd.github.v3+json',
        };

        if (process.env.GITHUB_TOKEN) {
            headers['Authorization'] = `token ${process.env.GITHUB_TOKEN}`;
        }

        const releaseResponse = await fetch(
            `https://api.github.com/repos/${REPO_OWNER}/${REPO_NAME}/releases/latest`,
            { headers }
        );

        if (!releaseResponse.ok) {
            throw new Error(`Failed to fetch release info: ${releaseResponse.statusText}`);
        }

        const releaseData = await releaseResponse.json();
        const asset = releaseData.assets.find(a => a.name === ASSET_NAME);

        if (!asset) {
            throw new Error(`Asset "${ASSET_NAME}" not found in release ${releaseData.tag_name}`);
        }

        console.log(`[2/4] Downloading ${ASSET_NAME} from release ${releaseData.tag_name}...`);

        const downloadResponse = await fetch(asset.browser_download_url, {
            headers: { 'User-Agent': 'Node.js-Release-Downloader' },
            redirect: 'follow',
        });

        if (!downloadResponse.ok) {
            throw new Error(`Failed to download asset: ${downloadResponse.statusText}`);
        }

        const arrayBuffer = await downloadResponse.arrayBuffer();
        const zipBuffer = Buffer.from(arrayBuffer);

        console.log(`[3/4] Preparing target directory: ${TARGET_DIR}`);
        if (!fs.existsSync(TARGET_DIR)) {
            fs.mkdirSync(TARGET_DIR, { recursive: true });
        }

        console.log(`[4/4] Extracting contents directly into static/espconnect/...`);
        const zip = new AdmZip(zipBuffer);
        const zipEntries = zip.getEntries();

        zipEntries.forEach((entry) => {
            // Strip leading 'dist/' or 'dist\' folder name from zip entry path
            const relativePath = entry.entryName.replace(/^dist[/\\]/, '');

            if (!relativePath) return; // Skip the base 'dist/' root entry itself

            const targetPath = path.join(TARGET_DIR, relativePath);

            if (entry.isDirectory) {
                fs.mkdirSync(targetPath, { recursive: true });
            } else {
                // Ensure parent folder exists before writing file
                fs.mkdirSync(path.dirname(targetPath), { recursive: true });
                fs.writeFileSync(targetPath, entry.getData());
            }
        });

        console.log('✅ Extraction complete! Files placed flat in static/espconnect/.');
    } catch (error) {
        console.error('❌ Error during asset download/extraction:', error.message);
        process.exit(1);
    }
}

downloadAndExtract();
