import React, { useState } from "react";
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


  const [internalValue, setInternalValue] =
    useState(
      defaultValue ?? firstTab
    );


  const activeValue =
    value ?? internalValue;


  const handleChange = (tabValue: string) => {

    if (value === undefined) {
      setInternalValue(tabValue);
    }

    onChange?.(tabValue);
  };


  const activeTab = items.find(
    (item) => item.value === activeValue
  );


  return (
    <div className="tabs">

      <div
        className="tabs-list"
        role="tablist"
      >

        {items.map((item) => (

          <button
            key={item.value}
            type="button"
            role="tab"
            className={
              item.value === activeValue
                ? "tabs-button tabs-active"
                : "tabs-button"
            }
            aria-selected={
              item.value === activeValue
            }
            disabled={item.disabled}
            onClick={() =>
              handleChange(item.value)
            }
          >
            {item.label}
          </button>

        ))}

      </div>


      <div
        className="tabs-panel"
        role="tabpanel"
      >

        {activeTab?.content}

      </div>


    </div>
  );
}