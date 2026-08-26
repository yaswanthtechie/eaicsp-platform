import type { Meta, StoryObj } from "@storybook/react";
import { Button } from "./Button";
import { Card } from "./Card";
import { Badge } from "./Badge";
import { AlertBanner } from "./AlertBanner";
import { StatusIndicator } from "./StatusIndicator";

const meta = {
  title: "Theme/High Contrast",
} satisfies Meta;

export default meta;

type Story = StoryObj<typeof meta>;

export const HighContrast: Story = {
  render: () => {
    document.documentElement.setAttribute(
      "data-theme",
      "high-contrast"
    );

    return (
      <div
        style={{
          display: "grid",
          gap: "16px",
          padding: "24px",
          background: "var(--color-background)",
          color: "var(--color-text)",
        }}
      >
        <h2>High Contrast Theme</h2>

        <Button>Primary Button</Button>

        <Card>
          <h3>Card</h3>
          <p>Card using high-contrast design tokens.</p>
        </Card>

        <Badge status="info">
          Badge
        </Badge>

        <AlertBanner
          type="warning"
          title="Important alert"
          message="This alert demonstrates the high-contrast theme."
        />

        <StatusIndicator status="success" />
      </div>
    );
  },
};
