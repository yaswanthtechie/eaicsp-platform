import type { Preview } from "@storybook/react-vite";
import "../src/theme/variables.css";

const preview: Preview = {
  tags: ["autodocs"],

  globalTypes: {
    theme: {
      name: "Theme",
      description: "Global theme for components",
      defaultValue: "light",
      toolbar: {
        icon: "paintbrush",
        items: [
          { value: "light", title: "Light" },
          { value: "dark", title: "Dark" },
          { value: "high-contrast", title: "High Contrast" },
        ],
        dynamicTitle: true,
      },
    },
  },

  decorators: [
    (Story, context) => {
      const theme = context.globals.theme || "light";

      document.documentElement.setAttribute("data-theme", theme);

      return (
        <div
          style={{
            minHeight: "100vh",
            background: "var(--color-background)",
            color: "var(--color-text)",
            padding: "24px",
          }}
        >
          <Story />
        </div>
      );
    },
  ],

  parameters: {
    a11y: {
      test: "error",
    },
  },
};

export default preview;