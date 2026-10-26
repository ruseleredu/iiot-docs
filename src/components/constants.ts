
export const GROUPS = ['A', 'B', 'C', 'D', 'E', 'F', 'G', 'H', 'I', 'J', 'K', 'L', 'M', 'X', 'P', 'N'] as const;
export const ORG = 'ELT85B-N21-2026-2';
export const labgradehref = '/iiot-docs/labs/como-funciona-avaliacao';
export const courseid = '35058'; // Moodle course ID
export const HOMEFOLDER = 'ELT85BN21'; //  
export const COURSE = 'ELT85B'; // Course Name

/* ------------------------------------------------------------------ */
/* Opções do gen_iot_aluno.py                                           */
/* ------------------------------------------------------------------ */

export type GenIotOpcoes = {
    semGitea?: boolean;
    semRunner?: boolean;
    giteaDb?: "sqlite" | "postgres";
    giteaRepo?: string;
    semMicrobin?: boolean;
    semFuxa?: boolean;
    semNtfy?: boolean;
    semMqttExplorer?: boolean;
    semSenha?: boolean;
    protegerHttp?: boolean;
    mqttSemAnonimo?: boolean;
    portaHttp?: number;
    ponteMqtt?: string;
    captura?: boolean;
    capturaFiltro?: string;
    extras?: string[];
};

export const PRESETS_IOT: Record<string, GenIotOpcoes> = {
    lab05: {}, // LAB IoT completo
    lab06: { semGitea: true, semMicrobin: true },
    lab07: { semGitea: true, semMicrobin: true, semFuxa: true, semNtfy: true },
    lab08: { semGitea: true, semMicrobin: true, semFuxa: true, semNtfy: true, captura: true },
    lab09: { semGitea: true, semMicrobin: true, semFuxa: true, semNtfy: true, captura: true },
    projeto: {},
};

/* ------------------------------------------------------------------ */
/* Opções do gen_iot_scada_portal.py (servidor do laboratório)          */
/* ------------------------------------------------------------------ */

export type ScadaOpcoes = {
    semTunel?: boolean;
    publicoUrl?: string;
    vpsHost?: string;
    vpsAdmin?: string;
    semGitea?: boolean;
    semRunner?: boolean;
    giteaDb?: "postgres" | "sqlite";
    giteaRepo?: string;
    runnerCapacidade?: number;
    runnerDns?: string;
    semMicrobin?: boolean;
    semFuxa?: boolean;
    semNtfy?: boolean;
    protegerHttp?: boolean;
    mqttSemAnonimo?: boolean;
    mqttExplorerAuth?: boolean;
    extras?: string[];
};

export const PRESETS_SCADA: Record<string, ScadaOpcoes> = {
    lab05: {}, // LAB IoT completo
    lab06: { semGitea: true, semMicrobin: true },
    lab07: { semGitea: true, semMicrobin: true, semFuxa: true, semNtfy: true },
    lab08: {},
    projeto: {},
};
