"use client";

import { ReactNode } from "react";

interface Column<T> {
  key: keyof T | string;
  header: string;
  render?: (row: T) => ReactNode;
  width?: string;
  align?: "left" | "center" | "right";
}

interface TableProps<T> {
  columns: Column<T>[];
  data: T[];
  onRowClick?: (row: T) => void;
  emptyMessage?: string;
}

export function Table<T extends Record<string, unknown>>({
  columns,
  data,
  onRowClick,
  emptyMessage = "No data",
}: TableProps<T>) {
  const alignClass = {
    left: "text-left",
    center: "text-center",
    right: "text-right",
  };

  return (
    <div className="font-mono overflow-x-auto">
      {/* Header */}
      <div className="flex border-b border-terminal-gray text-terminal-white-dim text-sm">
        {columns.map((col) => (
          <div
            key={String(col.key)}
            className={`px-3 py-2 ${col.width || "flex-1"} ${
              alignClass[col.align || "left"]
            }`}
          >
            {col.header}
          </div>
        ))}
      </div>

      {/* Body */}
      {data.length === 0 ? (
        <div className="px-3 py-8 text-center text-terminal-white-dim">
          {emptyMessage}
        </div>
      ) : (
        data.map((row, idx) => (
          <div
            key={idx}
            className={`
              flex border-b border-terminal-gray text-terminal-green
              ${onRowClick ? "cursor-pointer hover:bg-terminal-darkgray" : ""}
            `}
            onClick={() => onRowClick?.(row)}
          >
            {columns.map((col) => (
              <div
                key={String(col.key)}
                className={`px-3 py-2 ${col.width || "flex-1"} ${
                  alignClass[col.align || "left"]
                } truncate`}
              >
                {col.render
                  ? col.render(row)
                  : String(row[col.key as keyof T] ?? "")}
              </div>
            ))}
          </div>
        ))
      )}
    </div>
  );
}
