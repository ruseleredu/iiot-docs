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
        start: "11-03-2026",
        end: "18-03-2026",
        conteudo: "Apresentação da Disciplina; Materiais utilizados na disciplina; Formação dos grupos;",
    },
    {
        tarefa: "LAB01",
        hrefi: "/lab/LAB01",
        hrefe: "https://moodle.utfpr.edu.br/course/section.php?id=384201", // external

        start: "18-03-2026",
        end: "25-03-2026",
        conteudo: "Utilização da matriz de contatos; Utilização de equipamentos; Regras do Laboratório;",
    },
    {
        tarefa: "LAB02",
        hrefi: "/lab/LAB02",
        hrefe: "https://moodle.utfpr.edu.br/course/section.php?id=380901", // external

        start: "25-03-2026",
        end: "01-Apr-2026",
        conteudo: "Portas Lógicas; Tensões de Entrada e Saída - Famílias Lógicas;",
    },
    {
        tarefa: "LAB03",
        hrefi: "/lab/LAB03",
        hrefe: "https://moodle.utfpr.edu.br/course/section.php?id=380902", // external

        start: "01-Apr-2026",
        end: "08-Apr-2026",
        conteudo: "Portas inversoras, E, OU, NE e NOU (Roteiro 3.2);",
    },
    {
        tarefa: "LAB04",
        hrefi: "/lab/LAB04",
        hrefe: "https://moodle.utfpr.edu.br/course/section.php?id=380903", // external

        start: "08-04-2026",
        end: "15-04-2026",
        conteudo: "Equivalência entre funções lógicas (Roteiro 4.1);",
        //   conteudo: "Módulo PWM; Conversor ADC;",
    },
    {
        tarefa: "LAB05",
        hrefi: "/lab/LAB05",
        hrefe: "hhttps://moodle.utfpr.edu.br/course/section.php?id=387986", // external

        start: "15-04-2026",
        end: "22-04-2026",
        conteudo: "Avaliação de uma tabela verdade - I (Roteiro 4.2) e Equações Lógicas descritas em Linguagem C;",
        // conteudo: "DMA: Direct memory access (Acesso direto à memória);",
    },
    {
        tarefa: "LAB06",
        hrefi: "/lab/LAB06",
        hrefe: "https://moodle.utfpr.edu.br/course/section.php?id=387992", // external

        start: "22-04-2026",
        end: "29-04-2026",
        conteudo: "Multiplexador (Roteiro 5.3).",
    },
    {
        tarefa: "LAB07",
        hrefi: "/lab/LAB07",
        hrefe: "https://moodle.utfpr.edu.br/course/section.php?id=387993", // external

        start: "29-04-2026",
        end: "06-May-2026",
        conteudo: "Demultiplexador (Roteiro 5.4);",
    },
    {
        tarefa: "LAB08",
        hrefi: "/lab/LAB08",
        hrefe: "https://moodle.utfpr.edu.br/course/section.php?id=392012", // external

        start: "06-05-2026",
        end: "13-05-2026",
        conteudo: "Flip-Flop RS (Roteiro 7.1);",
        // conteudo: "Uso do STM32CubeMonitor; InfluDB;",
    },
    {
        tarefa: "LAB09",
        hrefi: "/lab/LAB09",
        hrefe: "https://moodle.utfpr.edu.br/course/section.php?id=392440", // external

        start: "13-05-2026",
        end: "20-05-2026",
        // conteudo: "Uso do STM32CubeMonitor; InfluDB;",
        conteudo: "Contadores Assíncronos (Roteiro 9.1);",
        // conteudo: "FreeRTOS: Tarefas, Filas e Semáforos;",
    },
    {
        tarefa: "LAB10",
        hrefi: "/lab/LAB10",
        hrefe: "https://moodle.utfpr.edu.br/course/section.php?id=387994", // external

        start: "20-05-2026",
        end: "27-05-2026",
        // conteudo: "Uso do STM32CubeMonitor; InfluDB;",
        conteudo: " Validação do LAB 05 com o Arduino Uno R3 SMD ou com tinkercad;",
        // conteudo: "FreeRTOS: Tarefas, Filas e Semáforos;",
    },

];
// src/components/LabTable.tsx
