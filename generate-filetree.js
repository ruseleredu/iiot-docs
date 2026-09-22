const fs = require('fs');
const path = require('path');

/**
 * Pastas e arquivos que devem ser ignorados durante a leitura
 */
const IGNORED_NAMES = new Set([
    'node_modules',
    '.git',
    '.ds_store',
    'dist',
    'build',
    '.docusaurus',
    '.pio',
]);

/**
 * Função recursiva para varrer o diretório
 */
function walkDir(dirPath, relativePath = '') {
    const items = fs.readdirSync(dirPath, { withFileTypes: true });
    let results = [];

    // Ordena mantendo pastas primeiro, depois arquivos
    items.sort((a, b) => {
        if (a.isDirectory() && !b.isDirectory()) return -1;
        if (!a.isDirectory() && b.isDirectory()) return 1;
        return a.name.localeCompare(b.name);
    });

    for (const item of items) {
        if (IGNORED_NAMES.has(item.name.toLowerCase())) continue;

        const itemRelativePath = relativePath ? `${relativePath}/${item.name}` : item.name;
        const fullPath = path.join(dirPath, item.name);

        if (item.isDirectory()) {
            const subItems = fs.readdirSync(fullPath);
            // Filtra itens ignorados da subpasta
            const validSubItems = subItems.filter(name => !IGNORED_NAMES.has(name.toLowerCase()));

            if (validSubItems.length === 0) {
                // Se a pasta for vazia, adiciona barra ao final
                results.push(`${itemRelativePath}/`);
            } else {
                // Varre a subpasta recursivamente
                results = results.concat(walkDir(fullPath, itemRelativePath));
            }
        } else {
            results.push(itemRelativePath);
        }
    }

    return results;
}

function generateSnippet(targetPath) {
    const absolutePath = path.resolve(targetPath);

    if (!fs.existsSync(absolutePath)) {
        console.error(`❌ Erro: O diretório "${targetPath}" não foi encontrado.`);
        process.exit(1);
    }

    const rootName = path.basename(absolutePath);
    const filesList = walkDir(absolutePath);

    const formattedFiles = filesList
        .map((file) => `    "${file}",`)
        .join('\n');

    const snippet = `<FileTree
  root="${rootName}"
  files={[
${formattedFiles}
  ]}
/>`;

    console.log('\n✅ Snippet gerado com sucesso!\n');
    console.log('--------------------------------------------------');
    console.log(snippet);
    console.log('--------------------------------------------------\n');
    console.log('💡 Dica: Adicione c, r, u ou d após as aspas nos arquivos que possuem ações.');
    console.log('   Exemplo: "wokwi.toml u" ou "src/main.cpp r"\n');
}

// Obtém o caminho passado pela linha de comando
const targetDir = process.argv[2] || '.';
generateSnippet(targetDir);
