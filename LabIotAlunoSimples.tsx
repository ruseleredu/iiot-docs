import React from "react";
import Tabs from "@theme/Tabs";
import TabItem from "@theme/TabItem";
import ThemeCodeBlock from "@theme/CodeBlock";
import Admonition from "@theme/Admonition";
import Link from "@docusaurus/Link";

import { COURSE, GROUPS, HOMEFOLDER, PRESETS_IOT, GenIotOpcoes } from "../constants";

/* ------------------------------------------------------------------ */
/* Versão simplificada do LabIotAluno: só os comandos mais usados       */
/* ------------------------------------------------------------------ */

// as mesmas do gen_iot_aluno.py (DISCIPLINAS)
const DISCIPLINAS: Record<string, { nome: string }> = {
    elt85b: { nome: "IoT Industrial" },
    elt73a: { nome: "Sistemas Microcontrolados" },
};

type Opcoes = GenIotOpcoes & {
    docs?: boolean;
    docsModo?: "pages" | "build";
    docsMinutos?: number;
    docsRepo?: string;
    docsRamo?: string;
    docsCaminho?: string;
};

function montarFlags(o: Opcoes): string[] {
    const f: string[] = [];
    if (o.semGitea) {
        f.push("--sem-gitea");
    } else {
        if (o.semRunner) f.push("--sem-runner");
        if (o.giteaDb && o.giteaDb !== "sqlite") f.push(`--gitea-db ${o.giteaDb}`);
        if (o.giteaRepo !== undefined && o.giteaRepo !== "nodered") f.push(`--gitea-repo "${o.giteaRepo}"`);
    }
    if (o.semMicrobin) f.push("--sem-microbin");
    if (o.semFuxa) f.push("--sem-fuxa");
    if (o.semNtfy) f.push("--sem-ntfy");
    if (o.semMqttExplorer) f.push("--sem-mqtt-explorer");
    if (o.semSenha) f.push("--sem-senha");
    if (o.protegerHttp) f.push("--proteger-http");
    if (o.mqttSemAnonimo) f.push("--mqtt-sem-anonimo");
    if (o.portaHttp && o.portaHttp !== 80) f.push(`--porta-http ${o.portaHttp}`);
    if (o.ponteMqtt) f.push(`--ponte-mqtt ${o.ponteMqtt}`);
    if (o.captura) {
        f.push("--captura");
        if (o.capturaFiltro) f.push(`--captura-filtro "${o.capturaFiltro}"`);
    }
    if (o.docs) {
        f.push("--docs");
        if (o.docsModo && o.docsModo !== "pages") f.push(`--docs-modo ${o.docsModo}`);
        if (o.docsMinutos !== undefined && o.docsMinutos !== 60) f.push(`--docs-minutos ${o.docsMinutos}`);
        if (o.docsRepo) f.push(`--docs-repo ${o.docsRepo}`);
        if (o.docsRamo) f.push(`--docs-ramo ${o.docsRamo}`);
        if (o.docsCaminho) f.push(`--docs-caminho ${o.docsCaminho}`);
    }
    if (o.extras) f.push(...o.extras);
    return f;
}

type LabIotAlunoSimplesProps = {
    /** Nome do laboratório, ex: "lab05" */
    labName?: string;
    /** Sobrescreve/complementa o preset do laboratório */
    opcoes?: Opcoes;
    /** Grupos exibidos (padrão: GROUPS de constants) */
    grupos?: readonly string[];
    /**
     * Página com a versão completa (componente LabIotAluno).
     * Padrão: `/labs/<LABNAME>-docker`. Use `false` para não exibir.
     */
    completo?: string | false;
    /** Texto antes do link da versão completa */
    completoTexto?: string;
};

const GRUPO_VALIDO = /^[a-z]$/;

function Cmd({ children }: { children: string }) {
    return <ThemeCodeBlock className="language-bash">{children}</ThemeCodeBlock>;
}

const PARAR_TUDO = `for /f "delims=" %i in ('docker compose ls -q') do docker compose -p %i down`;

