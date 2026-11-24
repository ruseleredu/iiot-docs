import React from "react";
import Tabs from "@theme/Tabs";
import TabItem from "@theme/TabItem";
import ThemeCodeBlock from "@theme/CodeBlock";

import { GROUPS, ORG, HOMEFOLDER } from "../constants"; // one folder up

type PjtTeamMembersProps = {
    /** Prefixo dos repositórios do projeto final, ex: "projeto" */
    pjtName?: string;
    /** Perfil do VS Code, ex: "ESP32IO" */
    vscodeProfile?: string;
};

export default function PjtTeamMembers({
    pjtName = "projeto",
    vscodeProfile = "ESP32IO",
}: PjtTeamMembersProps) {
    const pjtNameUpper = pjtName.toUpperCase();

    return (
        <Tabs groupId="grupo" queryString="grupo">
            {GROUPS.map((group) => {
                const groupLower = group.toLowerCase();
                const repoName = `${pjtName}-grupo-${groupLower}`;
                const fullRepo = `${ORG}/${repoName}`;
                const repoUrl = `https://github.com/${fullRepo}`;
                const teamsUrl = `https://github.com/orgs/${ORG}/teams/grupo-${groupLower}`;
                const commitsUrl = `https://github.com/${fullRepo}/commits/main/`;
                const teamSlug = `grupo-${groupLower}`;
                const passUrl = `${repoUrl}/blob/main/ACESSO-${pjtNameUpper}.md`;

                return (
                    <TabItem key={group} value={group} label={group}>
                        <ul>
                            <li>
                                <b>Grupo:</b>{" "}
                                <a href={teamsUrl} target="_blank" rel="noopener noreferrer">
                                    Grupo-{group} (slug: <code>{teamSlug}</code>)
                                </a>
                            </li>
                            <li>
                                <b>Repositório:</b>{" "}
                                <a href={repoUrl} target="_blank" rel="noopener noreferrer">
                                    {repoUrl}
                                </a>
                            </li>
                            <li>
                                <b>Commits:</b>{" "}
                                <a href={commitsUrl} target="_blank" rel="noopener noreferrer">
                                    {commitsUrl}
                                </a>
                            </li>
                            <li>
                                <b>Acessos:</b>{" "}
                                <a href={passUrl} target="_blank" rel="noopener noreferrer">
                                    {`ACESSO-${pjtNameUpper}.md`}
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
                            <b>2.</b> Clone e entre no repositório do projeto final:
                        </p>
                        <ThemeCodeBlock className="language-bash">
                            {`git clone ${repoUrl}.git && cd ${repoName}`}
                        </ThemeCodeBlock>
                        <p>
                            <b>3.</b> Abra o conteúdo do repositório no perfil {vscodeProfile} do VS Code e compile:
                        </p>
                        <ThemeCodeBlock className="language-bash">
                            {`cd /d "%USERPROFILE%\\${HOMEFOLDER}\\${repoName}" && code . --profile "${vscodeProfile}"`}
                        </ThemeCodeBlock>
                    </TabItem>
                );
            })}
        </Tabs>
    );
}
