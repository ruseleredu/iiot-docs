import { NavbarItem } from "@docusaurus/theme-common";

// 1. Import the labData array
// https://gemini.google.com/share/c52111cbf825
// Adjust the path as needed.
const { labData } = require("./src/data/labData");
// OR: import { labData } from './src/data/labData';

// 2. Create the Docusaurus-compatible array format
const labDropdownItems = labData.map((lab) => ({
    // Docusaurus expects 'label'. We use your 'conteudo' property for the text.
    //label: lab.conteudo,
    label: `${lab.tarefa} - ${lab.conteudo}`,
    // Docusaurus expects 'to' (for internal links). We use your 'hrefi' property.
    to: lab.hrefi,
}));

const { quizData } = require("./src/data/quizData");

// 2. Create the Docusaurus-compatible array format
const quizDropdownItems = quizData.map((quiz) => ({
    // Docusaurus expects 'label'. We use your 'descricao' property for the text.
    //label: lab.conteudo,
    label: `${quiz.quiz} - ${quiz.descricao}`,
    // Docusaurus expects 'to' (for internal links). We use your 'hrefi' property.
    to: quiz.hrefi,
}));

const navbarItems: NavbarItem[] = [
    {
        type: "docSidebar",
        sidebarId: "tutorialSidebar",
        position: "left",
        label: "Tutorial",
    },
    {
        label: "UTFPR",
        to: "/utfpr/about", // Link to a page in your UTFPR docs
        type: "dropdown",
        position: "left",
        items: [
            {
                to: "/utfpr/ELT85B/folder", // Link to a page in your UTFPR docs
                label: "ELT85B - IIoT",
            },
        ],
    },
    {
        to: "/ead/intro", // Link to a page in your EaD docs
        label: "EaD",
        type: "dropdown",
        position: "left",
        activeBaseRegex: `/ead/`, // Highlight when any EaD doc is active
        items: [...quizDropdownItems],
    },
    {
        to: "/lab/intro", // Link to a page in your LAB docs
        label: "LABs",
        type: "dropdown",
        position: "left",
        activeBaseRegex: `/lab/`, // Highlight when any LAB doc is active
        items: [...labDropdownItems],
    },
    {
        label: "Projetos",
        to: "/pjts/intro", // Link to a page in your UTFPR docs
        type: "dropdown",
        position: "left",
        items: [
            {
                to: "/pjts/2026.2", // Link to a page in your PJTS docs
                label: "Semestre 2026.2",
            },
        ],
    },
    // { to: "/blog", label: "Blog", position: "right" },
    { to: "/pdf/CT2026.pdf", label: "Calendário", position: "right", target: '_blank' },
    {
        href: "https://github.com/ruseleredu/iiot-docs",
        label: "GitHub",
        position: "right",
    },
];

export default navbarItems;
