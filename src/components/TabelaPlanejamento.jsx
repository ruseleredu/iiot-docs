import React from 'react';

/**
 * TabelaPlanejamento
 * ------------------
 * Renderiza o planejamento de uma disciplina (Atividades Síncrona,
 * Atividades Assíncrona e Procedimentos de Ensino) a partir de um objeto
 * vindo de `disciplinas.json` (gerado por `scripts/gerar-json.js`).
 *
 * Uso em um arquivo .mdx:
 *
 *   import disciplinas from '@site/src/data/disciplinas.json';
 *   import TabelaPlanejamento from '@site/src/components/TabelaPlanejamento';
 *
 *   export const disciplina = disciplinas.disciplinas.find(
 *     (d) => d.slug === 'elt73a-s22'
 *   );
 *
 *   <TabelaPlanejamento disciplina={disciplina} />
 */

function Secao({ titulo, cor, children }) {
  return (
    <section style={{ marginBottom: '2rem' }}>
      <h2 style={{ borderBottom: `3px solid ${cor}`, paddingBottom: '.3rem' }}>
        {titulo}
      </h2>
      {children}
    </section>
  );
}

function Tabela({ colunas, linhas, vazio }) {
  if (!linhas || linhas.length === 0) {
    return <p><em>{vazio}</em></p>;
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
            {colunas.map((c) => (
              <td key={c.chave}>
                {c.render ? c.render(linha) : linha[c.chave] ?? ''}
              </td>
            ))}
          </tr>
        ))}
      </tbody>
    </table>
  );
}

export default function TabelaPlanejamento({ disciplina }) {
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
          colunas={[
            { chave: 'semana', rotulo: 'Semana' },
            { chave: 'data', rotulo: 'Data' },
            { chave: 'cht', rotulo: 'CHT' },
            { chave: 'ch_planejada', rotulo: 'CH Planejada' },
            { chave: 'professor', rotulo: 'Professor' },
            { chave: 'conteudo_previsto', rotulo: 'Conteúdo previsto' },
          ]}
        />
      </Secao>

      <Secao titulo="Atividades Assíncrona" cor="#4682B4">
        <Tabela
          vazio="Sem atividades assíncronas cadastradas."
          linhas={assincronas}
          colunas={[
            { chave: 'semana', rotulo: 'Semana' },
            {
              chave: 'periodo',
              rotulo: 'Início – Fim',
              render: (l) => `${l.data_inicio} – ${l.data_fim}`,
            },
            { chave: 'ch_ead', rotulo: 'CHEad' },
            { chave: 'conteudo_previsto', rotulo: 'Conteúdo previsto' },
          ]}
        />
      </Secao>

      <Secao titulo="Procedimentos de Ensino" cor="#A07F00">
        <Tabela
          vazio="Sem procedimentos cadastrados."
          linhas={procedimentos}
          colunas={[
            { chave: 'atividade', rotulo: 'Atividade' },
            { chave: 'descricao', rotulo: 'Descrição' },
          ]}
        />
      </Secao>
    </div>
  );
}
