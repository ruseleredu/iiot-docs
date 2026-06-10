// src/components/QuizTable.tsx
import React from "react";
import Link from "@docusaurus/Link";
import DataTable, { Column } from "./DataTable";
import { quizData, QuizRow } from "../data/quizData";

interface QuizTableProps {
    index?: number;
    internal?: boolean; // true => use hrefi, false => use hrefe
}

function renderLink(
    label: string,
    hrefi?: string,
    hrefe?: string,
    internal: boolean = true
) {
    const href = internal ? hrefi : hrefe;
    if (!href) return <span>{label}</span>;

    return internal ? (
        <Link to={href}>{label}</Link>
    ) : (
        <a href={href} target="_blank" rel="noopener noreferrer">
            {label}
        </a>
    );
}

export default function QuizTable({ index, internal = true }: QuizTableProps) {
    const rows = index !== undefined ? [quizData[index]] : quizData;

    const columns: Column<QuizRow>[] = [
        {
            header: "Quiz",
            accessor: (row) => renderLink(row.quiz, row.hrefi, row.hrefe, internal),
        },
        { header: "Início", accessor: (row) => row.start },
        { header: "Fim", accessor: (row) => row.end },
        { header: "Descrição", accessor: (row) => row.descricao },
    ];

    return <DataTable columns={columns} rows={rows} />;
}

