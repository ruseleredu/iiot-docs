// src/components/DataTable.tsx
import React from "react";
// import Link from "@docusaurus/Link";

export type Column<T> = {
    header: string;                      // column header label
    accessor: (row: T) => React.ReactNode; // how to render cell
    className?: string;                  // optional cell style
};

interface DataTableProps<T> {
    columns: Column<T>[];
    rows: T[];
}

export default function DataTable<T>({ columns, rows }: DataTableProps<T>) {
    return (
        <table className="border-collapse border border-gray-300 w-full text-sm mx-auto">
            <thead>
                <tr className="bg-gray-100">
                    {columns.map((col, i) => (
                        <th className={`border border-gray-300 px-3 py-1 text-center ${col.className || ""}`}>
                            {col.header}
                        </th>
                    ))}
                </tr>
            </thead>
            <tbody>
                {rows.map((row, rowIndex) => (
                    <tr key={rowIndex}>
                        {columns.map((col, colIndex) => (
                            <td className={`border border-gray-300 px-3 py-1 ${col.className || ""}`}>
                                {col.accessor(row)}
                            </td>
                        ))}
                    </tr>
                ))}
            </tbody>
        </table>
    );
}
