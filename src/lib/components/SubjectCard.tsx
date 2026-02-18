/**
 * SubjectCard.tsx
 *
 * サブジェクト情報を表示するカードコンポーネント。
 * carryover トグルと keyFeatures バッジを含む。
 */

import type React from "react";
import { useCallback } from "react";
import type { Subject } from "../types/subject";

export interface SubjectCardProps {
  subject: Subject;
  onToggleCarryover: (id: string, carryover: boolean) => void;
  highlight?: string;
}

const cardStyle: React.CSSProperties = {
  border: "1px solid #e0e0e0",
  borderRadius: "8px",
  padding: "12px",
  marginBottom: "8px",
  backgroundColor: "#fafafa",
  transition: "box-shadow 0.2s ease",
};

const cardActiveStyle: React.CSSProperties = {
  ...cardStyle,
  borderColor: "#4caf50",
  backgroundColor: "#f1f8e9",
};

const headerStyle: React.CSSProperties = {
  display: "flex",
  justifyContent: "space-between",
  alignItems: "center",
  marginBottom: "6px",
};

const nameStyle: React.CSSProperties = {
  fontWeight: 600,
  fontSize: "14px",
  color: "#212121",
  margin: 0,
};

const descriptionStyle: React.CSSProperties = {
  fontSize: "12px",
  color: "#616161",
  margin: "0 0 8px 0",
  lineHeight: 1.4,
};

const featuresContainerStyle: React.CSSProperties = {
  display: "flex",
  flexWrap: "wrap",
  gap: "4px",
  marginBottom: "8px",
};

const featureBadgeStyle: React.CSSProperties = {
  display: "inline-block",
  padding: "2px 8px",
  fontSize: "11px",
  borderRadius: "12px",
  backgroundColor: "#e3f2fd",
  color: "#1565c0",
};

const featureBadgeHighlightStyle: React.CSSProperties = {
  ...featureBadgeStyle,
  backgroundColor: "#fff9c4",
  color: "#f57f17",
  fontWeight: 600,
};

const toggleContainerStyle: React.CSSProperties = {
  display: "flex",
  alignItems: "center",
  gap: "6px",
};

const toggleLabelStyle: React.CSSProperties = {
  fontSize: "12px",
  color: "#757575",
  cursor: "pointer",
  userSelect: "none",
};

const metaStyle: React.CSSProperties = {
  fontSize: "11px",
  color: "#9e9e9e",
  marginTop: "4px",
};

function highlightText(text: string, highlight: string): React.ReactNode {
  if (!highlight) {
    return text;
  }

  const lowerText = text.toLowerCase();
  const lowerHighlight = highlight.toLowerCase();
  const index = lowerText.indexOf(lowerHighlight);

  if (index === -1) {
    return text;
  }

  return (
    <>
      {text.slice(0, index)}
      <mark style={{ backgroundColor: "#fff59d", padding: 0 }}>
        {text.slice(index, index + highlight.length)}
      </mark>
      {text.slice(index + highlight.length)}
    </>
  );
}

export const SubjectCard: React.FC<SubjectCardProps> = ({
  subject,
  onToggleCarryover,
  highlight = "",
}) => {
  const handleToggle = useCallback(() => {
    onToggleCarryover(subject.id, !subject.carryover);
  }, [subject.id, subject.carryover, onToggleCarryover]);

  const isFeatureHighlighted = (feature: string): boolean => {
    if (!highlight) return false;
    return feature.toLowerCase().includes(highlight.toLowerCase());
  };

  return (
    <div
      style={subject.carryover ? cardActiveStyle : cardStyle}
      data-testid={`subject-card-${subject.id}`}
    >
      <div style={headerStyle}>
        <h4 style={nameStyle}>
          {highlightText(subject.name, highlight)}
        </h4>
        <div style={toggleContainerStyle}>
          <label style={toggleLabelStyle} htmlFor={`carryover-${subject.id}`}>
            Carryover
          </label>
          <input
            id={`carryover-${subject.id}`}
            type="checkbox"
            checked={subject.carryover}
            onChange={handleToggle}
            aria-label={`${subject.name} carryover toggle`}
          />
        </div>
      </div>

      {subject.description && (
        <p style={descriptionStyle}>
          {highlightText(subject.description, highlight)}
        </p>
      )}

      {subject.keyFeatures.length > 0 && (
        <div style={featuresContainerStyle}>
          {subject.keyFeatures.map((feature, i) => (
            <span
              key={`${feature}-${i}`}
              style={
                isFeatureHighlighted(feature)
                  ? featureBadgeHighlightStyle
                  : featureBadgeStyle
              }
            >
              {feature}
            </span>
          ))}
        </div>
      )}

      <div style={metaStyle}>
        {subject.sourceJobId && <span>Job: {subject.sourceJobId}</span>}
        {subject.sourceJobId && subject.createdAt && <span> | </span>}
        {subject.createdAt && (
          <span>
            {new Date(subject.createdAt).toLocaleDateString("ja-JP")}
          </span>
        )}
      </div>
    </div>
  );
};
