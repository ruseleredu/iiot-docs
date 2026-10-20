import React from "react";
import Tabs from "@theme/Tabs";
import TabItem from "@theme/TabItem";
import ThemeCodeBlock from "@theme/CodeBlock";
import Admonition from "@theme/Admonition";

import { GROUPS, HOMEFOLDER } from "../constants"; // one folder up

/* ------------------------------------------------------------------ */
/* Opções do gen_iot_aluno.py                                           */
/* ------------------------------------------------------------------ */

/** Opções do gen_iot_aluno.py (cada uma vira um argumento de linha de comando). */
export type GenIotOpcoes = {
    /** --sem-gitea: sem Gitea e sem CI */
    semGitea?: boolean;
    /** --sem-runner: Gitea sem Actions */
    semRunner?: boolean;
    /** --gitea-db postgres (padrão sqlite) */
    giteaDb?: "sqlite" | "postgres";
    /** --gitea-repo <nome> (padrão "nodered"; "" = nenhum) */
    giteaRepo?: string;
    /** --sem-microbin */
    semMicrobin?: boolean;
    /** --sem-fuxa */
    semFuxa?: boolean;
    /** --sem-ntfy */
    semNtfy?: boolean;
    /** --sem-mqtt-explorer */
    semMqttExplorer?: boolean;
    /** --sem-senha: tudo aberto, sem login */
    semSenha?: boolean;
    /** --proteger-http: login nos dashboards e no FUXA */
    protegerHttp?: boolean;
    /** --mqtt-sem-anonimo: MQTT exige usuário/senha */
    mqttSemAnonimo?: boolean;
    /** --porta-http <n> (padrão 80) */
    portaHttp?: number;
    /** --ponte-mqtt HOST[:PORTA]: liga o broker local ao do laboratório */
    ponteMqtt?: string;
    /** --captura: netshoot gravando .pcap para o Wireshark */
    captura?: boolean;
    /** --captura-filtro "<BPF>", ex.: "port 1883" */
    capturaFiltro?: string;
    /** Argumentos extras, passados como estão (ex.: ["--runner-capacidade 2"]) */
    extras?: string[];
};

/**
 * Pré-configuração por laboratório. A página pode sobrescrever qualquer opção
 * com a prop `opcoes`.
 */
export const PRESETS_IOT: Record<string, GenIotOpcoes> = {
    lab05: {}, // LAB IoT completo
    lab06: { semGitea: true, semMicrobin: true },
    lab07: { semGitea: true, semMicrobin: true, semFuxa: true, semNtfy: true },
    lab08: { captura: true, capturaFiltro: "port 1883" },
    projeto: {},
};

function montarFlags(o: GenIotOpcoes): string[] {
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
    if (o.extras) f.push(...o.extras);
    return f;
}

/* ------------------------------------------------------------------ */
/* Componente                                                           */
/* ------------------------------------------------------------------ */

type LabIotAlunoProps = {
    /** Nome do laboratório, ex: "lab05", "lab07" (minúsculas, começa com letra) */
    labName?: string;
    /** Sobrescreve/complementa o preset do laboratório */
    opcoes?: GenIotOpcoes;
    /** Grupos exibidos (padrão: GROUPS de constants) */
    grupos?: readonly string[];
};

const GRUPO_VALIDO = /^[a-z]$/; // o script aceita uma letra a..z, exceto p e n

function Cmd({ children }: { children: string }) {
    return <ThemeCodeBlock className="language-bash">{children}</ThemeCodeBlock>;
}

