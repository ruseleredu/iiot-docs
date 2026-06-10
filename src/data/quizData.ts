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
        start: "09-Mar-2026",
        end: "15-Mar-2026",
        descricao:
            "Apresentação da Disciplina; Materiais utilizados na disciplina;",
    },
    {
        quiz: "Q01",
        hrefi: "/ead/Q01",
        hrefe: "https://moodle.utfpr.edu.br/course/section.php?id=375304",
        start: "16-Mar-2026",
        end: "22-Mar-2026",
        descricao:
            "Sistemas Numéricos e Representação de Dados; Conceitos Básicos de Eletrônica;",
    },
    {
        quiz: "Q02",
        hrefi: "/ead/Q02",
        hrefe: "https://moodle.utfpr.edu.br/course/section.php?id=375305",
        start: "23-Mar-2026",
        end: "29-Mar-2026",
        descricao:
            "Portas lógicas. Tabela Verdade. Mintermos e Maxtermos. Funções lógicas;",
    },
    {
        quiz: "Q03",
        hrefi: "/ead/Q03",
        hrefe: "https://moodle.utfpr.edu.br/course/section.php?id=375306",
        start: "30-Mar-2026",
        end: "05-Apr-2026",
        descricao:
            "Teoremas fundamentais da álgebra de Boole. Teorema de Morgan e simplificação de funções lógicas.",
    },
    {
        quiz: "Q04",
        hrefi: "/ead/Q04",
        hrefe: "https://moodle.utfpr.edu.br/course/section.php?id=375307",
        start: "06-Apr-2026",
        end: "12-Apr-2026",
        descricao:
            "Formas canônicas (mintermos e maxitermos), Mapas de Veitch Karnaugh;",
    },
    {
        quiz: "Q05",
        hrefi: "/ead/Q05",
        hrefe: "https://moodle.utfpr.edu.br/course/section.php?id=375308",
        start: "13-Apr-2026",
        end: "19-Apr-2026",
        descricao: "Exercícios sobre simplificação e introdução ao Arduino;",
    },
    {
        quiz: "Q06",
        hrefi: "/ead/Q06",
        hrefe: "https://moodle.utfpr.edu.br/course/section.php?id=375309",
        start: "20-Apr-2026",
        end: "26-Apr-2026",
        descricao: "Multiplexador e Demultiplexador;",
    },
    {
        quiz: "Q07",
        hrefi: "/ead/Q07",
        hrefe: "https://moodle.utfpr.edu.br/course/section.php?id=375310",
        start: "27-Apr-2026",
        end: "03-May-2026",
        descricao: "Códigos, codificadores e decodificadores;",
    },
    {
        quiz: "Q08",
        hrefi: "/ead/Q08",
        hrefe: "https://moodle.utfpr.edu.br/course/section.php?id=391745",
        start: "04-May-2026",
        end: "10-May-2026",
        descricao: "Arduino - Parte 02;",
    },
    {
        quiz: "Q09",
        hrefi: "/ead/Q09",
        hrefe: "https://moodle.utfpr.edu.br/course/section.php?id=375314",
        start: "11-May-2026",
        end: "17-May-2026",
        descricao: "Flip flop RS e JK;",
    },
    {
        quiz: "Q10",
        hrefi: "/ead/Q10",
        hrefe: "https://moodle.utfpr.edu.br/course/section.php?id=375315",
        start: "18-May-2026",
        end: "24-May-2026",
        descricao: "Flip flop JK, T e D;",
    },

    {
        quiz: "Q11",
        hrefi: "/ead/Q11",
        hrefe: "https://moodle.utfpr.edu.br/course/section.php?id=375316",
        start: "25-May-2026",
        end: "31-May-2026",
        descricao: "Contadores Assíncronos;",
    },
    {
        quiz: "Q12",
        hrefi: "/ead/Q12",
        hrefe: "https://moodle.utfpr.edu.br/course/section.php?id=375317",
        start: "01-Jun-2026",
        end: "07-Jun-2026",
        descricao: "Contadores Síncronos;",
    },
    {
        quiz: "Q13",
        hrefi: "/ead/Q13",
        hrefe: "https://moodle.utfpr.edu.br/course/section.php?id=375312",
        start: "08-Jun-2026",
        end: "14-Jun-2026",
        descricao: "Aritmética binaria, somador e subtrator;",
    },
    {
        quiz: "Q14",
        hrefi: "/ead/Q14",
        hrefe: "https://moodle.utfpr.edu.br/course/section.php?id=375318",
        start: "08-Jun-2026",
        end: "15-Jun-2026",
        descricao: "Conversão análogico-digital (CAD) e digital-analógico (CDA);",
    },
    {
        quiz: "Q15",
        hrefi: "/ead/Q15",
        hrefe: "https://moodle.utfpr.edu.br/course/section.php?id=375319",
        start: "08-Jun-2026",
        end: "15-Jun-2026",
        descricao: "Tipos de memórias digitais, registradores e geradores de clock;",
    },
];
