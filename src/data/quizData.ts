// src/data/quizData.ts
export type QuizRow = {
    quiz: string;

    // internal/external quiz links
    hrefi?: string; // internal (/quiz/quiz00)
    hrefe?: string; // external (Moodle, etc.)

    start: string;
    end: string;
    descricao: string;
};

export const quizData: QuizRow[] = [
    {
        quiz: "Q00",
        hrefi: "/ead/Q00",
        hrefe: "https://moodle.utfpr.edu.br/course/section.php?id=384598",
        start: "20-08-2026",
        end: "27-08-2026",
        descricao: "Apresentação da Disciplina; Formação dos grupos;",
    },
    {
        quiz: "Q01",
        hrefi: "/ead/Q01",
        hrefe: "https://moodle.utfpr.edu.br/course/section.php?id=375304",
        start: "27-08-2026",
        end: "03-09-2026",
        descricao: "Visão Geral sobre IoT;",
    },
    {
        quiz: "Q02",
        hrefi: "/ead/Q02",
        hrefe: "https://moodle.utfpr.edu.br/course/section.php?id=375305",
        start: "03-09-2026",
        end: "10-09-2026",
        descricao: "A Internet na IoT;",
    },
    {
        quiz: "Q03",
        hrefi: "/ead/Q03",
        hrefe: "https://moodle.utfpr.edu.br/course/section.php?id=375306",
        start: "10-09-2026",
        end: "17-09-2026",
        descricao: "Sensores e Atuadores em IoT;",
    },
    {
        quiz: "Q04",
        hrefi: "/ead/Q04",
        hrefe: "https://moodle.utfpr.edu.br/course/section.php?id=375307",
        start: "17-09-2026",
        end: "24-09-2026",
        descricao: "Pilha de Protocolos IoT: Enlace e Rede;",
    },
    {
        quiz: "Q05",
        hrefi: "/ead/Q05",
        hrefe: "https://moodle.utfpr.edu.br/course/section.php?id=375308",
        start: "24-09-2026",
        end: "01-10-2026",
        descricao: "Pilha de Protocolos IoT: Aplicação;",
    },
    {
        quiz: "Q06",
        hrefi: "/ead/Q06",
        hrefe: "https://moodle.utfpr.edu.br/course/section.php?id=375309",
        start: "01-10-2026",
        end: "08-10-2026",
        descricao: "Computação em Nevoeiro (Fog Computing);",
    },
    {
        quiz: "Q07",
        hrefi: "/ead/Q07",
        hrefe: "https://moodle.utfpr.edu.br/course/section.php?id=375310",
        start: "08-10-2026",
        end: "15-10-2026",
        descricao: "Plataforma de Serviços IoT;",
    },
    {
        quiz: "Q08",
        hrefi: "/ead/Q08",
        hrefe: "https://moodle.utfpr.edu.br/course/section.php?id=391745",
        start: "15-10-2026",
        end: "22-10-2026",
        descricao: "Mercados de IoT: Agricultura e Energia;", // 19 a 23 – SICITE 2026
    },
    {
        quiz: "Q09",
        hrefi: "/ead/Q09",
        hrefe: "https://moodle.utfpr.edu.br/course/section.php?id=375314",
        start: "22-10-2026",
        end: "29-10-2026",
        descricao: "Mercados de IoT: Indústria e Transporte;", // 19 a 23 – SICITE 2026
    },
    {
        quiz: "Q10",
        hrefi: "/ead/Q10",
        hrefe: "https://moodle.utfpr.edu.br/course/section.php?id=375315",
        start: "29-10-2026",
        end: "05-11-2026",
        descricao: "Padrões IoT;",
    },

    {
        quiz: "Q11",
        hrefi: "/ead/Q11",
        hrefe: "https://moodle.utfpr.edu.br/course/section.php?id=375316",
        start: "25-May-2026",
        end: "31-May-2026",
        descricao: "Projeto Final: Definição e Kickoff;",
    },
    {
        quiz: "Q12",
        hrefi: "/ead/Q12",
        hrefe: "https://moodle.utfpr.edu.br/course/section.php?id=375317",
        start: "01-Jun-2026",
        end: "07-Jun-2026",
        descricao: "Projeto Final: Integração Node-RED e InfluxDB;",
    },
    {
        quiz: "Q13",
        hrefi: "/ead/Q13",
        hrefe: "https://moodle.utfpr.edu.br/course/section.php?id=375312",
        start: "08-Jun-2026",
        end: "14-Jun-2026",
        descricao: "Projeto Final: Dashboard;",
    },
    {
        quiz: "Q14",
        hrefi: "/ead/Q14",
        hrefe: "https://moodle.utfpr.edu.br/course/section.php?id=375318",
        start: "08-Jun-2026",
        end: "15-Jun-2026",
        descricao: "Projeto Final: Refinamento e APS Final;",
    },
    {
        quiz: "Q15",
        hrefi: "/ead/Q15",
        hrefe: "https://moodle.utfpr.edu.br/course/section.php?id=375319",
        start: "08-Jun-2026",
        end: "15-Jun-2026",
        descricao: "Projeto Final: Apresentações;",
    },
];
