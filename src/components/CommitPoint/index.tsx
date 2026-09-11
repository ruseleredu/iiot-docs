import { useId, useRef, useEffect, type ReactNode } from 'react';
import { useLocation } from '@docusaurus/router';
import ThemeCodeBlock from '@theme/CodeBlock';
import Admonition from '@theme/Admonition';

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
  /** Tipo do admonition. Default: 'info'. */
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
}: CommitPointProps): ReactNode {
  const auto = useAutoNumber();
  const numero = n != null ? n : auto;
  const token = `${prefix}${numero}`;
  const pts = pontos != null ? pontos : points;

  // Id da ancora: explicito ou derivado do token (ex.: "T1" -> "t1").
  const anchorId = (id ?? token).toLowerCase();

  const mensagem = `${token}: ${task}`;
  const comando =
    `git add ${files} && git commit -m "${mensagem}"` + (push ? ' && git push' : '');

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
        <ThemeCodeBlock language="bash">{comando}</ThemeCodeBlock>
      </Admonition>
    </div>
  );
}
