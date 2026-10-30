import { useId, useRef, useEffect, type ReactNode } from 'react';
import { useLocation } from '@docusaurus/router';
import ThemeCodeBlock from '@theme/CodeBlock';
import Admonition from '@theme/Admonition';
import useBrokenLinks from '@docusaurus/useBrokenLinks';

/** Tipos de admonition suportados pelo Docusaurus. */
export type AdmonitionType = 'note' | 'tip' | 'info' | 'warning' | 'danger';

/*
 * Numeracao automatica em ordem do documento, por pagina.
 * - Cada instancia recebe um numero sequencial (1, 2, 3, ...) conforme aparece.
 * - Deduplicacao por useId => estavel sob re-render / StrictMode.
 * - Limpeza no unmount zera o contador ao sair da pagina => voltar renumera.
 */
const registry = new Map<string, { ids: Map<string, number>; count: number }>();

function useAutoNumber(): number {
  const { pathname } = useLocation();
  const id = useId();
  const numRef = useRef<number | null>(null);

  let bucket = registry.get(pathname);
  if (!bucket) {
    bucket = { ids: new Map(), count: 0 };
    registry.set(pathname, bucket);
  }

  if (numRef.current == null) {
    if (!bucket.ids.has(id)) {
      bucket.count += 1;
      bucket.ids.set(id, bucket.count);
    }
    numRef.current = bucket.ids.get(id)!;
  }

  useEffect(() => {
    return () => {
      const b = registry.get(pathname);
      if (b) {
        b.ids.delete(id);
        if (b.ids.size === 0) b.count = 0;
      }
    };
  }, [pathname, id]);

  return numRef.current!;
}

export interface CommitPointProps {
  /** Descricao da tarefa (obrigatoria). */
  task: string;
  /** Tipo do admonition. Default: 'tip'. */
  type?: AdmonitionType;
  /** Pontos da tarefa (exibidos no titulo). */
  pontos?: number;
  /** Alias de `pontos`. */
  points?: number;
  /** Arquivos do `git add`. Default: '.'. */
  files?: string;
  /** Prefixo do token. Default: 'T'. */
  prefix?: string;
  /** Inclui `&& git push`. Default: true. */
  push?: boolean;
  /** Forca o numero, ignorando o incremento automatico. */
  n?: number;
  /** Titulo opcional; sobrescreve o padrao "Ponto de commit - T<n>". */
  title?: ReactNode;
  /** Id da ancora para deep-link. Default: o token em minusculas (ex.: "t1"). */
  id?: string;
  /** Marca a tarefa com commit vazio (ex.: deploy/release, que nao muda arquivos). */
  allowEmpty?: boolean;
  /** Comando extra mostrado apos o commit (ex.: alias de deploy). */
  run?: string;
  /**
   * Mostra, em blocos separados: antes do commit, `git conferir <files>` (alias do Lab 01:
   * terminal na raiz e cada arquivo no lugar); depois do push, o que o commit levou e se foi
   * enviado. Default: true; `check={false}` mostra so o commit.
   */
  check?: boolean;
}

export default function CommitPoint({
  task,
  type = 'info',
  pontos,
  points,
  files = '.',
  prefix = 'T',
  push = true,
  n,
  title,
  id,
  allowEmpty = false,
  run,
  check = true,
}: CommitPointProps): ReactNode {
  const auto = useAutoNumber();
  const numero = n != null ? n : auto;
  const token = `${prefix}${numero}`;
  const pts = pontos != null ? pontos : points;

  useBrokenLinks().collectAnchor(id);   // registra #tN no verificador de âncoras
  // Id da ancora: explicito ou derivado do token (ex.: "T1" -> "t1").
  const anchorId = (id ?? token).toLowerCase();

  const mensagem = `${token}: ${task}`;
  const commit = allowEmpty
    ? `git commit --allow-empty -m "${mensagem}"`             // deploy/release: sem mudanca de arquivo
    : `git add ${files} && git commit -m "${mensagem}"`;
  const comando = commit + (push ? ' && git push' : '') + (run ? `\n${run}` : '');

  // Conferencia (check):
  // - antes: "git conferir <arquivos>", alias configurado uma vez no Lab 01 (Parte 2.1). O Git
  //   roda o alias na raiz do repositorio, de qualquer subpasta: ele mostra a raiz, avisa se o
  //   terminal esta numa subpasta (o git add do passo 2 tem de rodar na raiz), marca cada
  //   arquivo como "ok" ou "FALTA" e mostra o "git status --short --ignored" so deles
  //   (?? novo, M modificado, !! ignorado; quem nao aparece ja esta no Git sem mudanca).
  // - depois: a 1a linha do "git status -sb" diz se o commit ja foi enviado ([ahead N] = nao),
  //   e o "git log -1 --stat" lista os arquivos que o commit levou.
  const lista = files.split(/\s+/).filter((f) => f && !f.startsWith('-') && f !== '.');
  const antes = ['git conferir', ...lista].join(' ');
  const depois = 'git status -sb && git log -1 --stat --oneline';

  const tituloPadrao: ReactNode = (
    <>
      {`Ponto de commit · ${token}${pts != null ? ` (${pts} pts)` : ''}`}{' '}
      <a
        href={`#${anchorId}`}
        aria-label={`Link direto para ${token}`}
        title={`Link direto para ${token}`}
        style={{ textDecoration: 'none', opacity: 0.55 }}>
        #
      </a>
    </>
  );

  return (
    <div id={anchorId} style={{ scrollMarginTop: 'var(--ifm-navbar-height, 60px)' }}>
      <Admonition type={type} title={title ?? tituloPadrao}>
        <p>{task}</p>
        {check ? (
          <>
            <ThemeCodeBlock language="bash" title="1. Conferir os arquivos">
              {antes}
            </ThemeCodeBlock>
            <ThemeCodeBlock language="bash" title={`2. Commit ${token}${push ? ' e push' : ''}`}>
              {comando}
            </ThemeCodeBlock>
            <ThemeCodeBlock language="bash" title="3. Conferir o commit e o envio">
              {depois}
            </ThemeCodeBlock>
            <p style={{ fontSize: '0.85em', marginBottom: 0 }}>
              Só faça o commit se o passo 1 não mostrar <code>ATENCAO</code> (terminal fora da
              raiz do repositório){lista.length ? <> nem <code>FALTA</code></> : ''}.
              {lista.length > 0 && (
                <>
                  {' '}Nas mudanças, <code>??</code> é arquivo novo e <code>M</code>, modificado:
                  os dois entram no commit. <code>!!</code> é arquivo bloqueado pelo{' '}
                  <code>.gitignore</code>, e o <code>git add</code> vai falhar. Um arquivo que não
                  aparece ali já está no Git e não mudou desde o último commit.
                </>
              )}{' '}
              No passo 3, a primeira linha não pode ter <code>[ahead</code> (commit ainda não
              enviado){lista.length ? `, e a lista tem de trazer os arquivos da ${token}` : ''}.
            </p>
          </>
        ) : (
          <ThemeCodeBlock language="bash">{comando}</ThemeCodeBlock>
        )}
      </Admonition>
    </div>
  );
}
