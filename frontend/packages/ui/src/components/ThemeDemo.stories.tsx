import type { Meta, StoryObj } from "@storybook/react";
import { Button } from "./Button";
import { Card } from "./Card";
import { Badge } from "./Badge";
import { Tabs } from "./Tabs";

const meta = {
  title: "Theme/High Contrast Demo",
} satisfies Meta;

export default meta;

type Story = StoryObj<typeof meta>;

export const HighContrastDemo: Story = {
  render: () => (
    <div
      data-theme="high-contrast"
      style={{
        minHeight: "500px",
        padding: "24px",
        background: "var(--color-background)",
        color: "var(--color-text)",
      }}
    >
      <h2>High Contrast Theme Demo</h2>

      <div
        style={{
          display: "flex",
          gap: "16px",
          marginBottom: "24px",
        }}
      >
        <Button>Primary Button</Button>

        <Badge status="info">
          Badge
        </Badge>
      </div>

      <Card>
        <h3>Card</h3>
        <p>
          This card uses the centralized theme tokens.
        </p>
      </Card>

      <div style={{ marginTop: "24px" }}>
        <Tabs
          items={[
            {
              value: "one",
              label: "First",
              content: "First tab content",
            },
            {
              value: "two",
              label: "Second",
              content: "Second tab content",
            },
          ]}
        />
      </div>
    </div>
  ),
};