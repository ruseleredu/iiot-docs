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
    const groups = ["A", "B", "C", "D", "E", "F", "G", "H", "I", "J", "K", "L", "M", "P"];
    const org = "ELT85B-N21-2026-2";

    return (
        <Tabs>
            {groups.map((group) => {
                const groupLower = group.toLowerCase();
                const repoName = `${labName}-grupo-${groupLower}`;
                const fullRepo = `${org}/${repoName}`;
                const repoUrl = `https://github.com/${fullRepo}`;
                const reposUrl = `https://github.com/orgs/${org}/teams/grupo-${groupLower}/repositories`;
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
                            <li>
                                <b>Repositórios:</b>{" "}
                                <a href={reposUrl} target="_blank" rel="noopener noreferrer">
                                    {reposUrl}
                                </a>
                            </li>
                        </ul>
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
                            <b>3.</b> Inicie o projeto no PlatformIO:
                        </p>
                        <ThemeCodeBlock className="language-bash">
                            {`pio project init -b esp32dev -O "framework=arduino" -O "monitor_speed=115200" --sample-code`}
                        </ThemeCodeBlock>
                        <p>
                            <b>4.</b> Fluxo diário de trabalho:
                        </p>
                        <ThemeCodeBlock className="language-bash">
                            {`git pull
git add .
git commit -m "Descreva suas alterações"
git push`}
                        </ThemeCodeBlock>

                        <p>
                            <b>5.</b> Abrir o repositório no navegador:
                        </p>
                        <ThemeCodeBlock className="language-bash">
                            {`gh repo view ${fullRepo} --web`}
                        </ThemeCodeBlock>
                    </TabItem>
                );
            })}
        </Tabs>
    );
}

