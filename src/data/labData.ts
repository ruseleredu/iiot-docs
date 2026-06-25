// src/data/labData.ts
export type LabRow = {
    tarefa: string;

    // internal/external lab links
    hrefi?: string; // internal
    hrefe?: string; // external


    start: string;
    end: string;
    conteudo: string;
};

export const labData: LabRow[] = [
    {
        tarefa: "LAB00",
        hrefi: "/lab/LAB00", // internal page
        hrefe: "https://moodle.utfpr.edu.br/course/section.php?id=384200", // external
        start: "20-08-2026",
        end: "27-08-2026",
        conteudo: "Apresentação da Disciplina; Formação dos grupos;",
    },
    {
        tarefa: "LAB01",
        hrefi: "/lab/LAB01",
        hrefe: "https://moodle.utfpr.edu.br/course/section.php?id=384201", // external
        start: "27-08-2026",
        end: "03-09-2026",
        conteudo: "Visão Geral sobre IoT;",
    },
    {
        tarefa: "LAB02",
        hrefi: "/lab/LAB02",
        hrefe: "https://moodle.utfpr.edu.br/course/section.php?id=380901", // external
        start: "03-09-2026",
        end: "10-09-2026",
        conteudo: "A Internet na IoT;",
    },
    {
        tarefa: "LAB03",
        hrefi: "/lab/LAB03",
        hrefe: "https://moodle.utfpr.edu.br/course/section.php?id=380902", // external
        start: "10-09-2026",
        end: "17-09-2026",
        conteudo: "Sensores e Atuadores em IoT;",
    },
    {
        tarefa: "LAB04",
        hrefi: "/lab/LAB04",
        hrefe: "https://moodle.utfpr.edu.br/course/section.php?id=380903", // external
        start: "17-09-2026",
        end: "24-09-2026",
        conteudo: "Pilha de Protocolos IoT: Enlace e Rede;",
    },
    {
        tarefa: "LAB05",
        hrefi: "/lab/LAB05",
        hrefe: "hhttps://moodle.utfpr.edu.br/course/section.php?id=387986", // external
        start: "24-09-2026",
        end: "01-10-2026",
        conteudo: "Pilha de Protocolos IoT: Aplicação;",
    },
    {
        tarefa: "LAB06",
        hrefi: "/lab/LAB06",
        hrefe: "https://moodle.utfpr.edu.br/course/section.php?id=387992", // external
        start: "01-10-2026",
        end: "08-10-2026",
        conteudo: "Computação em Nevoeiro (Fog Computing);",
    },
    {
        tarefa: "LAB07",
        hrefi: "/lab/LAB07",
        hrefe: "https://moodle.utfpr.edu.br/course/section.php?id=387993", // external
        start: "08-10-2026",
        end: "15-10-2026",
        conteudo: "Plataforma de Serviços IoT;",
    },
    {
        tarefa: "LAB08",
        hrefi: "/lab/LAB08",
        hrefe: "https://moodle.utfpr.edu.br/course/section.php?id=392012", // external
        start: "15-10-2026",
        end: "22-10-2026",
        conteudo: "Mercados de IoT: Agricultura e Energia;", // 19 a 23 – SICITE 2026
    },
    {
        tarefa: "LAB09",
        hrefi: "/lab/LAB09",
        hrefe: "https://moodle.utfpr.edu.br/course/section.php?id=392440", // external
        start: "22-10-2026",
        end: "29-10-2026",
        conteudo: "Mercados de IoT: Indústria e Transporte;", // 19 a 23 – SICITE 2026
    },
    {
        tarefa: "LAB10",
        hrefi: "/lab/LAB10",
        hrefe: "https://moodle.utfpr.edu.br/course/section.php?id=387994", // external
        start: "29-10-2026",
        end: "05-11-2026",
        conteudo: "Padrões IoT;",
    },

];
// src/components/LabTable.tsx
