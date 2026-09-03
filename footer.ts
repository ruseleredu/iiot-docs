import { ThemeConfig } from "@docusaurus/preset-classic";

const currentYear = new Date().getFullYear();

const formatter = new Intl.DateTimeFormat("pt-BR", {
    timeZone: "America/Sao_Paulo",
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
    hourCycle: "h23",
});

const utc3Time = formatter.format(new Date());

// Using consistent styling for links
const linkStyle =
    'style="color: #ffffff; font-weight: bold;" target="_blank" rel="noopener noreferrer"';
const gitlink = `<a href="https://ruseleredu.github.io/iiot-docs/" ${linkStyle}>ELT85B</a>`;
const docusaurusVersion = require("@docusaurus/core/package.json").version;
const doclink = `<a href="https://docusaurus.io/" ${linkStyle}>Docusaurus</a>  v${docusaurusVersion}`;

const COPYRIGHT_STRING = `Copyright © ${currentYear} ${gitlink}. Built with ${doclink} at ${utc3Time} (UTC-3).`;

// In your module.exports / export default:
// footer: { copyright: COPYRIGHT_STRING }
const footer: ThemeConfig["footer"] = {
    style: "dark",
    links: [
        {
            title: "UTFPR",
            items: [
                {
                    label: "Moodle",
                    href: "https://moodle.utfpr.edu.br/",
                },
                {
                    label: "Webmail",
                    href: "https://webmail.utfpr.edu.br/",
                },
                {
                    label: "Sistemas",
                    href: "https://sistemas2.utfpr.edu.br/",
                },
                {
                    label: "SEI",
                    href: "https://sei.utfpr.edu.br/",
                },
                {
                    label: "Chat",
                    href: "https://chat.utfpr.edu.br/",
                },
                {
                    label: "Ajuda",
                    href: "https://ajuda.utfpr.edu.br/",
                },
                {
                    label: "Calendário",
                    href: "https://www.utfpr.edu.br/alunos/calendario",
                },
                {
                    label: "TCC",
                    href: "https://nupet.daelt.ct.utfpr.edu.br/tcc/engenharia/index.html",
                },
            ],
        },
        {
            title: "Online Services",
            items: [
                {
                    label: "Markdown Preview",
                    href: "https://markdownlivepreview.com/",
                },
                {
                    label: "Wokwi",
                    href: "https://wokwi.com/esp32",
                },
                {
                    label: "Cirkit Designer",
                    href: "https://www.cirkitdesigner.com/esp32-simulator",
                },
                {
                    label: "Code Beautify",
                    href: "https://codebeautify.org/",
                },
                {
                    label: "SQLite Viewer",
                    href: "https://inloop.github.io/sqlite-viewer/",
                },
                {
                    label: "Mermaid Editor",
                    href: "https://mermaid.ai/live/",
                },
                {
                    label: "Compiler Explorer",
                    href: "https://compiler-explorer.com",
                },
            ],
        },
        {
            title: "Desenvolvedor",
            items: [
                {
                    label: "Visual Studio Code",
                    href: "https://code.visualstudio.com/download",
                },
                {
                    label: "PlatformIO",
                    href: "https://platformio.org//install/ide?install=vscode",
                },
                {
                    label: "Git SCM",
                    href: "https://git-scm.com/downloads",
                },
                {
                    label: "GitHub CLI",
                    href: "https://cli.github.com/",
                },
                {
                    label: "GitHub Desktop",
                    href: "https://desktop.github.com/download/",
                },
                {
                    label: "Docker Desktop",
                    href: "https://www.docker.com/products/docker-desktop/",
                },
                {
                    label: "Node-RED",
                    href: "https://nodered.org/",
                },
            ],
        },
        {
            title: "Recursos",
            items: [
                {
                    label: "DeepBlue",
                    href: "https://deepbluembedded.com/",
                },
                {
                    label: "RandomNerdTutorials",
                    href: "https://randomnerdtutorials.com/projects-esp32/",
                },
                {
                    label: "Learn Electronics",
                    href: "https://lastminuteengineers.com/",
                },
                {
                    label: "Wokwi",
                    href: "https://wokwi.com/",
                },
                {
                    label: "ESP32",
                    href: "https://www.espressif.com/en/products/socs/esp32",
                },
                {
                    label: "Arduino Documentation",
                    href: "https://docs.arduino.cc/",
                },
                {
                    label: "ESP32 Learning Kit",
                    href: "https://docs.keyestudio.com/en/latest/docs/esp32/esp32.html",
                },
            ],
        },
        {
            title: "Doku Sites",
            items: [
                {
                    label: "IoT Industrial",
                    href: "https://ruseleredu.github.io/iiot-docs/",
                },
                {
                    label: "Main Site",
                    href: "https://adrianoruseler.github.io/site/",
                },
                {
                    label: "MIC-ESP32",
                    href: "https://ruseleredu.github.io/mic-docs/",
                },
                {
                    label: "MIC-STM32",
                    href: "https://ruseleredu.github.io/stm32doc/",
                },
                {
                    label: "Sistemas Digitais",
                    href: "https://ruseleredu.github.io/sd-docs/",
                },
                {
                    label: "Analógica",
                    href: "https://ruseleredu.github.io/ea-docs/",
                },
                {
                    label: "Moodle Docs",
                    href: "https://ruseleredu.github.io/moodle-docs/",
                },
                {
                    label: "Kroki Docs",
                    href: "https://ruseleredu.github.io/kroki-docs/",
                },
            ],
        },
        {
            title: "Moodle",
            items: [
                {
                    label: "IoT Industrial",
                    href: "https://moodle.utfpr.edu.br/course/view.php?id=35058",
                },
                {
                    label: "Analógica",
                    href: "https://moodle.utfpr.edu.br/course/view.php?id=4785",
                },
                {
                    label: "Microcontrolados",
                    href: "https://moodle.utfpr.edu.br/course/view.php?id=29540",
                },
                {
                    label: "Digitais - EaD",
                    href: "https://moodle.utfpr.edu.br/course/view.php?id=27864",
                },
                {
                    label: "Digitais - LAB",
                    href: "https://moodle.utfpr.edu.br/course/view.php?id=28604",
                },
                {
                    label: "PSIM",
                    href: "https://moodle.utfpr.edu.br/course/view.php?id=12454",
                },
                {
                    label: "LTspice",
                    href: "https://moodle.utfpr.edu.br/course/view.php?id=12399",
                },
            ],
        },
        {
            title: "AI", //
            items: [
                {
                    label: "Gemini",
                    href: "https://gemini.google.com/app",
                }, //
                {
                    label: "ChatGPT",
                    href: "https://chatgpt.com/",
                }, //
                {
                    label: "Claude",
                    href: "https://claude.ai/",
                },
                {
                    label: "Copilot",
                    href: "https://copilot.microsoft.com/",
                },
                {
                    label: "DeepSeek",
                    href: "https://chat.deepseek.com/",
                },
                {
                    label: "Grok",
                    href: "https://grok.com/",
                },
                {
                    label: "Kimi",
                    href: "https://www.kimi.com/en",
                },
                {
                    label: "GLM",
                    href: "https://chat.z.ai/",
                },
            ],
        },
    ],
    copyright: COPYRIGHT_STRING,
};

export default footer;
