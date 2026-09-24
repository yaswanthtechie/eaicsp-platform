import { Component, type ReactNode } from "react";

import { colors, radius, space } from "../tokens";

interface Props {
  children: ReactNode;
}

interface State {
  hasError: boolean;
}

export default class ErrorBoundary extends Component<Props, State> {
  state: State = {
    hasError: false,
  };

  static getDerivedStateFromError(): State {
    return {
      hasError: true,
    };
  }

  handleRetry = () => {
    this.setState({
      hasError: false,
    });
  };

  render() {
    if (this.state.hasError) {
      return (
        <div
          style={{
            padding: space.lg,
            border: `1px solid ${colors.danger}`,
            borderRadius: radius.md,
            background: colors.surface,
            color: colors.text,
          }}
        >
          <h2>Something went wrong</h2>

          <p style={{ color: colors.textMuted }}>
            Unable to load this widget.
          </p>

          <button onClick={this.handleRetry}>Retry</button>
        </div>
      );
    }

    return this.props.children;
  }
}