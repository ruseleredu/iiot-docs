import React from "react";
import Tabs from "@theme/Tabs";
import TabItem from "@theme/TabItem";
import ThemeCodeBlock from "@theme/CodeBlock";
import Admonition from "@theme/Admonition";


import { GROUPS, ORG } from "../constants"; // one folder up

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
                const reposUrl = `https://github.com/orgs/${ORG}/teams/grupo-${groupLower}/repositories`;
                const teamSlug = `grupo-${groupLower}`;

                return (
                    <TabItem key={group} value={groupLower} label={group}>
                        <ul>
                            <li>
                                <b>Organização:</b>{" "}
                                <a href={`https://github.com/${ORG}`} target="_blank" rel="noopener noreferrer">
                                    {ORG}
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
                            {`git clone ${repoUrl}.git`}
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
                    </TabItem>
                );
            })}
        </Tabs>
    );
}
