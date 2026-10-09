import React from 'react';
// Importa os componentes padrões do Docusaurus
import MDXComponents from '@theme-original/MDXComponents';
// Importa o seu componente customizado
import LabTable from "@site/src/components/shared/LabTable";
import QuizTable from "@site/src/components/shared/QuizTable";
import LabTeamMembers from "@site/src/components/shared/LabTeamMembers";
import LabSubmit from "@site/src/components/shared/LabSubmit";
import LabFromTemplate from "@site/src/components/LabFromTemplate";
import CommitPoint from "@site/src/components/shared/CommitPoint";
import FileTree from "@site/src/components/shared/FileTree";
import SimpleFileTree from "@site/src/components/shared/SimpleFileTree";
import GroupCommands from "@site/src/components/shared/GroupCommands";
import Tabs from "@theme/Tabs";
import TabItem from "@theme/TabItem";
import {
    LabSetup,
    LabLogout,
    DevTools,
} from "@site/src/components/shared/InstructionsSite";


export default {
    // Mantém os componentes padrão do MDX
    ...MDXComponents,
    // Registra o componente globalmente
    LabTable,
    QuizTable,
    LabTeamMembers,
    LabSubmit,
    LabFromTemplate,
    CommitPoint,
    FileTree,
    SimpleFileTree,
    Tabs,
    TabItem,
    LabSetup,
    LabLogout,
    DevTools,
    GroupCommands,
};
