import { useEffect, useState, type ReactNode } from "react";
import { colors, space, radius } from "../tokens";

export interface Tab {
  label: string;
  content: ReactNode;
}

export interface TabsProps {
  tabs: Tab[];
}

export function Tabs({ tabs }: TabsProps) {
  const [activeTab, setActiveTab] = useState(0);

  // Reset active tab if the tabs array becomes shorter
  useEffect(() => {
    if (activeTab >= tabs.length) {
      setActiveTab(0);
    }
  }, [tabs, activeTab]);

  // Prevent crashes when there are no tabs
  if (tabs.length === 0) {
    return (
      <div
        style={{
          border: `1px solid ${colors.border}`,
          borderRadius: radius.md,
          padding: space.lg,
          backgroundColor: colors.surface,
          color: colors.text,
          textAlign: "center",
        }}
      >
        No tabs available.
      </div>
    );
  }

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
            type="button"
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
                  ? colors.textInverse
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
        {tabs[activeTab]?.content}
      </div>
    </div>
  );
}