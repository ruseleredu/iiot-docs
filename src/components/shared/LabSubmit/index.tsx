import React, { useState, type ReactElement } from 'react';
import Tabs from '@theme/Tabs';
import TabItem from '@theme/TabItem';
import Admonition from '@theme/Admonition';
import labassigns from '@site/src/data/labassigns.json';
import styles from './styles.module.css';

// Grupos e organização da turma. Ajuste aqui se a lista mudar.
import { GROUPS, ORG, labgradehref } from '../../constants';

// Aceita tanto { "lab00": 1748058 } quanto { "lab00": { cmid, title } }.
type LabEntry = number | { cmid: number; title?: string };

interface LabAssigns {
  moodleBaseUrl: string;
  labs: Record<string, LabEntry>;
}

const data = labassigns as LabAssigns;

function CopyButton({ text }: { text: string }): ReactElement {
  const [copied, setCopied] = useState(false);

  function copy(): void {
    if (!navigator.clipboard) return;
    navigator.clipboard.writeText(text).then(() => {
      setCopied(true);
      setTimeout(() => setCopied(false), 1500);
    });
  }

  return (
    <button type="button" className={styles.copyBtn} onClick={copy}>
      {copied ? 'Copiado' : 'Copiar'}
    </button>
  );
}

export interface LabSubmitProps {
  labName: string;
}

export default function LabSubmit({ labName }: LabSubmitProps): ReactElement {
  const base = (data.moodleBaseUrl || '').replace(/\/$/, '');
  const entry = data.labs[labName];

  const cmid: number | undefined =
    typeof entry === 'number' ? entry : entry?.cmid;
  const title: string =
    (typeof entry === 'object' && entry?.title) || labName;

  if (!cmid) {
    return (
      <div className={styles.warning}>
        A atividade <code>{labName}</code> ainda não tem <code>cmid</code>{' '}
        configurado em <code>src/data/labassigns.json</code>.
      </div>
    );
  }

  const submitUrl = `${base}/mod/assign/view.php?id=${cmid}&action=editsubmission`;

  return (
    <div className={styles.wrapper}>
      <Tabs groupId="grupo" queryString="grupo">
        {GROUPS.map((g) => {
          const repo = `${labName}-grupo-${g.toLowerCase()}`;
          const repoUrl = `https://github.com/${ORG}/${repo}`;

          return (
            <TabItem key={g} value={g} label={`${g}`}>
              <div className={styles.card}>
                <p className={styles.repoLabel}>
                  Repositório do <strong>Grupo {g}</strong> para {title}:
                </p>

                <div className={styles.repoRow}>
                  <a href={repoUrl} target="_blank" rel="noreferrer">
                    <code>
                      {ORG}/{repo}
                    </code>
                  </a>
                  <CopyButton text={repoUrl} />
                </div>

                <ol className={styles.steps}>
                  <li>Copie o link do repositório acima.</li>
                  <li>Abra a página de envio da atividade no Moodle (botão abaixo).</li>
                  <li>
                    Clique em <strong>Adicionar envio</strong>.
                  </li>
                  <li>
                    Cole o link no campo <strong>Texto online</strong>.
                  </li>
                  <li>
                    Clique em <strong>Salvar mudanças</strong>.
                  </li>
                  <li>
                    Confira se o status mudou para{' '}
                    <em>Enviado para avaliação</em>.
                  </li>
                </ol>

                <a
                  className={styles.submitBtn}
                  href={submitUrl}
                  target="_blank"
                  rel="noreferrer"
                >
                  Abrir envio no Moodle
                </a>
              </div>
            </TabItem>
          );
        })}
      </Tabs>
      <Admonition type="info" title="Avaliação por commits">
        <p>
          Cada cartão <strong>Ponto de commit</strong> é uma tarefa: faça-a, copie o comando do cartão e rode.
          A mensagem começa com o código (<code>T1:</code>, <code>T2:</code>…) — é como a correção identifica sua entrega.
          Um commit por tarefa; pode refazer (vale o mais recente); e <strong>não esqueça o <code>git push</code></strong>.
          Detalhes em <a href="${labgradehref}">Como funciona a avaliação</a>.
        </p>
      </Admonition>
    </div>
  );
}
