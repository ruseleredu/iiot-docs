// Lista quais componentes de src/components são usados no site Docusaurus.
//
// Uso (na raiz do site, onde está o docusaurus.config.ts):
//   node scripts/componentes-usados.mjs            -> resumo
//   node scripts/componentes-usados.mjs --detalhe  -> mostra também as páginas de cada componente
//   node scripts/componentes-usados.mjs LabIotAluno -> só as páginas que usam esse componente

import fs from "node:fs";
import path from "node:path";

const RAIZ = process.cwd();

// pastas de conteúdo (as mesmas do docusaurus.config.ts: docs, blog e os plugin-content-docs)
const CONTEUDO = ["docs", "blog", "labs", "quiz", "projects", "tpls", "infra-docs", "src/pages"];
// infra-docs tem exclude: ['**/docker/**']
const IGNORAR = [/[\\/]node_modules[\\/]/, /^infra-docs[\\/](.*[\\/])?docker[\\/]/];

const COMPONENTES = "src/components";
const MDX_COMPONENTS = ["src/theme/MDXComponents.tsx", "src/theme/MDXComponents.js", "src/theme/MDXComponents.ts"];

const args = process.argv.slice(2);
const detalhe = args.includes("--detalhe");
const filtro = args.find((a) => !a.startsWith("--"));

const rel = (f) => path.relative(RAIZ, f).split(path.sep).join("/");

function listar(dir, exts) {
    const abs = path.join(RAIZ, dir);
    if (!fs.existsSync(abs)) return [];
    const out = [];
    for (const e of fs.readdirSync(abs, { withFileTypes: true, recursive: true })) {
        if (!e.isFile()) continue;
        const f = path.join(e.parentPath ?? e.path, e.name);
        const r = rel(f);
        if (IGNORAR.some((re) => re.test(r))) continue;
        if (exts.includes(path.extname(e.name))) out.push(f);
    }
    return out;
}

