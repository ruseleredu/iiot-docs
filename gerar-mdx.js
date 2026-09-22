#!/usr/bin/env node
// @ts-check
"use strict";

/**
 * gerar-mdx.js
 * ============
 * Le o consolidado `disciplinas.json` (produzido por scripts/gerar-json.js) e
 * gera uma pagina .mdx por disciplina. Cada pagina apenas seleciona a
 * disciplina pelo slug e delega a renderizacao ao componente React
 * <TabelaPlanejamento>, mantendo o JSON como unica fonte de verdade.
 *
 * Tambem gera um indice `index.mdx` listando todas as disciplinas.
 *
 * Uso:
 *   node scripts/gerar-mdx.js
 *   node scripts/gerar-mdx.js --data ./src/data/disciplinas.json --out ./docs/planejamento
 *
 * Nao requer dependencias externas.
 */

const fs = require("fs");
const path = require("path");

function parseArgs(argv) {
  const args = {
    data: "./src/data/disciplinas.json",
    out: "./docs/planejamento",
  };
  for (let i = 0; i < argv.length; i++) {
    const a = argv[i];
    if (a === "--data") args.data = argv[++i];
    else if (a === "--out") args.out = argv[++i];
    else if (a === "-h" || a === "--help") args.help = true;
  }
  return args;
}

function ajuda() {
  console.log(`
Uso: node scripts/gerar-mdx.js [opcoes]

  --data <arquivo>  Caminho do disciplinas.json (padrao: ./src/data/disciplinas.json)
  --out <dir>       Diretorio de saida das paginas .mdx (padrao: ./docs/planejamento)
  -h, --help        Mostra esta ajuda
`);
}

/** Escapa aspas para uso seguro dentro do YAML do frontmatter. */
function yaml(str) {
  return `"${String(str || "").replace(/"/g, '\\"')}"`;
}

function paginaDisciplina(d, indice) {
  return `---
title: ${yaml(d.disciplina)}
sidebar_label: ${yaml(d.codigo)}
sidebar_position: ${indice + 2}
slug: /planejamento/${d.slug}
---

import disciplinas from '@site/src/data/disciplinas.json';
import TabelaPlanejamento from '@site/src/components/TabelaPlanejamento';

export const disciplina = disciplinas.disciplinas.find(
  (item) => item.slug === ${yaml(d.slug)}
);

# ${d.disciplina}

<TabelaPlanejamento disciplina={disciplina} />
`;
}

function paginaIndice(disciplinas) {
  const itens = disciplinas
    .map(
      (d) =>
        `- [${d.disciplina} (${d.codigo})](/planejamento/${d.slug}) — ` +
        `${d.sincronas.length} síncronas, ${d.assincronas.length} assíncronas, ` +
        `${d.procedimentos.length} procedimentos`
    )
    .join("\n");

  return `---
title: Planejamento de Aula
sidebar_label: Visão geral
sidebar_position: 1
slug: /planejamento
---

# Planejamento de Aula

Páginas geradas automaticamente a partir dos dados extraídos dos planejamentos.

${itens}
`;
}

function main() {
  const args = parseArgs(process.argv.slice(2));
  if (args.help) return ajuda();

  const dataPath = path.resolve(args.data);
  const outDir = path.resolve(args.out);

  if (!fs.existsSync(dataPath)) {
    console.error(`Arquivo nao encontrado: ${dataPath}`);
    console.error("Rode antes: node scripts/gerar-json.js");
    process.exit(1);
  }

  const consolidado = JSON.parse(fs.readFileSync(dataPath, "utf-8"));
  const disciplinas = consolidado.disciplinas || [];
  fs.mkdirSync(outDir, { recursive: true });

  fs.writeFileSync(
    path.join(outDir, "index.mdx"),
    paginaIndice(disciplinas),
    "utf-8"
  );

  disciplinas.forEach((d, i) => {
    fs.writeFileSync(
      path.join(outDir, `${d.slug}.mdx`),
      paginaDisciplina(d, i),
      "utf-8"
    );
  });

  console.log("==================== RESUMO ====================");
  console.log(`Paginas geradas em: ${outDir}`);
  console.log(`  - index.mdx (indice)`);
  for (const d of disciplinas) console.log(`  - ${d.slug}.mdx`);
  console.log(`\nTotal: ${disciplinas.length} disciplina(s) + 1 indice`);
}

main();
