import React from "react";
import Tabs from "@theme/Tabs";
import TabItem from "@theme/TabItem";
import ThemeCodeBlock from "@theme/CodeBlock";
import Admonition from "@theme/Admonition";


import { GROUPS, ORG, HOMEFOLDER } from "../constants"; // one folder up

type LabTeamMembersProps = {
    /** Nome do laboratório, ex: "lab00", "lab05", "projeto" */
    labName?: string;
    /** Perfil do VS Code, ex: "ESP32IO" */
    vscodeProfile?: string;
};

export default function LabTeamMembers({
    labName = "lab00",
    vscodeProfile = "ESP32IO",
}: LabTeamMembersProps) {
    return (
        <Tabs>
            {GROUPS.map((group) => {
                const groupLower = group.toLowerCase();
                const repoName = `${labName}-grupo-${groupLower}`;
                const fullRepo = `${ORG}/${repoName}`;
                const repoUrl = `https://github.com/${fullRepo}`;
                const teamsUrl = `https://github.com/orgs/${ORG}/teams/grupo-${groupLower}`;
                const CommitsUrl = `https://github.com/${fullRepo}/commits/main/`;
                const teamSlug = `grupo-${groupLower}`;

                return (
                    <TabItem key={group} value={groupLower} label={group}>
                        <ul>
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
                                <b>Commits:</b>{" "}
                                <a href={CommitsUrl} target="_blank" rel="noopener noreferrer">
                                    {CommitsUrl}
                                </a>
                            </li>
                            <li>
                                <b>Time:</b>{" "}
                                <a href={teamsUrl} target="_blank" rel="noopener noreferrer">
                                    {teamsUrl}
                                </a>
                            </li>
                        </ul>
                        <p>
                            <b>1.</b> Crie e entre na pasta-mãe da disciplina:
                        </p>
                        <ThemeCodeBlock className="language-bash">
                            {`mkdir "%USERPROFILE%\\${HOMEFOLDER}" & cd /d "%USERPROFILE%\\${HOMEFOLDER}"`}
                        </ThemeCodeBlock>
                        <p>
                            <b>2.</b> Clone e entre no repositório do laboratório:
                        </p>
                        <ThemeCodeBlock className="language-bash">
                            {`git clone ${repoUrl}.git && cd ${repoName}`}
                        </ThemeCodeBlock>
                        <p>
                            <b>3.</b> Verifique status e abra o conteúdo do repositório no perfil {`${vscodeProfile}`} do VS Code :
                        </p>
                        <ThemeCodeBlock className="language-bash">
                            {`git status && code . --profile "${vscodeProfile}"`}
                        </ThemeCodeBlock>
                    </TabItem>
                );
            })}
        </Tabs>
    );
}