export default function LabIotAluno({
    labName = "lab05",
    opcoes,
    grupos = GROUPS,
}: LabIotAlunoProps) {
    const lab = labName.toLowerCase();
    const o: GenIotOpcoes = { ...(PRESETS_IOT[lab] ?? {}), ...(opcoes ?? {}) };
    const flags = montarFlags(o);
    const conflito = o.semSenha && (o.protegerHttp || o.mqttSemAnonimo);
    const labValido = /^[a-z][a-z0-9]{1,20}$/.test(lab);

    const porta = o.portaHttp ?? 80;
    const base = `http://localhost${porta === 80 ? "" : `:${porta}`}`;
    const pastaMae = `%USERPROFILE%\\${HOMEFOLDER}`;
    const gitea = !o.semGitea;
    // as variáveis do cmd (%IOT_...%) são expandidas ao ler a linha: o "set" fica em linhas
    // próprias (passo 0) e nunca encadeado com && no mesmo comando que as usa

    return (
        <>
            <Admonition type="info" title="Antes de começar">
                <p>
                    Precisa do <b>Docker Desktop</b> aberto (com pelo menos 4 GB de memória
                    {gitea && !o.semRunner ? "; 6 GB com o CI" : ""}) e do <b>Python 3</b>.
                    Os comandos são para o <b>Prompt de Comando</b> (cmd) do Windows.
                </p>
                <p>
                    Configuração do <code>{lab}</code>:{" "}
                    {flags.length ? flags.map((f) => <code key={f} style={{ marginRight: 4 }}>{f}</code>) : "LAB IoT completo (sem opções)"}
                </p>
            </Admonition>

            {!labValido && (
                <Admonition type="danger" title="Nome de laboratório inválido">
                    <code>{labName}</code>: o <code>--lab</code> deve começar com letra e ter só letras/dígitos (ex.: lab05).
                </Admonition>
            )}
            {conflito && (
                <Admonition type="danger" title="Opções incompatíveis">
                    <code>--sem-senha</code> não combina com <code>--proteger-http</code> nem com{" "}
                    <code>--mqtt-sem-anonimo</code>: o script vai recusar.
                </Admonition>
            )}

            <Tabs>
                {/* P (professor) e N (notas) não são grupos de alunos: sem aba */}
                {grupos.filter((g) => !["p", "n"].includes(g.toLowerCase())).map((group) => {
                    const letra = group.toLowerCase();
                    const conta = `${lab}-${letra}`;
                    // repositório do grupo (mesmo nome do LabTeamMembers), já clonado na pasta-mãe
                    const repoName = `${labName}-grupo-${letra}`;
                    const repo = `${pastaMae}\\${repoName}`;
                    // atalhos (variáveis do cmd): IOT_GEN = gerador, IOT_DIR = pasta de saída (dentro do repo)
                    const atalhos = [
                        `set "IOT_REPO=${repo}"`,
                        `set "IOT_GEN=%IOT_REPO%\\docker\\gen_iot_aluno.py"`,
                        `set "IOT_DIR=%IOT_REPO%\\docker\\${conta}"`,
                    ].join("\n");
                    const entrar = `cd /d "%IOT_DIR%"`;
                    const gerar = [`py "%IOT_GEN%"`, `--lab ${lab}`, `--grupo ${letra}`, ...flags, `--saida "%IOT_DIR%"`].join(" ");
                    const commit = `${entrar} && git add . && git commit -m "T0: Hello Docker!" && git push`;
                    const valido = GRUPO_VALIDO.test(letra) && letra !== "p" && letra !== "n";

                    const servicos: [string, string][] = [
                        ["Portal", `${base}/`],
                        ["Node-RED", `${base}/${conta}/`],
                        ["Dashboard", `${base}/${conta}/dashboard`],
                    ];
                    if (!o.semFuxa) servicos.push(["FUXA", `${base}/fuxa/${conta}/`]);
                    if (gitea) servicos.push(["Gitea", `${base}/git/`]);
                    if (!o.semNtfy) servicos.push(["Avisos (ntfy)", `${base}/avisos/`]);
                    if (!o.semMicrobin) servicos.push(["MicroBin", `${base}/bin/`]);
                    if (!o.semMqttExplorer) servicos.push(["MQTT Explorer", "http://localhost:3001/"]);

                    return (
                        <TabItem key={group} value={letra} label={group}>
                            {!valido ? (
                                <Admonition type="danger" title="Grupo inválido">
                                    O <code>gen_iot_aluno.py</code> aceita só uma letra de <code>a</code> a{" "}
                                    <code>z</code> (sem <code>p</code> e <code>n</code>); <code>{group}</code> não serve.
                                </Admonition>
                            ) : (
                                <>
                                    <ul>
                                        <li>
                                            <b>Conta:</b> <code>{conta}</code> (usuário, tópicos MQTT <code>{conta}/#</code>)
                                        </li>
                                        <li>
                                            <b>Gerador (<code>%IOT_GEN%</code>):</b>{" "}
                                            <code>{`${repo}\\docker\\gen_iot_aluno.py`}</code>
                                        </li>
                                        <li>
                                            <b>Pasta do LAB IoT (<code>%IOT_DIR%</code>):</b>{" "}
                                            <code>{`${repo}\\docker\\${conta}`}</code>
                                        </li>
                                    </ul>

                                    <p>
                                        <b>0.</b> Crie os atalhos (valem só nesta janela do cmd; abriu outra, rode de novo):
                                    </p>
                                    <Cmd>{atalhos}</Cmd>

                                    <p>
                                        <b>1.</b> Atualize o repositório <code>{repoName}</code> (já clonado), que traz o gerador:
                                    </p>
                                    <Cmd>{`git -C "%IOT_REPO%" pull`}</Cmd>

                                    <p><b>2.</b> Instale a dependência do gerador (uma vez):</p>
                                    <Cmd>{`py -m pip install bcrypt`}</Cmd>

                                    <p><b>3.</b> Gere o LAB IoT do grupo em <code>{`docker\\${conta}`}</code>:</p>
                                    <Cmd>{gerar}</Cmd>

                                    <p><b>4.</b> Suba os containers (a primeira vez demora):</p>
                                    <Cmd>{`${entrar} && docker compose up -d --build`}</Cmd>

                                    <p><b>5.</b> Confira e veja a senha:</p>
                                    <Cmd>{`docker compose ps && type credenciais.txt`}</Cmd>

                                    <p><b>6.</b> Abra o portal:</p>
                                    <Cmd>{`start ${base}/`}</Cmd>

                                    <p><b>7.</b> Registre a pasta do LAB IoT no repositório:</p>
                                    <Cmd>{commit}</Cmd>

                                    <details>
                                        <summary><b>Endereços</b></summary>
                                        <ul>
                                            {servicos.map(([nome, url]) => (
                                                <li key={nome}>
                                                    <b>{nome}:</b>{" "}
                                                    <a href={url} target="_blank" rel="noopener noreferrer">{url}</a>
                                                </li>
                                            ))}
                                            <li>
                                                <b>MQTT (ESP32 na mesma rede):</b> <code>&lt;IP-da-máquina&gt;:1883</code>
                                            </li>
                                        </ul>
                                    </details>

                                    <details>
                                        <summary><b>Operações com Docker</b></summary>

                                        <p>Subir de novo (depois de reiniciar o PC ou de um <code>down</code>):</p>
                                        <Cmd>{`${entrar} && docker compose up -d`}</Cmd>

                                        <p>Parar (os dados ficam):</p>
                                        <Cmd>{`${entrar} && docker compose down`}</Cmd>

                                        <p>Reiniciar tudo:</p>
                                        <Cmd>{`${entrar} && docker compose restart`}</Cmd>

                                        <p>Ver erros do Node-RED (Ctrl+C para sair):</p>
                                        <Cmd>{`${entrar} && docker compose logs -f ${conta}-nodered`}</Cmd>

                                        <p>Mudou alguma opção? Gere de novo na mesma pasta e recrie:</p>
                                        <Cmd>{`${gerar} && ${entrar} && docker compose up -d --build --remove-orphans`}</Cmd>

                                        <p>Atualizar as imagens:</p>
                                        <Cmd>{`${entrar} && docker compose pull && docker compose build --pull && docker compose up -d`}</Cmd>

                                        {gitea && (
                                            <>
                                                <p>Refazer usuário, organização e secrets do Gitea:</p>
                                                <Cmd>{`${entrar} && docker compose run --rm gitea-init`}</Cmd>
                                            </>
                                        )}

                                        {o.captura && (
                                            <>
                                                <p>Wireshark ao vivo (só MQTT):</p>
                                                <Cmd>{`${entrar} && wireshark-ao-vivo.cmd port 1883`}</Cmd>
                                            </>
                                        )}

                                        <Admonition type="warning" title="Apagar tudo">
                                            <p>
                                                Remove containers <b>e volumes</b> (Gitea, ntfy, MicroBin, MQTT). Os fluxos em{" "}
                                                <code>data/</code> e as telas em <code>fuxa/</code> ficam na pasta.
                                            </p>
                                            <Cmd>{`${entrar} && docker compose down -v`}</Cmd>
                                        </Admonition>
                                    </details>
                                </>
                            )}
                        </TabItem>
                    );
                })}
            </Tabs>
        </>
    );
}
