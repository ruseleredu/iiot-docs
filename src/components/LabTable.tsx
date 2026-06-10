// src/components/LabTable.tsx
import React from "react";
import Link from "@docusaurus/Link";
import DataTable, { Column } from "./DataTable";
import { labData, LabRow } from "../data/labData";

interface LabTableProps {
    index?: number;
    internal?: boolean; // select which link set to use
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

export default function LabTable({ index, internal = true }: LabTableProps) {
    const rows = index !== undefined ? [labData[index]] : labData;

    const columns: Column<LabRow>[] = [
        {
            header: "Tarefa",
            accessor: (row) =>
                renderLink(row.tarefa, row.hrefi, row.hrefe, internal),
            className: "text-center",
        },
        { header: "Início", accessor: (row) => row.start },
        { header: "Fim", accessor: (row) => row.end },
        { header: "Conteúdo", accessor: (row) => row.conteudo },
    ];

    return <DataTable columns={columns} rows={rows} />;
}

