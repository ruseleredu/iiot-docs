import React from "react";
import ThemeCodeBlock from "@theme/CodeBlock";
import Admonition from "@theme/Admonition";

import { GROUPS, ORG } from "../constants"; // one folder up

/* ------------------------------------------------------------------ */
/* Opções do gen_iot_scada_portal.py (servidor do laboratório)          */
/* ------------------------------------------------------------------ */

const PUBLICO_URL_PADRAO = "https://iot.adrianoruseler.com";
const SCRIPT = "gen_iot_scada_portal.py";

/** Opções do gen_iot_scada_portal.py (cada uma vira um argumento de linha de comando). */
export type ScadaOpcoes = {
    /** --sem-tunel: só rede local (http://IP/), sem VPS */
    semTunel?: boolean;
    /** --publico-url (padrão https://iot.adrianoruseler.com) */
    publicoUrl?: string;
    /** --vps-host (padrão: host da publicoUrl) */
    vpsHost?: string;
    /** Usuário SSH de administração do VPS (só nos comandos de instalação; padrão "ubuntu") */
    vpsAdmin?: string;
    /** --sem-gitea: sem Gitea e sem CI */
    semGitea?: boolean;
    /** --sem-runner: Gitea sem Actions */
    semRunner?: boolean;
    /** --gitea-db sqlite (padrão postgres) */
    giteaDb?: "postgres" | "sqlite";
    /** --gitea-repo <nome> (padrão "nodered"; "" = nenhum) */
    giteaRepo?: string;
    /** --runner-capacidade <n> (padrão 2) */
    runnerCapacidade?: number;
    /** --runner-dns IP[,IP] (DNS da instituição, se o 53 externo for bloqueado) */
    runnerDns?: string;
    /** --sem-microbin */
    semMicrobin?: boolean;
    /** --sem-fuxa */
    semFuxa?: boolean;
    /** --sem-ntfy */
    semNtfy?: boolean;
    /** --proteger-http: login nos dashboards e endpoints HTTP */
    protegerHttp?: boolean;
    /** --mqtt-sem-anonimo: MQTT exige usuário/senha */
    mqttSemAnonimo?: boolean;
    /** --mqtt-explorer-auth */
    mqttExplorerAuth?: boolean;
    /** Argumentos extras, passados como estão */
    extras?: string[];
};

/**
 * Pré-configuração por laboratório (mesmas ideias do PRESETS_IOT do aluno).
 * A página pode sobrescrever qualquer opção com a prop `opcoes`.
 */
export const PRESETS_SCADA: Record<string, ScadaOpcoes> = {
    lab05: {}, // LAB IoT completo
    lab06: { semGitea: true, semMicrobin: true },
    lab07: { semGitea: true, semMicrobin: true, semFuxa: true, semNtfy: true },
    lab08: {},
    projeto: {},
};

function montarFlags(o: ScadaOpcoes): string[] {
    const f: string[] = [];
    if (o.semTunel) {
        f.push("--sem-tunel");
    } else {
        if (o.publicoUrl && o.publicoUrl !== PUBLICO_URL_PADRAO) f.push(`--publico-url ${o.publicoUrl}`);
        if (o.vpsHost) f.push(`--vps-host ${o.vpsHost}`);
    }
    if (o.semGitea) {
        f.push("--sem-gitea");
    } else {
        if (o.giteaDb === "sqlite") f.push("--gitea-db sqlite");
        if (o.giteaRepo !== undefined && o.giteaRepo !== "nodered") f.push(`--gitea-repo "${o.giteaRepo}"`);
        if (o.semRunner) f.push("--sem-runner");
        else {
            if (o.runnerCapacidade && o.runnerCapacidade !== 2) f.push(`--runner-capacidade ${o.runnerCapacidade}`);
            if (o.runnerDns) f.push(`--runner-dns ${o.runnerDns}`);
        }
    }
    if (o.semMicrobin) f.push("--sem-microbin");
    if (o.semFuxa) f.push("--sem-fuxa");
    if (o.semNtfy) f.push("--sem-ntfy");
    if (o.protegerHttp) f.push("--proteger-http");
    if (o.mqttSemAnonimo) f.push("--mqtt-sem-anonimo");
    if (o.mqttExplorerAuth) f.push("--mqtt-explorer-auth");
    if (o.extras) f.push(...o.extras);
    return f;
}

