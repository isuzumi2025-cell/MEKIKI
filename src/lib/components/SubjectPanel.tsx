/**
 * SubjectPanel.tsx
 *
 * サブジェクト一覧パネル。
 * 検索バーと carryover フィルタリング、SubjectCard の一覧表示を提供する。
 */

import type React from "react";
import { useState, useMemo, useCallback } from "react";
import type { Subject } from "../types/subject";
import { SubjectCard } from "./SubjectCard";

export interface SubjectPanelProps {
  subjects: Subject[];
  onToggleCarryover: (id: string, carryover: boolean) => void;
  onRemove?: (id: string) => void;
}

type FilterMode = "all" | "carryover" | "non-carryover";

const panelStyle: React.CSSProperties = {
  fontFamily: "'Inter', 'Segoe UI', sans-serif",
  padding: "16px",
  backgroundColor: "#ffffff",
  borderRadius: "12px",
  border: "1px solid #e0e0e0",
  maxWidth: "480px",
  width: "100%",
};

const headerStyle: React.CSSProperties = {
  display: "flex",
  justifyContent: "space-between",
  alignItems: "center",
  marginBottom: "12px",
};

const titleStyle: React.CSSProperties = {
  fontSize: "16px",
  fontWeight: 700,
  color: "#212121",
  margin: 0,
};

const countStyle: React.CSSProperties = {
  fontSize: "12px",
  color: "#9e9e9e",
};

const searchInputStyle: React.CSSProperties = {
  width: "100%",
  padding: "8px 12px",
  fontSize: "13px",
  border: "1px solid #e0e0e0",
  borderRadius: "6px",
  outline: "none",
  boxSizing: "border-box",
  marginBottom: "8px",
};

const filterContainerStyle: React.CSSProperties = {
  display: "flex",
  gap: "6px",
  marginBottom: "12px",
};

const filterButtonBaseStyle: React.CSSProperties = {
  padding: "4px 12px",
  fontSize: "12px",
  border: "1px solid #e0e0e0",
  borderRadius: "16px",
  cursor: "pointer",
  backgroundColor: "#ffffff",
  color: "#616161",
  transition: "all 0.15s ease",
};

const filterButtonActiveStyle: React.CSSProperties = {
  ...filterButtonBaseStyle,
  backgroundColor: "#1976d2",
  borderColor: "#1976d2",
  color: "#ffffff",
};

const listContainerStyle: React.CSSProperties = {
  maxHeight: "400px",
  overflowY: "auto",
};

const emptyStyle: React.CSSProperties = {
  textAlign: "center",
  padding: "24px",
  color: "#9e9e9e",
  fontSize: "13px",
};

export const SubjectPanel: React.FC<SubjectPanelProps> = ({
  subjects,
  onToggleCarryover,
}) => {
  const [searchQuery, setSearchQuery] = useState("");
  const [filterMode, setFilterMode] = useState<FilterMode>("all");

  const handleSearchChange = useCallback(
    (e: React.ChangeEvent<HTMLInputElement>) => {
      setSearchQuery(e.target.value);
    },
    []
  );

  const filteredSubjects = useMemo(() => {
    let result = subjects;

    if (filterMode === "carryover") {
      result = result.filter((s) => s.carryover);
    } else if (filterMode === "non-carryover") {
      result = result.filter((s) => !s.carryover);
    }

    if (searchQuery.trim()) {
      const lowerQuery = searchQuery.toLowerCase();
      result = result.filter(
        (s) =>
          s.name.toLowerCase().includes(lowerQuery) ||
          s.description?.toLowerCase().includes(lowerQuery) ||
          s.keyFeatures.some((f) => f.toLowerCase().includes(lowerQuery))
      );
    }

    return result;
  }, [subjects, searchQuery, filterMode]);

  const carryoverCount = useMemo(
    () => subjects.filter((s) => s.carryover).length,
    [subjects]
  );

  return (
    <div style={panelStyle} data-testid="subject-panel">
      <div style={headerStyle}>
        <h3 style={titleStyle}>Subjects</h3>
        <span style={countStyle}>
          {filteredSubjects.length} / {subjects.length}
          {carryoverCount > 0 && ` (${carryoverCount} carryover)`}
        </span>
      </div>

      <input
        type="text"
        placeholder="Search subjects..."
        value={searchQuery}
        onChange={handleSearchChange}
        style={searchInputStyle}
        data-testid="subject-search"
        aria-label="Search subjects"
      />

      <div style={filterContainerStyle}>
        <button
          style={filterMode === "all" ? filterButtonActiveStyle : filterButtonBaseStyle}
          onClick={() => setFilterMode("all")}
          data-testid="filter-all"
        >
          All
        </button>
        <button
          style={
            filterMode === "carryover"
              ? filterButtonActiveStyle
              : filterButtonBaseStyle
          }
          onClick={() => setFilterMode("carryover")}
          data-testid="filter-carryover"
        >
          Carryover
        </button>
        <button
          style={
            filterMode === "non-carryover"
              ? filterButtonActiveStyle
              : filterButtonBaseStyle
          }
          onClick={() => setFilterMode("non-carryover")}
          data-testid="filter-non-carryover"
        >
          Non-carryover
        </button>
      </div>

      <div style={listContainerStyle} data-testid="subject-list">
        {filteredSubjects.length === 0 ? (
          <div style={emptyStyle}>
            {subjects.length === 0
              ? "No subjects registered"
              : "No subjects match the current filter"}
          </div>
        ) : (
          filteredSubjects.map((subject) => (
            <SubjectCard
              key={subject.id}
              subject={subject}
              onToggleCarryover={onToggleCarryover}
              highlight={searchQuery}
            />
          ))
        )}
      </div>
    </div>
  );
};
