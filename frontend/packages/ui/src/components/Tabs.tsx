import { useState } from "react";
import { colors, space, radius } from "../tokens";

export interface Tab {
  label: string;
  content: React.ReactNode;
}

export interface TabsProps {
  tabs: Tab[];
}

export function Tabs({ tabs }: TabsProps) {
  const [activeTab, setActiveTab] = useState(0);

  return (
    <div
      style={{
        border: `1px solid ${colors.border}`,
        borderRadius: radius.md,
        overflow: "hidden",
      }}
    >
      <div
        style={{
          display: "flex",
          borderBottom: `1px solid ${colors.border}`,
          backgroundColor: colors.surface,
        }}
      >
        {tabs.map((tab, index) => (
          <button
            key={tab.label}
            onClick={() => setActiveTab(index)}
            style={{
              padding: `${space.sm}px ${space.md}px`,
              cursor: "pointer",
              border: "none",
              backgroundColor:
                activeTab === index
                  ? colors.primary
                  : colors.surface,
              color:
                activeTab === index
                  ? "#fff"
                  : colors.text,
              fontWeight: "bold",
              flex: 1,
            }}
          >
            {tab.label}
          </button>
        ))}
      </div>

      <div
        style={{
          padding: space.lg,
          backgroundColor: colors.surface,
          color: colors.text,
        }}
      >
        {tabs[activeTab].content}
      </div>
    </div>
  );
}