import React from 'react';
import type {
  Disciplina,
  AtividadeSincrona,
  AtividadeAssincrona,
  Procedimento,
} from '../../types/planejamento';

/**
 * TabelaPlanejamento
 * ------------------
 * Renderiza o planejamento de uma disciplina (Atividades Síncrona,
 * Atividades Assíncrona e Procedimentos de Ensino) a partir de um objeto
 * vindo de `disciplinas.json` (gerado por `scripts/gerar-json.js`).
 *
 * Uso em um arquivo .mdx (a parte ESM do MDX é JavaScript, sem cast de TS):
 *
 *   import disciplinas from '@site/src/data/disciplinas.json';
 *   import TabelaPlanejamento from '@site/src/components/TabelaPlanejamento';
 *
 *   export const disciplina = disciplinas.disciplinas.find(
 *     (item) => item.slug === 'elt73a-s22'
 *   );
 *
 *   <TabelaPlanejamento disciplina={disciplina} />
 *
 * Em uma página .tsx (aí sim com tipos), importe PlanejamentoConsolidado de
 * '@site/src/types/planejamento' e faça o cast do JSON antes de usar.
 */

interface Coluna<T> {
  chave: string;
  rotulo: string;
  render?: (linha: T) => React.ReactNode;
}

interface SecaoProps {
  titulo: string;
  cor: string;
  children: React.ReactNode;
}

function Secao({ titulo, cor, children }: SecaoProps): React.ReactElement {
  return (
    <section style={{ marginBottom: '2rem' }}>
      <h2 style={{ borderBottom: `3px solid ${cor}`, paddingBottom: '.3rem' }}>
        {titulo}
      </h2>
      {children}
    </section>
  );
}

interface TabelaProps<T> {
  colunas: Coluna<T>[];
  linhas: T[];
  vazio: string;
}

function Tabela<T>({ colunas, linhas, vazio }: TabelaProps<T>): React.ReactElement {
  if (!linhas || linhas.length === 0) {
    return (
      <p>
        <em>{vazio}</em>
      </p>
    );
  }
  return (
    <table style={{ display: 'table', width: '100%' }}>
      <thead>
        <tr>
          {colunas.map((c) => (
            <th key={c.chave}>{c.rotulo}</th>
          ))}
        </tr>
      </thead>
      <tbody>
        {linhas.map((linha, i) => (
          <tr key={i}>
            {colunas.map((c) => {
              const valor = c.render
                ? c.render(linha)
                : ((linha as Record<string, unknown>)[c.chave] as React.ReactNode);
              return <td key={c.chave}>{valor ?? ''}</td>;
            })}
          </tr>
        ))}
      </tbody>
    </table>
  );
}

export interface TabelaPlanejamentoProps {
  disciplina?: Disciplina;
}

export default function TabelaPlanejamento({
  disciplina,
}: TabelaPlanejamentoProps): React.ReactElement {
  if (!disciplina) {
    return (
      <p>
        <strong>Disciplina não encontrada.</strong> Verifique o <code>slug</code>{' '}
        informado e se o arquivo <code>disciplinas.json</code> foi gerado.
      </p>
    );
  }

  const {
    disciplina: nome,
    codigo,
    professor,
    sincronas = [],
    assincronas = [],
    procedimentos = [],
  } = disciplina;

  const colunasSincronas: Coluna<AtividadeSincrona>[] = [
    { chave: 'semana', rotulo: 'Semana' },
    { chave: 'data', rotulo: 'Data' },
    { chave: 'cht', rotulo: 'CHT' },
    { chave: 'ch_planejada', rotulo: 'CH Planejada' },
    { chave: 'professor', rotulo: 'Professor' },
    { chave: 'conteudo_previsto', rotulo: 'Conteúdo previsto' },
  ];

  const colunasAssincronas: Coluna<AtividadeAssincrona>[] = [
    { chave: 'semana', rotulo: 'Semana' },
    {
      chave: 'periodo',
      rotulo: 'Início – Fim',
      render: (l) => `${l.data_inicio} – ${l.data_fim}`,
    },
    { chave: 'ch_ead', rotulo: 'CHEad' },
    { chave: 'conteudo_previsto', rotulo: 'Conteúdo previsto' },
  ];

  const colunasProcedimentos: Coluna<Procedimento>[] = [
    { chave: 'atividade', rotulo: 'Atividade' },
    { chave: 'descricao', rotulo: 'Descrição' },
  ];

  return (
    <div>
      <p>
        <strong>Código:</strong> {codigo}
        {professor ? (
          <>
            {' · '}
            <strong>Professor(a):</strong> {professor}
          </>
        ) : null}
      </p>

      <Secao titulo="Atividades Síncrona" cor="#007F00">
        <Tabela
          vazio="Sem atividades síncronas cadastradas."
          linhas={sincronas}
          colunas={colunasSincronas}
        />
      </Secao>

      <Secao titulo="Atividades Assíncrona" cor="#4682B4">
        <Tabela
          vazio="Sem atividades assíncronas cadastradas."
          linhas={assincronas}
          colunas={colunasAssincronas}
        />
      </Secao>

      <Secao titulo="Procedimentos de Ensino" cor="#A07F00">
        <Tabela
          vazio="Sem procedimentos cadastrados."
          linhas={procedimentos}
          colunas={colunasProcedimentos}
        />
      </Secao>
    </div>
  );
}
