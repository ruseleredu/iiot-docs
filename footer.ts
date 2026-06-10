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
            title: "Sistemas",
            items: [
                {
                    label: "Sigepe",
                    href: "https://sougov.sigepe.gov.br/sougov/Home",
                },
                {
                    label: "Consulta Diários",
                    href: "https://sistemas2.utfpr.edu.br/url/1141",
                },
                {
                    label: "Permanências",
                    href: "https://sistemas2.utfpr.edu.br/url/1026",
                },
                {
                    label: "Planejamento",
                    href: "https://sistemas2.utfpr.edu.br/url/1890",
                },
                {
                    label: "Lançamentos",
                    href: "https://sistemas2.utfpr.edu.br/url/1514",
                },
                {
                    label: "Mapa de Professor",
                    href: "https://sistemas2.utfpr.edu.br/url/1022",
                },
                {
                    label: "Mapa de Sala",
                    href: "https://sistemas2.utfpr.edu.br/url/1934",
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
                    label: "PlatformIO",
                    href: "https://platformio.org//install/ide?install=vscode",
                },
                {
                    label: "Arduino IDE",
                    href: "https://www.arduino.cc/en/software/",
                },
            ],
        },
        {
            title: "Ferramentas",
            items: [
                {
                    label: "K-Map Solver",
                    href: "https://karnaughmapsolver.com/",
                },
                {
                    label: "Karnaugh Map Solver",
                    href: "https://wredan.github.io/Karnaugh-Map-Solver/",
                },
                {
                    label: "Tinkercad Circuits",
                    href: "https://www.tinkercad.com/circuits",
                },
                {
                    label: "Logic circuit simplification",
                    href: "http://www.32x8.com/index.html",
                },
                {
                    label: "Quine McCluskey Solver",
                    href: "https://quinemccluskey.geeekyboy.com/",
                },
                {
                    label: "PlatformIO",
                    href: "https://platformio.org//install/ide?install=vscode",
                },
                {
                    label: "WinGet",
                    href: "https://winget.run/",
                },
            ],
        },
        {
            title: "Doku Sites",
            items: [
                {
                    label: "Main Site",
                    href: "https://adrianoruseler.github.io/site/",
                },
                {
                    label: "STM32 Docs",
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
                    label: "IIoT Industrial",
                    href: "https://ruseleredu.github.io/iiot-docs/",
                },
                {
                    label: "Moodle Docs",
                    href: "https://ruseleredu.github.io/moodle-docs/",
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