// tira blocos de código (``` e ~~~) e código inline, para não contar exemplos de JSX dentro de código
function semCodigo(txt) {
    return txt
        .replace(/^(\s*)(```+|~~~+)[\s\S]*?^\1\2\s*$/gm, "")
        .replace(/`[^`\n]*`/g, "");
}

/* 1. componentes definidos em src/components ------------------------- */
const comps = new Map(); // nome -> { arquivo, paginas: Set, codigo: Set }
// componentes ficam em .tsx/.jsx/.js (o .ts é constants, tipos...); nome com minúscula (não COURSE, GROUPS)
for (const f of listar(COMPONENTES, [".tsx", ".jsx", ".js"])) {
    const txt = fs.readFileSync(f, "utf8");
    const nomes = new Set();
    for (const m of txt.matchAll(/export\s+default\s+(?:function\s+)?([A-Z]\w*)/g)) nomes.add(m[1]);
    for (const m of txt.matchAll(/export\s+(?:function|const|class)\s+([A-Z]\w*)/g)) nomes.add(m[1]);
    for (const n of nomes) {
        if (!/[a-z]/.test(n)) continue;
        if (!comps.has(n)) comps.set(n, { arquivo: rel(f), paginas: new Set(), codigo: new Set() });
    }
}

/* 2. registrados globalmente em MDXComponents ------------------------ */
const globais = new Set();
const mdxFile = MDX_COMPONENTS.map((f) => path.join(RAIZ, f)).find((f) => fs.existsSync(f));
if (mdxFile) {
    const txt = fs.readFileSync(mdxFile, "utf8");
    const corpo = txt.slice(txt.indexOf("export default"));
    for (const m of corpo.matchAll(/^\s*([A-Z]\w*)\s*(?::[^,\n]+)?,?\s*$/gm)) globais.add(m[1]);
}

/* 3. uso nas páginas (.md/.mdx) --------------------------------------- */
const semDefinicao = new Map(); // tag -> Set(arquivos)
const paginas = CONTEUDO.flatMap((d) => listar(d, [".md", ".mdx"]));
for (const f of paginas) {
    const txt = semCodigo(fs.readFileSync(f, "utf8"));
    const importados = new Set();
    for (const m of txt.matchAll(/^import\s+([\s\S]+?)\s+from\s+['"][^'"]+['"]/gm)) {
        for (const n of m[1].matchAll(/[A-Z]\w*/g)) importados.add(n[0]);
    }
    for (const m of txt.matchAll(/<([A-Z][A-Za-z0-9]*)(?=[\s/>])/g)) {
        const tag = m[1];
        if (comps.has(tag)) comps.get(tag).paginas.add(rel(f));
        if (!globais.has(tag) && !importados.has(tag)) {
            if (!semDefinicao.has(tag)) semDefinicao.set(tag, new Set());
            semDefinicao.get(tag).add(rel(f));
        }
    }
}

/* 4. uso por código (src/pages, src/theme, outros componentes) -------- */
const codigo = ["src"].flatMap((d) => listar(d, [".tsx", ".ts", ".jsx", ".js"]));
for (const f of codigo) {
    if (mdxFile && path.resolve(f) === path.resolve(mdxFile)) continue; // o registro global não conta como uso
    const txt = fs.readFileSync(f, "utf8");
    for (const m of txt.matchAll(/^import\s+([\s\S]+?)\s+from\s+['"]([^'"]+)['"]/gm)) {
        for (const n of m[1].matchAll(/[A-Z]\w*/g)) {
            const c = comps.get(n[0]);
            if (c && c.arquivo !== rel(f)) c.codigo.add(rel(f));
        }
    }
}

/* 5. relatório -------------------------------------------------------- */
const ordem = [...comps.entries()].sort((a, b) => b[1].paginas.size - a[1].paginas.size || a[0].localeCompare(b[0]));

if (filtro) {
    const c = comps.get(filtro);
    if (!c) {
        console.log(`${filtro}: não encontrado em ${COMPONENTES}`);
        process.exit(1);
    }
    console.log(`${filtro} (${c.arquivo})${globais.has(filtro) ? " [global]" : ""}`);
    [...c.paginas].sort().forEach((p) => console.log(`  página: ${p}`));
    [...c.codigo].sort().forEach((p) => console.log(`  código: ${p}`));
    if (!c.paginas.size && !c.codigo.size) console.log("  sem uso");
    process.exit(0);
}

console.log(`Páginas lidas: ${paginas.length}   Componentes em ${COMPONENTES}: ${comps.size}   Globais: ${globais.size}\n`);

console.log("USADOS NAS PÁGINAS (nº de páginas)");
for (const [n, c] of ordem.filter(([, c]) => c.paginas.size)) {
    console.log(`  ${String(c.paginas.size).padStart(3)}  ${n}${globais.has(n) ? "  [global]" : ""}   ${c.arquivo}`);
    if (detalhe) [...c.paginas].sort().forEach((p) => console.log(`         - ${p}`));
}

console.log("\nUSADOS SÓ POR CÓDIGO (outros componentes, src/pages, src/theme)");
for (const [n, c] of ordem.filter(([, c]) => !c.paginas.size && c.codigo.size)) {
    console.log(`       ${n}   <- ${[...c.codigo].join(", ")}`);
}

console.log("\nSEM USO (candidatos a remover)");
for (const [n, c] of ordem.filter(([, c]) => !c.paginas.size && !c.codigo.size)) {
    console.log(`       ${n}${globais.has(n) ? "  [global, mas nenhuma página usa]" : ""}   ${c.arquivo}`);
}

const globaisSemComp = [...globais].filter((g) => !comps.has(g));
if (globaisSemComp.length) {
    console.log(`\nGLOBAIS QUE NÃO VÊM DE ${COMPONENTES} (tema do Docusaurus): ${globaisSemComp.join(", ")}`);
}

if (semDefinicao.size) {
    console.log("\nTAGS SEM IMPORT NEM REGISTRO GLOBAL (a página pode quebrar: verifique)");
    for (const [t, fs_] of [...semDefinicao].sort()) {
        console.log(`       <${t}>   ${[...fs_].slice(0, 3).join(", ")}${fs_.size > 3 ? ` (+${fs_.size - 3})` : ""}`);
    }
}
