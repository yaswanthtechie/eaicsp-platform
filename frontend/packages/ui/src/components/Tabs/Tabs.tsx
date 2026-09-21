import React, {
  useRef,
  useState,
  type KeyboardEvent,
} from "react";
import "./Tabs.css";

export interface TabItem {
  value: string;
  label: string;
  content: React.ReactNode;
  disabled?: boolean;
}

export interface TabsProps {
  items: TabItem[];

  // Controlled mode
  value?: string;

  // Uncontrolled mode
  defaultValue?: string;

  onChange?: (value: string) => void;
}

export function Tabs({
  items,
  value,
  defaultValue,
  onChange,
}: TabsProps) {
  const firstTab = items.find(
    (item) => !item.disabled
  )?.value;

  const [internalValue, setInternalValue] = useState(
    defaultValue ?? firstTab
  );

  const activeValue = value ?? internalValue;

  const tabRefs = useRef<
    Record<string, HTMLButtonElement | null>
  >({});

  const handleChange = (tabValue: string) => {
    const selectedTab = items.find(
      (item) => item.value === tabValue
    );

    if (!selectedTab || selectedTab.disabled) {
      return;
    }

    if (value === undefined) {
      setInternalValue(tabValue);
    }

    onChange?.(tabValue);
  };

  const handleKeyDown = (
    event: KeyboardEvent<HTMLButtonElement>,
    currentValue: string
  ) => {
    const enabledTabs = items.filter(
      (item) => !item.disabled
    );

    if (enabledTabs.length === 0) {
      return;
    }

    const currentIndex = enabledTabs.findIndex(
      (item) => item.value === currentValue
    );

    if (currentIndex === -1) {
      return;
    }

    let nextIndex: number;

    switch (event.key) {
      case "ArrowRight":
        nextIndex =
          (currentIndex + 1) % enabledTabs.length;
        break;

      case "ArrowLeft":
        nextIndex =
          (currentIndex - 1 + enabledTabs.length) %
          enabledTabs.length;
        break;

      case "Home":
        nextIndex = 0;
        break;

      case "End":
        nextIndex = enabledTabs.length - 1;
        break;

      default:
        return;
    }

    event.preventDefault();

    const nextTab = enabledTabs[nextIndex];

    handleChange(nextTab.value);

    requestAnimationFrame(() => {
      tabRefs.current[nextTab.value]?.focus();
    });
  };

  const activeTab = items.find(
    (item) => item.value === activeValue
  );

  const activeTabId = `tab-${activeValue}`;
  const activePanelId = `tabpanel-${activeValue}`;

  return (
    <div className="tabs">
      <div
        className="tabs-list"
        role="tablist"
        aria-label="Tabs"
      >
        {items.map((item) => {
          const isActive =
            item.value === activeValue;

          const tabId = `tab-${item.value}`;
          const panelId = `tabpanel-${item.value}`;

          return (
            <button
              key={item.value}
              ref={(element) => {
                tabRefs.current[item.value] = element;
              }}
              id={tabId}
              type="button"
              role="tab"
              className={
                isActive
                  ? "tabs-button tabs-active"
                  : "tabs-button"
              }
              aria-selected={isActive}
              aria-controls={panelId}
              tabIndex={isActive ? 0 : -1}
              disabled={item.disabled}
              onClick={() =>
                handleChange(item.value)
              }
              onKeyDown={(event) =>
                handleKeyDown(
                  event,
                  item.value
                )
              }
            >
              {item.label}
            </button>
          );
        })}
      </div>

      <div
        id={activePanelId}
        className="tabs-panel"
        role="tabpanel"
        aria-labelledby={activeTabId}
        tabIndex={0}
      >
        {activeTab?.content}
      </div>
    </div>
  );
}