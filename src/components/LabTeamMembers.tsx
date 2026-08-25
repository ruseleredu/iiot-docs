import React from "react";
import Tabs from "@theme/Tabs";
import TabItem from "@theme/TabItem";
import ThemeCodeBlock from "@theme/CodeBlock";
import Admonition from "@theme/Admonition";

type LabTeamMembersProps = {
    /** Nome do laboratório, ex: "lab00", "lab05", "projeto" */
    labName?: string;
    /** Perfil do VS Code, ex: "STM32" */
    vscodeProfile?: string;
};

export default function LabTeamMembers({
    labName = "lab00",
    vscodeProfile = "ESP32IO",
}: LabTeamMembersProps) {
    const groups = ["A", "B", "C", "D", "E", "F", "G", "H", "I", "J", "K", "L", "X"];
    const org = "ELT85B-N21-2026-2";

    return (
        <Tabs>
            {groups.map((group) => {
                const groupLower = group.toLowerCase();
                const repoName = `${labName}-grupo-${groupLower}`;
                const fullRepo = `${org}/${repoName}`;
                const repoUrl = `https://github.com/${fullRepo}`;
                const teamSlug = `grupo-${groupLower}`;

                return (
                    <TabItem key={group} value={groupLower} label={group}>
                        <ul>
                            <li>
                                <b>Organização:</b>{" "}
                                <a href={`https://github.com/${org}`} target="_blank" rel="noopener noreferrer">
                                    {org}
                                </a>
                            </li>
                            <li>
                                <b>Grupo:</b> Grupo-{group} (slug: <code>{teamSlug}</code>)
                            </li>
                            <li>
                                <b>Repositório:</b>{" "}
                                <a href={repoUrl} target="_blank" rel="noopener noreferrer">
                                    {repoUrl}
                                </a>
                            </li>
                        </ul>

                        <Admonition type="note" title="Configure o GitHub CLI (apenas na primeira vez)">
                            <ThemeCodeBlock className="language-bash">
                                {`gh auth login`}
                            </ThemeCodeBlock>
                            <ThemeCodeBlock className="language-bash">
                                {`git config --global user.name "Seu Nome"`}
                            </ThemeCodeBlock>
                            <ThemeCodeBlock className="language-bash">
                                {`git config --global user.email "seu@email.com"`}
                            </ThemeCodeBlock>
                        </Admonition>

                        <p>
                            <b>1.</b> Clone o repositório do laboratório:
                        </p>
                        <ThemeCodeBlock className="language-bash">
                            {`gh repo clone ${fullRepo}`}
                        </ThemeCodeBlock>
                        <ThemeCodeBlock className="language-bash">
                            {`cd ${repoName}`}
                        </ThemeCodeBlock>

                        <p>
                            <b>2.</b> Abra no VS Code:
                        </p>
                        <ThemeCodeBlock className="language-bash">
                            {`code . --profile "${vscodeProfile}"`}
                        </ThemeCodeBlock>

                        <p>
                            <b>3.</b> Fluxo diário de trabalho:
                        </p>
                        <ThemeCodeBlock className="language-bash">
                            {`git pull
git add .
git commit -m "Descreva suas alterações"
git push`}
                        </ThemeCodeBlock>

                        <p>
                            <b>4.</b> Abrir o repositório no navegador:
                        </p>
                        <ThemeCodeBlock className="language-bash">
                            {`gh repo view ${fullRepo} --web`}
                        </ThemeCodeBlock>


                        <Admonition type="tip" title="Branch + Pull Request (opcional)">
                            <ThemeCodeBlock className="language-bash">
                                {`git checkout -b feature/exercicio-1
git add . && git commit -m "Exercício 1" && git push -u origin feature/exercicio-1
gh pr create --title "Exercício 1" --body "Concluído"`}
                            </ThemeCodeBlock>
                        </Admonition>

                        <Admonition type="info" title="Regras de acesso">
                            <ul>
                                <li>
                                    Você pode fazer <b>push</b> apenas no repositório do seu grupo (
                                    <code>{repoName}</code>).
                                </li>
                                <li>Não é possível acessar ou alterar os repositórios dos outros grupos.</li>
                                <li>Em caso de erro de permissão, verifique com o professor se você está no time correto.</li>
                            </ul>
                        </Admonition>
                    </TabItem>
                );
            })}
        </Tabs>
    );
}

