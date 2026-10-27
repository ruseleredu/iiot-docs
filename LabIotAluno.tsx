import React from "react";
import Tabs from "@theme/Tabs";
import TabItem from "@theme/TabItem";
import ThemeCodeBlock from "@theme/CodeBlock";
import Admonition from "@theme/Admonition";

import { GROUPS, HOMEFOLDER, PRESETS_IOT, GenIotOpcoes } from "../constants"; // updated import

/* ------------------------------------------------------------------ */
/* Opções do gen_iot_aluno.py                                           */
/* ------------------------------------------------------------------ */

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
                <Cmd>{`docker desktop start`}</Cmd>
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

                    // limpeza: o estado do Node-RED fica todo em data\<conta> (montado em /data);
                    // settings\<conta>.js e .segredos.json ficam fora, então senha e login não mudam.
                    // Nos comandos com "del"/"rmdir ... 2>nul" o "&" (dentro de parênteses) segue
                    // mesmo se o arquivo não existir, sem rodar nada fora da pasta se o "cd" falhar.
                    const nr = `${conta}-nodered`;
                    const dataNr = `data\\${conta}`;
                    const pararNr = `${entrar} && docker compose stop ${nr}`;
                    const limparFluxos =
                        `${pararNr} && (del /q "${dataNr}\\flows.json" "${dataNr}\\flows_cred.json" ` +
                        `"${dataNr}\\.flows*.backup" 2>nul & docker compose start ${nr})`;
                    const limparPaleta =
                        `${pararNr} && (rmdir /s /q "${dataNr}\\node_modules" 2>nul & ` +
                        `del /q "${dataNr}\\package.json" "${dataNr}\\package-lock.json" "${dataNr}\\.config.nodes.json" 2>nul & ` +
                        `docker compose start ${nr})`;
                    const limparNr = `${pararNr} && rmdir /s /q "${dataNr}" && ${gerar} && ${entrar} && docker compose up -d ${nr}`;
                    const voltarCommit =
                        `${pararNr} && git checkout -- "${dataNr}" && git clean -fdq "${dataNr}" && docker compose start ${nr}`;
                    const guardarLimpo = `${pararNr} && tar -a -cf nodered-limpo.zip "${dataNr}" && docker compose start ${nr}`;
                    const restaurarLimpo = `${pararNr} && rmdir /s /q "${dataNr}" && tar -xf nodered-limpo.zip && docker compose start ${nr}`;
                    const fuxaNr = `${conta}-fuxa`;
                    const limparFuxa =
                        `${entrar} && docker compose stop ${fuxaNr} && rmdir /s /q "fuxa\\${conta}" && ${gerar} && ` +
                        `${entrar} && docker compose up -d ${fuxaNr}`;
                    const zerarParar = `${entrar} && docker compose down -v --remove-orphans && (rmdir /s /q data & rmdir /s /q fuxa) 2>nul`;
                    const zerarSubir = `${gerar} && ${entrar} && docker compose up -d --build`;

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
                                        <b>1.</b> Crie os atalhos (valem só nesta janela do cmd; abriu outra, rode de novo):
                                    </p>
                                    <Cmd>{atalhos}</Cmd>


                                    <p><b>2.</b> Gere o LAB IoT do grupo em <code>{`docker\\${conta}`}</code>:</p>
                                    <Cmd>{gerar}</Cmd>

                                    <p><b>3.</b> Suba os containers (a primeira vez demora):</p>
                                    <Cmd>{`${entrar} && docker compose up -d --build`}</Cmd>

                                    <p><b>4.</b> Confira e veja a senha:</p>
                                    <Cmd>{`docker compose ps && type credenciais.txt`}</Cmd>

                                    <p><b>5.</b> Abra o portal:</p>
                                    <Cmd>{`start ${base}/`}</Cmd>

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

                                        <p>
                                            Mudou alguma opção? Gere de novo na mesma pasta e recrie (o Node-RED e o
                                            MQTT só leem login e senhas ao iniciar, por isso o <code>restart</code>):
                                        </p>
                                        <Cmd>{`${gerar} && ${entrar} && docker compose up -d --build --remove-orphans && docker compose restart ${conta}-nodered mosquitto`}</Cmd>

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
                                            <p>
                                                Para limpar também os fluxos e as telas, veja <b>Limpar (voltar ao original)</b>.
                                            </p>
                                        </Admonition>
                                    </details>

                                    <details>
                                        <summary><b>Limpar (voltar ao original)</b></summary>

                                        <p>
                                            Tudo o que se faz no Node-RED (fluxos, credenciais dos nós, nós instalados pela
                                            paleta, bancos sqlite, projetos) fica em <code>{`docker\\${conta}\\${dataNr}`}</code>.
                                            O login e a senha ficam fora dela e <b>não mudam</b> com a limpeza.
                                            Os nós que já vêm na imagem (dashboard, modbus, opcua...) continuam lá.
                                        </p>

                                        <p><b>Node-RED inteiro</b> (como recém-gerado): apaga a pasta e o gerador a recria.</p>
                                        <Cmd>{limparNr}</Cmd>

                                        <p><b>Só os fluxos</b> (mantém os nós instalados e os bancos):</p>
                                        <Cmd>{limparFluxos}</Cmd>

                                        <p><b>Só os nós instalados pela paleta</b> (<i>Manage palette</i>):</p>
                                        <Cmd>{limparPaleta}</Cmd>

                                        <p>
                                            <b>Voltar ao último commit</b> (ex.: o <code>T0</code> do passo 7): desfaz o que mudou
                                            em <code>{dataNr}</code> desde então.
                                        </p>
                                        <Cmd>{voltarCommit}</Cmd>

                                        <p>
                                            <b>Guardar um ponto de partida</b> e voltar a ele quando quiser
                                            (o <code>nodered-limpo.zip</code> fica na pasta do LAB IoT):
                                        </p>
                                        <Cmd>{guardarLimpo}</Cmd>
                                        <p>Restaurar:</p>
                                        <Cmd>{restaurarLimpo}</Cmd>

                                        {!o.semFuxa && (
                                            <>
                                                <p><b>FUXA</b> (telas e conexões; o login do grupo é recriado pelo gerador):</p>
                                                <Cmd>{limparFuxa}</Cmd>
                                            </>
                                        )}

                                        <Admonition type="danger" title="Zerar o LAB IoT inteiro">
                                            <p>
                                                Apaga containers, volumes
                                                {gitea ? " (inclusive os repositórios do Gitea: faça push para outro lugar antes)" : ""},
                                                {" "}<code>data\</code> e <code>fuxa\</code>. O <code>.segredos.json</code> fica:
                                                a senha continua a mesma.
                                            </p>
                                            <Cmd>{zerarParar}</Cmd>
                                            <p>Gerar e subir de novo:</p>
                                            <Cmd>{zerarSubir}</Cmd>
                                        </Admonition>

                                        <p>
                                            Depois de limpar, o <code>git status</code> mostra os arquivos apagados: faça um commit
                                            (ex.: <code>git commit -am "limpeza"</code>) ou deixe como está.
                                        </p>
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
