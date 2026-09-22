#!/usr/bin/env node
// @ts-check
"use strict";

/**
 * gerar-json.js
 * =============
 * Le os tres bancos SQLite gerados pelo `extrair_planejamento.py` usando o
 * SQLite embutido do Node (node:sqlite) e produz arquivos JSON prontos para
 * serem consumidos pelo React/Docusaurus na geracao de paginas MDX.
 *
 * Nao ha dependencia nativa (better-sqlite3): usa o modulo interno do Node,
 * disponivel a partir do Node 22.5 (sem flag a partir do Node 23.4 / 24).
 *
 * Saidas (no diretorio --out):
 *   - sincrona.json        (agrupado por disciplina)
 *   - assincrona.json      (agrupado por disciplina)
 *   - procedimentos.json   (agrupado por disciplina)
 *   - disciplinas.json     (consolidado: 1 objeto por disciplina com os 3 tipos)
 *
 * Uso:
 *   node scripts/gerar-json.js
 *   node scripts/gerar-json.js --db-dir ./bancos --out ./src/data
 */

const fs = require("fs");
const path = require("path");

// Silencia apenas o aviso "SQLite is an experimental feature".
const _emitWarning = process.emitWarning;
process.emitWarning = function (warning, ...rest) {
  const nome = rest[0] && rest[0].type ? rest[0].type : rest[0];
  if (nome === "ExperimentalWarning" && String(warning).includes("SQLite")) return;
  return _emitWarning.call(process, warning, ...rest);
};

// Carrega o SQLite embutido do Node com mensagem de erro amigavel.
let DatabaseSync;
try {
  ({ DatabaseSync } = require("node:sqlite"));
} catch (err) {
  console.error(
    "\nNao foi possivel carregar o SQLite embutido do Node (node:sqlite).\n" +
      `Sua versao do Node: ${process.version}\n` +
      "Requer Node 22.5 ou superior. Em versoes 22.5-23.3, rode com a flag:\n" +
      "  node --experimental-sqlite scripts/gerar-json.js ...\n"
  );
  process.exit(1);
}

// --------------------------------------------------------------------------- //
// Argumentos de linha de comando
// --------------------------------------------------------------------------- //
function parseArgs(argv) {
  const args = { dbDir: ".", out: "." };
  for (let i = 0; i < argv.length; i++) {
    const a = argv[i];
    if (a === "--db-dir") args.dbDir = argv[++i];
    else if (a === "--out") args.out = argv[++i];
    else if (a === "-h" || a === "--help") args.help = true;
  }
  return args;
}

function ajuda() {
  console.log(`
Uso: node scripts/gerar-json.js [opcoes]

  --db-dir <dir>   Diretorio com sincrona.db, assincrona.db e procedimentos.db
                   (padrao: diretorio atual)
  --out <dir>      Diretorio de saida dos arquivos .json (padrao: diretorio atual)
  -h, --help       Mostra esta ajuda
`);
}

// --------------------------------------------------------------------------- //
// Utilidades
// --------------------------------------------------------------------------- //

/** Gera um slug seguro para URLs a partir do codigo/disciplina. */
function slugify(texto) {
  return String(texto || "")
    .normalize("NFD")
    .replace(/[\u0300-\u036f]/g, "") // remove acentos
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/^-+|-+$/g, "");
}

/** Converte "5" -> 5 quando for inteiro; caso contrario mantem o texto. */
function numeroOuTexto(v) {
  if (v === null || v === undefined || v === "") return null;
  const n = Number(v);
  return Number.isInteger(n) && String(n) === String(v).trim() ? n : v;
}

/** Abre um banco somente-leitura; retorna null se o arquivo nao existir. */
function abrirBanco(arquivo) {
  if (!fs.existsSync(arquivo)) {
    console.warn(`  ! banco nao encontrado, ignorando: ${arquivo}`);
    return null;
  }
  // A opcao readOnly existe nas versoes recentes; se nao existir, abre normal.
  try {
    return new DatabaseSync(arquivo, { readOnly: true });
  } catch (_e) {
    return new DatabaseSync(arquivo);
  }
}

/**
 * Agrupa registros por disciplina (chave = codigo). Retorna um array de
 * objetos { codigo, disciplina, professor, arquivo, slug, registros[] }.
 * As colunas de agrupamento sao removidas de cada registro individual.
 */
function agruparPorDisciplina(linhas) {
  const grupos = new Map();
  for (const linha of linhas) {
    const codigo = linha.codigo || "sem-codigo";
    if (!grupos.has(codigo)) {
      grupos.set(codigo, {
        codigo,
        disciplina: linha.disciplina || "",
        professor: linha.professor_disciplina || "",
        arquivo: linha.arquivo || "",
        slug: slugify(codigo || linha.disciplina),
        registros: [],
      });
    }
    const {
      // remove os campos de agrupamento do registro individual
      disciplina,
      codigo: _c,
      professor_disciplina,
      arquivo,
      id,
      ...resto
    } = linha;
    grupos.get(codigo).registros.push(resto);
  }
  return [...grupos.values()];
}

