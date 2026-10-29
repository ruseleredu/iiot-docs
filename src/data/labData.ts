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
        hrefi: "/labs/LAB00", // internal page
        hrefe: "https://moodle.utfpr.edu.br/course/section.php?id=384200", // external
        start: "20-08-2026",
        end: "27-08-2026",
        conteudo: "Apresentação da Disciplina; Formação dos grupos;",
    },
    {
        tarefa: "LAB01",
        hrefi: "/labs/LAB01",
        hrefe: "https://moodle.utfpr.edu.br/course/section.php?id=384201", // external
        start: "27-08-2026",
        end: "03-09-2026",
        conteudo: "Git, GitHub e VS Code;",
    },
    {
        tarefa: "LAB02",
        hrefi: "/labs/LAB02",
        hrefe: "https://moodle.utfpr.edu.br/course/section.php?id=380901", // external
        start: "03-09-2026",
        end: "10-09-2026",
        conteudo: "PlatformIO, Wokwi e Docker;",
    },
    {
        tarefa: "LAB03",
        hrefi: "/labs/LAB03",
        hrefe: "https://moodle.utfpr.edu.br/course/section.php?id=380902", // external
        start: "10-09-2026",
        end: "17-09-2026",
        conteudo: "logs no ESP32 e ambientes de build (debug × release);",
    },
    {
        tarefa: "LAB04",
        hrefi: "/labs/LAB04",
        hrefe: "https://moodle.utfpr.edu.br/course/section.php?id=380903", // external
        start: "17-09-2026",
        end: "24-09-2026",
        conteudo: "WiFi e MQTT no ESP32;",
    },
    {
        tarefa: "LAB05",
        hrefi: "/labs/LAB05",
        hrefe: "hhttps://moodle.utfpr.edu.br/course/section.php?id=387986", // external
        start: "24-09-2026",
        end: "01-10-2026",
        conteudo: "DHT22, temporizador e MQTT com Node-RED;",
    },
    {
        tarefa: "LAB06",
        hrefi: "/labs/LAB06",
        hrefe: "https://moodle.utfpr.edu.br/course/section.php?id=387992", // external
        start: "01-10-2026",
        end: "08-10-2026",
        conteudo: "SSD1306, MQTT nos dois sentidos, SQLite e Dashboard;",
    },
    {
        tarefa: "LAB07",
        hrefi: "/labs/LAB07",
        hrefe: "https://moodle.utfpr.edu.br/course/section.php?id=387993", // external
        start: "08-10-2026",
        end: "15-10-2026",
        conteudo: "ADC, PWM, modos de operação e controle ON/OFF;",
    },
    {
        tarefa: "LAB08",
        hrefi: "/labs/LAB08",
        hrefe: "https://moodle.utfpr.edu.br/course/section.php?id=392012", // external
        start: "15-10-2026",
        end: "22-10-2026",
        conteudo: "Modbus, S7 e OPC-UA (conceitos iniciais);", // 19 a 23 – SICITE 2026
    },
    {
        tarefa: "LAB09",
        hrefi: "/labs/LAB09",
        hrefe: "https://moodle.utfpr.edu.br/course/section.php?id=392440", // external
        start: "22-10-2026",
        end: "29-10-2026",
        conteudo: "Modbus, S7 e OPC-UA a fundo: painel SCADA e controle pela rede;", // 19 a 23 – SICITE 2026
    },
    {
        tarefa: "LAB10",
        hrefi: "/labs/LAB10",
        hrefe: "https://moodle.utfpr.edu.br/course/section.php?id=387994", // external
        start: "29-10-2026",
        end: "05-11-2026",
        conteudo: "SCADA da câmara com FUXA;",
    },
    {
        tarefa: "LAB11",
        hrefi: "/labs/LAB11",
        hrefe: "https://moodle.utfpr.edu.br/course/section.php?id=387994", // external
        start: "29-10-2026",
        end: "05-11-2026",
        conteudo: "Testes, simulação e CI/CD do firmware;",
    },
    {
        tarefa: "LAB12",
        hrefi: "/labs/LAB12",
        hrefe: "https://moodle.utfpr.edu.br/course/section.php?id=387994", // external
        start: "29-10-2026",
        end: "05-11-2026",
        conteudo: "LAB IoT na sua máquina;",
    },

];
// src/components/LabTable.tsx
