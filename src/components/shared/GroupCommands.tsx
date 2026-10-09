import React from "react";
import Tabs from "@theme/Tabs";
import TabItem from "@theme/TabItem";
import ThemeCodeBlock from "@theme/CodeBlock";

import { GROUPS, COURSE } from "../constants"; // imported GROUPS and COURSE

export type CommandItem = {
    /** Title or description appearing above the code block */
    title?: string;
    /** Title displayed directly on top of the code block box */
    codeTitle?: string;
    /** Raw command string containing {GROUP}, {group}, {COURSE}, or {course} */
    command: string;
};

type GroupCommandsProps = {
    /** Pass a single command string OR an array of command objects/strings */
    commands: string | (string | CommandItem)[];
    /** Language for syntax highlighting (default: "bash") */
    language?: string;
};

export default function GroupCommands({
    commands,
    language = "bash",
}: GroupCommandsProps) {
    // Normalize input to an array of CommandItem
    const commandList: CommandItem[] = Array.isArray(commands)
        ? commands.map((item) => (typeof item === "string" ? { command: item } : item))
        : [{ command: commands }];

    const courseUpper = (COURSE || "").toUpperCase();
    const courseLower = (COURSE || "").toLowerCase();

    // Helper function to replace all supported placeholders in any text field
    const formatText = (text?: string, group: string = "", groupLower: string = "") => {
        if (!text) return "";
        return text
            .replace(/\{GROUP\}/g, group)
            .replace(/\{group\}/g, groupLower)
            .replace(/\{COURSE\}/g, courseUpper)
            .replace(/\{course\}/g, courseLower);
    };

    return (
        <Tabs>
            {GROUPS.map((group) => {
                const groupLower = group.toLowerCase();

                return (
                    <TabItem key={group} value={groupLower} label={group}>
                        {commandList.map((item, index) => {
                            const processedTitle = formatText(item.title, group, groupLower);
                            const processedCodeTitle = formatText(item.codeTitle, group, groupLower);
                            const processedCommand = formatText(item.command, group, groupLower);

                            return (
                                <div key={index} style={{ marginBottom: "1rem" }}>
                                    {processedTitle && (
                                        <p style={{ marginBottom: "0.5rem" }}>
                                            <b>{index + 1}. {processedTitle}:</b>
                                        </p>
                                    )}
                                    <ThemeCodeBlock
                                        className={`language-${language}`}
                                        title={processedCodeTitle}
                                    >
                                        {processedCommand}
                                    </ThemeCodeBlock>
                                </div>
                            );
                        })}
                    </TabItem>
                );
            })}
        </Tabs>
    );
}