// --------------------------------------------------------------------------- //
// Leitura de cada tipo
// --------------------------------------------------------------------------- //
function lerSincronas(dbDir) {
  const db = abrirBanco(path.join(dbDir, "sincrona.db"));
  if (!db) return [];
  const linhas = db
    .prepare(
      `SELECT arquivo, disciplina, codigo, professor_disciplina, id,
              semana, semana_inicio, semana_fim, data,
              cht, ch_planejada, professor, conteudo_previsto
         FROM atividades_sincronas
        ORDER BY codigo, semana`
    )
    .all();
  db.close();
  for (const l of linhas) {
    l.semana = numeroOuTexto(l.semana);
    l.cht = numeroOuTexto(l.cht);
    l.ch_planejada = numeroOuTexto(l.ch_planejada);
  }
  return linhas;
}

function lerAssincronas(dbDir) {
  const db = abrirBanco(path.join(dbDir, "assincrona.db"));
  if (!db) return [];
  const linhas = db
    .prepare(
      `SELECT arquivo, disciplina, codigo, professor_disciplina, id,
              semana, semana_inicio, semana_fim,
              data_inicio, data_fim, ch_ead, conteudo_previsto
         FROM atividades_assincronas
        ORDER BY codigo, semana`
    )
    .all();
  db.close();
  for (const l of linhas) {
    l.semana = numeroOuTexto(l.semana);
    l.ch_ead = numeroOuTexto(l.ch_ead);
  }
  return linhas;
}

function lerProcedimentos(dbDir) {
  const db = abrirBanco(path.join(dbDir, "procedimentos.db"));
  if (!db) return [];
  const linhas = db
    .prepare(
      `SELECT arquivo, disciplina, codigo, professor_disciplina, id,
              atividade, descricao
         FROM procedimentos_ensino
        ORDER BY codigo, id`
    )
    .all();
  db.close();
  return linhas;
}

// --------------------------------------------------------------------------- //
// Escrita dos arquivos
// --------------------------------------------------------------------------- //
function escreverJSON(outDir, nome, dados) {
  const caminho = path.join(outDir, nome);
  fs.writeFileSync(caminho, JSON.stringify(dados, null, 2) + "\n", "utf-8");
  return caminho;
}

function pacotePorTipo(tipo, linhas) {
  const disciplinas = agruparPorDisciplina(linhas);
  return {
    tipo,
    geradoEm: new Date().toISOString(),
    totalRegistros: linhas.length,
    totalDisciplinas: disciplinas.length,
    disciplinas,
  };
}

/** Monta o consolidado: 1 objeto por disciplina com os tres tipos juntos. */
function consolidar(sinc, assinc, proc) {
  const porCodigo = new Map();

  function garantir(codigo, base) {
    if (!porCodigo.has(codigo)) {
      porCodigo.set(codigo, {
        codigo: base.codigo,
        disciplina: base.disciplina,
        professor: base.professor,
        arquivo: base.arquivo,
        slug: base.slug,
        sincronas: [],
        assincronas: [],
        procedimentos: [],
      });
    }
    return porCodigo.get(codigo);
  }

  for (const d of sinc) garantir(d.codigo, d).sincronas = d.registros;
  for (const d of assinc) garantir(d.codigo, d).assincronas = d.registros;
  for (const d of proc) garantir(d.codigo, d).procedimentos = d.registros;

  return {
    geradoEm: new Date().toISOString(),
    totalDisciplinas: porCodigo.size,
    disciplinas: [...porCodigo.values()],
  };
}

// --------------------------------------------------------------------------- //
// Main
// --------------------------------------------------------------------------- //
function main() {
  const args = parseArgs(process.argv.slice(2));
  if (args.help) return ajuda();

  const dbDir = path.resolve(args.dbDir);
  const outDir = path.resolve(args.out);
  fs.mkdirSync(outDir, { recursive: true });

  console.log(`Lendo bancos de : ${dbDir}`);

  const linhasSinc = lerSincronas(dbDir);
  const linhasAssinc = lerAssincronas(dbDir);
  const linhasProc = lerProcedimentos(dbDir);

  const pacoteSinc = pacotePorTipo("sincrona", linhasSinc);
  const pacoteAssinc = pacotePorTipo("assincrona", linhasAssinc);
  const pacoteProc = pacotePorTipo("procedimentos", linhasProc);

  const consolidado = consolidar(
    pacoteSinc.disciplinas,
    pacoteAssinc.disciplinas,
    pacoteProc.disciplinas
  );

  const escritos = [
    escreverJSON(outDir, "sincrona.json", pacoteSinc),
    escreverJSON(outDir, "assincrona.json", pacoteAssinc),
    escreverJSON(outDir, "procedimentos.json", pacoteProc),
    escreverJSON(outDir, "disciplinas.json", consolidado),
  ];

  console.log("\n==================== RESUMO ====================");
  console.log(
    `sincrona.json       : ${pacoteSinc.totalRegistros} registros / ` +
      `${pacoteSinc.totalDisciplinas} disciplinas`
  );
  console.log(
    `assincrona.json     : ${pacoteAssinc.totalRegistros} registros / ` +
      `${pacoteAssinc.totalDisciplinas} disciplinas`
  );
  console.log(
    `procedimentos.json  : ${pacoteProc.totalRegistros} registros / ` +
      `${pacoteProc.totalDisciplinas} disciplinas`
  );
  console.log(
    `disciplinas.json    : ${consolidado.totalDisciplinas} disciplinas (consolidado)`
  );
  console.log(`\nArquivos gravados em: ${outDir}`);
  for (const c of escritos) console.log(`  - ${path.basename(c)}`);
}

main();
