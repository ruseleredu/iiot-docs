/**
 * Tipos dos dados de Planejamento de Aula gerados por scripts/gerar-json.js.
 * Use-os para tipar os imports de JSON no React/Docusaurus.
 */

/** Uma linha de Atividade Síncrona. */
export interface AtividadeSincrona {
  semana: number | string | null;
  semana_inicio: string | null;
  semana_fim: string | null;
  data: string;
  cht: number | string | null;
  ch_planejada: number | string | null;
  professor: string;
  conteudo_previsto: string;
}

/** Uma linha de Atividade Assíncrona. */
export interface AtividadeAssincrona {
  semana: number | string | null;
  semana_inicio: string | null;
  semana_fim: string | null;
  data_inicio: string;
  data_fim: string;
  ch_ead: number | string | null;
  conteudo_previsto: string;
}

/** Um procedimento de ensino. */
export interface Procedimento {
  atividade: string;
  descricao: string;
}

/** Uma disciplina no arquivo consolidado `disciplinas.json`. */
export interface Disciplina {
  codigo: string;
  disciplina: string;
  professor: string;
  arquivo?: string;
  slug: string;
  sincronas: AtividadeSincrona[];
  assincronas: AtividadeAssincrona[];
  procedimentos: Procedimento[];
}

/** Estrutura do arquivo `disciplinas.json`. */
export interface PlanejamentoConsolidado {
  geradoEm: string;
  totalDisciplinas: number;
  disciplinas: Disciplina[];
}

/** Um grupo (disciplina) dentro dos arquivos por tipo. */
export interface DisciplinaTipo<T> {
  codigo: string;
  disciplina: string;
  professor: string;
  arquivo?: string;
  slug: string;
  registros: T[];
}

/**
 * Estrutura dos arquivos por tipo: `sincrona.json`, `assincrona.json` e
 * `procedimentos.json`.
 */
export interface PacoteTipo<T> {
  tipo: "sincrona" | "assincrona" | "procedimentos";
  geradoEm: string;
  totalRegistros: number;
  totalDisciplinas: number;
  disciplinas: DisciplinaTipo<T>[];
}