/**
 * Letras dos grupos de alunos: GROUPS sem 'P' (professor) e 'N' (notas).
 * O gerador recebe só a quantidade (--grupos) e distribui a, b, c... pulando p e n,
 * então GROUPS deve seguir essa mesma ordem.
 */
const LETRAS_ALUNOS = GROUPS.map((g) => g.toLowerCase()).filter((c) => c !== "p" && c !== "n");

/* ------------------------------------------------------------------ */
/* Componente                                                           */
/* ------------------------------------------------------------------ */

type LabIotProfessorProps = {
    /** Nome do laboratório, ex: "lab05", "lab07" */
    labName?: string;
    /** IP do servidor na rede do laboratório (se omitido, o professor edita o atalho IOT_IP) */
    ip?: string;
    /** Sobrescreve/complementa o preset do laboratório */
    opcoes?: ScadaOpcoes;
};

function Cmd({ children }: { children: string }) {
    return <ThemeCodeBlock className="language-bash">{children}</ThemeCodeBlock>;
}

export default function LabIotProfessor({
    labName = "lab05",
    ip,
    opcoes,
}: LabIotProfessorProps) {
    const githubOrg = ORG;
    const letras = LETRAS_ALUNOS;
    const grupos = letras.length; // GROUPS menos P e N
    const lab = labName.toLowerCase();
    const o: ScadaOpcoes = { ...(PRESETS_SCADA[lab] ?? {}), ...(opcoes ?? {}) };
    const flags = montarFlags(o);
    const labValido = /^[a-z][a-z0-9]{1,20}$/.test(lab);
    const nValido = grupos >= 1 && grupos <= 24;
    // o gerador usa a, b, c... (sem p e n): GROUPS precisa coincidir, senão as contas não batem
    const esperado = "abcdefghijklmoqrstuvwxyz".slice(0, grupos);
    const ordemValida = letras.join("") === esperado;

    const tunel = !o.semTunel;
    const gitea = !o.semGitea;
    const runner = gitea && !o.semRunner;
    const publico = (o.publicoUrl ?? PUBLICO_URL_PADRAO).replace(/\/$/, "");
    const vpsHost = o.vpsHost ?? new URL(publico).hostname;
    const vpsAdmin = `${o.vpsAdmin ?? "ubuntu"}@${vpsHost}`;
    const ipLocal = ip ?? "<IP-do-servidor>";
    const prof = `${lab}-p`;
    const notas = `${lab}-n`;

    // atalhos do cmd: o prompt já está na pasta do gerador (%CD%)
    // (cada "set" em linha própria: o cmd expande %VAR% ao ler a linha inteira)
    const atalhos = [
        `set "IOT_GEN=%CD%\\${SCRIPT}"`,
        `set "IOT_DIR=%CD%\\${lab}"`,
        `set "IOT_IP=${ipLocal}"`,
    ].join("\n");
    const entrar = `cd /d "%IOT_DIR%"`;
    const gerarArgs = [`--lab ${lab}`, `--grupos ${grupos}`, `--ip %IOT_IP%`, `--github-org ${githubOrg}`, ...flags];
    // --saida: gera sempre na mesma pasta, de qualquer diretório
    const gerar = [`py "%IOT_GEN%"`, ...gerarArgs, `--saida "%IOT_DIR%"`].join(" ");
    const gitBash = `"%ProgramFiles%\\Git\\bin\\bash.exe"`;

    // rede do laboratório: endereço público (o mesmo dentro e fora do laboratório)
    const baseLocal = PUBLICO_URL_PADRAO;
    const linhaGrupo = (conta: string, papel: string) => (
        <tr key={conta}>
            <td><code>{conta}</code></td>
            <td>{papel}</td>
            <td><code>{`/${conta}/`}</code></td>
            <td>{o.semFuxa || conta === notas ? "—" : <code>{`/fuxa/${conta}/`}</code>}</td>
            <td>{gitea && papel === "grupo" ? <code>{`${lab}-grupo-${conta.slice(-1)}`}</code> : "—"}</td>
        </tr>
    );

    return (
        <>
            <Admonition type="info" title="Servidor do laboratório (uso do professor)">
                <p>
                    Um único ambiente para a turma: {grupos} grupos (<code>{`${lab}-${letras[0]}`}</code> a{" "}
                    <code>{`${lab}-${letras[letras.length - 1]}`}</code>), professor (<code>{prof}</code>) e
                    painel de notas (<code>{notas}</code>). Comandos para o <b>Prompt de Comando</b> (cmd),
                    aberto na pasta onde está o <code>{SCRIPT}</code>.
                </p>
                <p>
                    Configuração do <code>{lab}</code>:{" "}
                    {flags.length
                        ? flags.map((f) => <code key={f} style={{ marginRight: 4 }}>{f}</code>)
                        : "LAB IoT completo, com túnel para o VPS"}
                </p>
            </Admonition>

            {!labValido && (
                <Admonition type="danger" title="Nome de laboratório inválido">
                    <code>{labName}</code>: o <code>--lab</code> deve começar com letra e ter só letras/dígitos (ex.: lab05).
                </Admonition>
            )}
            {!nValido && (
                <Admonition type="danger" title="Quantidade de grupos inválida">
                    <code>--grupos {grupos}</code>: GROUPS precisa ter de 1 a 24 grupos de alunos, além de P e N.
                </Admonition>
            )}
            {nValido && !ordemValida && (
                <Admonition type="danger" title="GROUPS fora da ordem do gerador">
                    O gerador cria as contas <code>{esperado.split("").join(", ")}</code>, mas GROUPS (sem P e N) tem{" "}
                    <code>{letras.join(", ")}</code>. Ajuste GROUPS em <code>constants</code>.
                </Admonition>
            )}

            <p><b>0.</b> Crie os atalhos (valem só nesta janela do cmd; abriu outra, volte à pasta do gerador e rode de novo):</p>
            <Cmd>{atalhos}</Cmd>
            {!ip && (
                <Admonition type="warning" title="IP do servidor">
                    Troque <code>&lt;IP-do-servidor&gt;</code> pelo IPv4 da placa de rede do laboratório
                    (veja com <code>ipconfig</code>). Com <code>127.x</code>, os alunos não alcançam o servidor.
                </Admonition>
            )}

            <p><b>1.</b> Instale a dependência do gerador (uma vez):</p>
            <Cmd>{`py -m pip install bcrypt`}</Cmd>

            <p><b>2.</b> Gere o LAB IoT da turma (pasta <code>{lab}</code>, ao lado do gerador):</p>
            <Cmd>{gerar}</Cmd>

            {tunel && (
                <>
                    <p>
                        <b>3.</b> Túnel para o VPS (<b>uma vez</b>): gere a chave, envie os arquivos e configure o Apache
                        de <code>{vpsHost}</code>:
                    </p>
                    <Cmd>{[
                        `${entrar} && docker compose run --rm --no-deps --build tunel chave`,
                        `ssh ${vpsAdmin} mkdir -p iot-lab`,
                        `scp -r vps tunel/chave/id_ed25519.pub ${vpsAdmin}:iot-lab/`,
                        `ssh -t ${vpsAdmin} sudo bash iot-lab/vps/setup-vps.sh iot-lab/id_ed25519.pub`,
                    ].join("\n")}</Cmd>
                </>
            )}

            <p><b>{tunel ? 4 : 3}.</b> Suba os containers (a primeira vez demora):</p>
            <Cmd>{`${entrar} && docker compose up -d --build`}</Cmd>

            <p><b>{tunel ? 5 : 4}.</b> Confira e veja as senhas de todos:</p>
            <Cmd>{`${entrar} && docker compose ps && type credenciais.txt`}</Cmd>

            <p><b>{tunel ? 6 : 5}.</b> Abra o portal:</p>
            <Cmd>{`start ${baseLocal}/`}</Cmd>

            <p>
                <b>{tunel ? 7 : 6}.</b> Publique os acessos nos repositórios dos grupos (
                <code>{`${githubOrg}/${lab}-grupo-<letra>`}</code>, arquivo{" "}
                <code>{`ACESSO-${lab.toUpperCase()}.md`}</code>). Precisa do Git for Windows e do{" "}
                <code>gh</code> autenticado (<code>gh auth login</code>). Primeiro confira, depois publique:
            </p>
            <Cmd>{[
                `${entrar} && ${gitBash} publicar-acessos-github.sh --arquivo --dry-run`,
                `${gitBash} publicar-acessos-github.sh --arquivo`,
            ].join("\n")}</Cmd>

            <details>
                <summary><b>Endereços e contas</b></summary>
                <ul>
                    <li><b>Rede do laboratório:</b> <a href={`${baseLocal}/`} target="_blank" rel="noopener noreferrer">{`${baseLocal}/`}</a></li>
                    {gitea && <li><b>Gitea:</b> <code>{"<base>/git/"}</code>{runner ? " (Actions: runner do laboratório)" : ""}</li>}
                    {!o.semNtfy && <li><b>Avisos (ntfy):</b> <code>{"<base>/avisos/"}</code> · tópico da turma <code>{`${lab}-avisos`}</code></li>}
                    {!o.semMicrobin && <li><b>MicroBin:</b> <code>{"<base>/bin/"}</code></li>}
                    <li><b>MQTT Explorer:</b> <code>{`http://${ipLocal}:3001/`}</code> (só na rede do laboratório)</li>
                    <li><b>MQTT:</b> <code>{`${ipLocal}:1883`}</code> (só na rede do laboratório)</li>
                </ul>
                <table>
                    <thead>
                        <tr><th>Conta</th><th>Papel</th><th>Node-RED</th><th>FUXA</th><th>Organização Gitea</th></tr>
                    </thead>
                    <tbody>
                        {letras.map((l) => linhaGrupo(`${lab}-${l}`, "grupo"))}
                        {linhaGrupo(prof, "professor")}
                        {linhaGrupo(notas, "notas")}
                    </tbody>
                </table>
            </details>

            <details>
                <summary><b>Operações com Docker</b></summary>

                <p>Subir de novo (depois de reiniciar o servidor ou de um <code>down</code>):</p>
                <Cmd>{`${entrar} && docker compose up -d`}</Cmd>

                <p>Parar (os dados ficam):</p>
                <Cmd>{`${entrar} && docker compose down`}</Cmd>

                <p>Reiniciar o Node-RED de um grupo (ex.: <code>{`${lab}-${letras[0]}`}</code>):</p>
                <Cmd>{`${entrar} && docker compose restart ${lab}-${letras[0]}-nodered`}</Cmd>

                <p>Ver erros do Node-RED de um grupo (Ctrl+C para sair):</p>
                <Cmd>{`${entrar} && docker compose logs -f ${lab}-${letras[0]}-nodered`}</Cmd>

                {tunel && (
                    <>
                        <p>Ver o túnel para o VPS:</p>
                        <Cmd>{`${entrar} && docker compose logs -f tunel`}</Cmd>
                    </>
                )}

                {runner && (
                    <>
                        <p>Ver o runner do CI:</p>
                        <Cmd>{`${entrar} && docker compose logs -f gitea-runner`}</Cmd>
                    </>
                )}

                <p>Mudou alguma opção? Gere de novo (as senhas são mantidas) e recrie:</p>
                <Cmd>{`${gerar} && ${entrar} && docker compose up -d --build --remove-orphans`}</Cmd>

                {gitea && (
                    <>
                        <p>Refazer usuários, organizações e secrets do Gitea:</p>
                        <Cmd>{`${entrar} && docker compose run --rm gitea-init`}</Cmd>
                    </>
                )}

                {runner && (
                    <>
                        <p>
                            Token do Wokwi CI (vira o secret <code>WOKWI_CLI_TOKEN</code> de cada organização e fica
                            guardado no <code>.segredos.json</code>):
                        </p>
                        <Cmd>{`${gerar} --wokwi-token SEU_TOKEN && ${entrar} && docker compose up -d && docker compose run --rm gitea-init`}</Cmd>
                    </>
                )}

                <p>Atualizar as imagens:</p>
                <Cmd>{`${entrar} && docker compose pull && docker compose build --pull && docker compose up -d`}</Cmd>

                <p>Retirar os acessos dos repositórios dos grupos (fim do semestre):</p>
                <Cmd>{`${entrar} && ${gitBash} publicar-acessos-github.sh --remover`}</Cmd>

                <Admonition type="warning" title="Senhas novas para todos">
                    <p>
                        Invalida as senhas atuais de todos os grupos: depois, publique os acessos de novo (passo{" "}
                        {tunel ? 7 : 6}).
                    </p>
                    <Cmd>{`${gerar} --novas-senhas && ${entrar} && docker compose up -d --build && docker compose run --rm gitea-init`}</Cmd>
                </Admonition>

                <Admonition type="danger" title="Apagar tudo">
                    <p>
                        Remove containers <b>e volumes</b> (Gitea, PostgreSQL, ntfy, MicroBin, MQTT) de toda a turma.
                        Os fluxos em <code>data/</code> e as telas em <code>fuxa/</code> ficam na pasta.
                    </p>
                    <Cmd>{`${entrar} && docker compose down -v`}</Cmd>
                </Admonition>
            </details>
        </>
    );
}
