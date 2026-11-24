import React, { useState, type CSSProperties, type ReactElement } from 'react';
import Tabs from '@theme/Tabs';
import TabItem from '@theme/TabItem';
import labassigns from '@site/src/data/labassigns.json';

// Grupos e organização da turma. Ajuste em constants se a lista mudar.
import { GROUPS, ORG } from '../constants'; // one folder up

// Aceita tanto { "projeto": 1748058 } quanto { "projeto": { cmid, title } }.
type LabEntry = number | { cmid: number; title?: string };

interface LabAssigns {
  moodleBaseUrl: string;
  labs: Record<string, LabEntry>;
}

const data = labassigns as LabAssigns;

// Estilos embutidos (equivalentes ao antigo styles.module.css)
const s: Record<string, CSSProperties> = {
  wrapper: { margin: '1.5rem 0' },
  card: {
    border: '1px solid var(--ifm-color-emphasis-300)',
    borderRadius: 'var(--ifm-global-radius, 8px)',
    padding: '1rem 1.25rem',
    background: 'var(--ifm-background-surface-color)',
  },
  repoLabel: { margin: '0 0 0.5rem' },
  repoRow: {
    display: 'flex',
    alignItems: 'center',
    gap: '0.5rem',
    flexWrap: 'wrap',
    marginBottom: '1rem',
  },
  steps: { margin: '0 0 1.25rem', paddingLeft: '1.25rem' },
  step: { margin: '0.3rem 0' },
  copyBtn: {
    border: '1px solid var(--ifm-color-emphasis-300)',
    color: 'var(--ifm-font-color-base)',
    borderRadius: 6,
    padding: '0.15rem 0.6rem',
    fontSize: '0.8rem',
    cursor: 'pointer',
  },
  submitBtn: {
    display: 'inline-block',
    background: 'var(--ifm-color-primary)',
    color: '#fff',
    padding: '0.5rem 1rem',
    borderRadius: 6,
    fontWeight: 600,
    textDecoration: 'none',
  },
  warning: {
    border: '1px solid var(--ifm-color-warning-dark)',
    background: 'var(--ifm-color-warning-contrast-background)',
    color: 'var(--ifm-color-warning-contrast-foreground)',
    padding: '0.75rem 1rem',
    borderRadius: 'var(--ifm-global-radius, 8px)',
  },
};

function CopyButton({ text }: { text: string }): ReactElement {
  const [copied, setCopied] = useState(false);
  const [hover, setHover] = useState(false);

  function copy(): void {
    if (!navigator.clipboard) return;
    navigator.clipboard.writeText(text).then(() => {
      setCopied(true);
      setTimeout(() => setCopied(false), 1500);
    });
  }

  return (
    <button
      type="button"
      style={{
        ...s.copyBtn,
        background: hover
          ? 'var(--ifm-color-emphasis-200)'
          : 'var(--ifm-color-emphasis-100)',
      }}
      onMouseEnter={() => setHover(true)}
      onMouseLeave={() => setHover(false)}
      onClick={copy}
    >
      {copied ? 'Copiado' : 'Copiar'}
    </button>
  );
}

function SubmitButton({ href }: { href: string }): ReactElement {
  const [hover, setHover] = useState(false);
  return (
    <a
      href={href}
      target="_blank"
      rel="noreferrer"
      style={{ ...s.submitBtn, opacity: hover ? 0.9 : 1, color: '#fff' }}
      onMouseEnter={() => setHover(true)}
      onMouseLeave={() => setHover(false)}
    >
      Abrir envio no Moodle
    </a>
  );
}

export interface PjtSubmitProps {
  /** Prefixo dos repositórios e chave em labassigns.json, ex: "projeto" */
  pjtName?: string;
}

export default function PjtSubmit({
  pjtName = 'projeto',
}: PjtSubmitProps): ReactElement {
  const base = (data.moodleBaseUrl || '').replace(/\/$/, '');
  const entry = data.labs[pjtName];

  const cmid: number | undefined =
    typeof entry === 'number' ? entry : entry?.cmid;
  const title: string =
    (typeof entry === 'object' && entry?.title) || 'o Projeto Final';

  if (!cmid) {
    return (
      <div style={s.warning}>
        A atividade <code>{pjtName}</code> ainda não tem <code>cmid</code>{' '}
        configurado em <code>src/data/labassigns.json</code>.
      </div>
    );
  }

  const submitUrl = `${base}/mod/assign/view.php?id=${cmid}&action=editsubmission`;

  return (
    <div style={s.wrapper}>
      <Tabs groupId="grupo" queryString="grupo">
        {GROUPS.map((g) => {
          const repo = `${pjtName}-grupo-${g.toLowerCase()}`;
          const repoUrl = `https://github.com/${ORG}/${repo}`;

          return (
            <TabItem key={g} value={g} label={g}>
              <div style={s.card}>
                <p style={s.repoLabel}>
                  Repositório do <strong>Grupo {g}</strong> para {title}:
                </p>

                <div style={s.repoRow}>
                  <a href={repoUrl} target="_blank" rel="noreferrer">
                    <code>
                      {ORG}/{repo}
                    </code>
                  </a>
                  <CopyButton text={repoUrl} />
                </div>

                <ol style={s.steps}>
                  <li style={s.step}>Copie o link do repositório acima.</li>
                  <li style={s.step}>
                    Abra a página de envio da atividade no Moodle (botão abaixo).
                  </li>
                  <li style={s.step}>
                    Clique em <strong>Adicionar envio</strong>.
                  </li>
                  <li style={s.step}>
                    Cole o link no campo <strong>Texto online</strong>.
                  </li>
                  <li style={s.step}>
                    Clique em <strong>Salvar mudanças</strong>.
                  </li>
                  <li style={s.step}>
                    Confira se o status mudou para{' '}
                    <em>Enviado para avaliação</em>.
                  </li>
                </ol>

                <SubmitButton href={submitUrl} />
              </div>
            </TabItem>
          );
        })}
      </Tabs>
    </div>
  );
}