export default function LabIotAlunoSimples({
    labName = "lab05",
    opcoes,
    grupos = GROUPS,
    completo,
    completoTexto,
}: LabIotAlunoSimplesProps) {
    const lab = labName.toLowerCase();
    const urlCompleto = completo === false ? null : completo ?? `/labs/${labName.toUpperCase()}-docker`;
    const o: Opcoes = { ...(PRESETS_IOT[lab] ?? {}), ...(opcoes ?? {}) };
    const flags = montarFlags(o);
    const disciplina = COURSE.toLowerCase();
    const disc = DISCIPLINAS[disciplina];

    const porta = o.portaHttp ?? 80;
    const base = `http://localhost${porta === 80 ? "" : `:${porta}`}`;
    const pastaMae = `%USERPROFILE%\\${HOMEFOLDER}`;

    return (
        <>
            <Admonition type="info" title="Antes de começar">
                <p>
                    Precisa do <b>Docker Desktop</b> aberto e do <b>Python 3</b>. Os comandos são para o{" "}
                    <b>Prompt de Comando</b> (cmd) do Windows.
                </p>
                <Cmd>{`docker desktop start`}</Cmd>
                <p>
                    <b>Atenção:</b> desligue tudo o que estiver rodando no Docker (outros LABs, outros
                    projetos), para não haver conflito de portas nem falta de memória:
                </p>
                <Cmd>{PARAR_TUDO}</Cmd>
                <p>
                    Disciplina: <b>{COURSE}{disc ? ` - ${disc.nome}` : ""}</b>.
                </p>
            </Admonition>

            <Tabs>
                {/* P (professor) e N (notas) não são grupos de alunos */}
                {grupos.filter((g) => !["p", "n"].includes(g.toLowerCase())).map((group) => {
                    const letra = group.toLowerCase();
                    const conta = `${lab}-${letra}`;
                    const repo = `${pastaMae}\\${labName}-grupo-${letra}`;
                    const atalhos = [
                        `set "IOT_REPO=${repo}"`,
                        `set "IOT_GEN=%IOT_REPO%\\docker\\gen_iot_aluno.py"`,
                        `set "IOT_DIR=%IOT_REPO%\\docker\\${conta}"`,
                    ].join("\n");
                    const entrar = `cd /d "%IOT_DIR%"`;
                    const gerar = [`py "%IOT_GEN%"`, `--disciplina ${disciplina}`, `--lab ${lab}`, `--grupo ${letra}`, ...flags, `--saida "%IOT_DIR%"`].join(" ");
                    const valido = GRUPO_VALIDO.test(letra);

                    const nr = `${conta}-nodered`;
                    const dataNr = `data\\${conta}`;
                    const limparFluxos =
                        `(${entrar} && docker compose stop ${nr} && (del /q "${dataNr}\\flows.json" "${dataNr}\\flows_cred.json" ` +
                        `"${dataNr}\\.flows*.backup" 2>nul & docker compose start ${nr}))`;

                    return (
                        <TabItem key={group} value={letra} label={group}>
                            {!valido ? (
                                <Admonition type="danger" title="Grupo inválido">
                                    O <code>gen_iot_aluno.py</code> aceita só uma letra de <code>a</code> a{" "}
                                    <code>z</code> (sem <code>p</code> e <code>n</code>); <code>{group}</code> não serve.
                                </Admonition>
                            ) : (
                                <>
                                    <p>
                                        <b>1.</b> Crie os atalhos (valem só nesta janela do cmd; abriu outra, rode de novo):
                                    </p>
                                    <Cmd>{atalhos}</Cmd>

                                    <p><b>2.</b> Gere o LAB IoT do grupo em <code>{`docker\\${conta}`}</code>:</p>
                                    <Cmd>{gerar}</Cmd>

                                    <p><b>3.</b> Suba os containers (a primeira vez demora):</p>
                                    <Cmd>{`${entrar} && docker compose up -d --build`}</Cmd>

                                    <p><b>4.</b> Abra o Portal: <a href={`${base}/`} target="_blank" rel="noopener noreferrer">{`${base}/`}</a></p>
                                    <Cmd>{`start ${base}/`}</Cmd>
                                    <p>
                                        <b>5.</b> Limpar (voltar ao original) — <b>só os fluxos</b> (mantém os nós
                                        instalados e os bancos):
                                    </p>
                                    <Cmd>{limparFluxos}</Cmd>
                                </>
                            )}
                        </TabItem>
                    );
                })}
            </Tabs>

            {urlCompleto && (
                <Admonition type="tip" title="Precisa de mais?">
                    <p>
                        {completoTexto ?? "Outros comandos (credenciais, logs, atualizar, limpar paleta/FUXA, zerar tudo) na"}{" "}
                        <Link to={urlCompleto}>
                            <b>versão completa</b>
                        </Link>.
                    </p>
                </Admonition>
            )}
        </>
    );
}
