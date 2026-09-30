import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import SupplierRisk from "../components/SupplierRisk";

vi.mock("../components/Skeleton", () => ({
  default: ({
    width,
    height,
  }: {
    width: string;
    height: number;
  }) => <div data-testid="skeleton">{width}-{height}</div>,
}));

const mockSupplierRisk = [
  {
    supplier: "BlinkIt",
    risk_score: 0.25,
    confidence: 0.91,
    sentiment_breakdown: {
      positive: 0.6,
      negative: 0.1,
      neutral: 0.3,
    },
  },
  {
    supplier: "DMart",
    risk_score: 0.52,
    confidence: 0.88,
    sentiment_breakdown: {
      positive: 0.3,
      negative: 0.4,
      neutral: 0.3,
    },
  },
  {
    supplier: "Big Basket",
    risk_score: 0.81,
    confidence: 0.94,
    sentiment_breakdown: {
      positive: 0.1,
      negative: 0.7,
      neutral: 0.2,
    },
  },
  {
    supplier: "Wholesale Shop",
    risk_score: 0.18,
    confidence: 0.89,
    sentiment_breakdown: {
      positive: 0.7,
      negative: 0.1,
      neutral: 0.2,
    },
  },
];

describe("SupplierRisk", () => {
  const defaultProps = {
    supplierRisk: mockSupplierRisk,
    loading: false,
    error: false,
    onRetry: vi.fn(),
  };

  it("shows loading skeleton while loading", () => {
    render(
      <SupplierRisk
        {...defaultProps}
        loading={true}
      />
    );

    expect(screen.getAllByTestId("skeleton")).toHaveLength(2);
  });

  it("shows supplier risk summary after loading", () => {
    render(<SupplierRisk {...defaultProps} />);

    expect(screen.getByText("Supplier Risk Summary")).toBeInTheDocument();
    expect(
      screen.getByText("Risk score and model confidence by supplier")
    ).toBeInTheDocument();
  });

  it("shows supplier names", () => {
    render(<SupplierRisk {...defaultProps} />);

    expect(screen.getByText("BlinkIt")).toBeInTheDocument();
    expect(screen.getByText("DMart")).toBeInTheDocument();
    expect(screen.getByText("Big Basket")).toBeInTheDocument();
    expect(screen.getByText("Wholesale Shop")).toBeInTheDocument();
  });

  it("shows risk levels", () => {
    render(<SupplierRisk {...defaultProps} />);

    expect(screen.getAllByText("High Risk").length).toBeGreaterThan(0);
    expect(screen.getAllByText("Medium Risk").length).toBeGreaterThan(0);
    expect(screen.getAllByText("Low Risk").length).toBeGreaterThan(0);
  });

  it("shows risk score and confidence labels", () => {
    render(<SupplierRisk {...defaultProps} />);

    expect(screen.getAllByText("Risk Score").length).toBeGreaterThan(0);
    expect(screen.getAllByText("Confidence").length).toBeGreaterThan(0);
  });

  it("shows sentiment information", () => {
    render(<SupplierRisk {...defaultProps} />);

    expect(screen.getAllByText("Sentiment").length).toBeGreaterThan(0);
    expect(screen.getAllByText(/Positive/).length).toBeGreaterThan(0);
    expect(screen.getAllByText(/Negative/).length).toBeGreaterThan(0);
    expect(screen.getAllByText(/Neutral/).length).toBeGreaterThan(0);
  });

  it("shows percentage values", () => {
    render(<SupplierRisk {...defaultProps} />);

    expect(screen.getAllByText(/\d+%/).length).toBeGreaterThan(0);
  });

  it("shows error state when supplier risk fails", () => {
    const onRetry = vi.fn();

    render(
      <SupplierRisk
        {...defaultProps}
        supplierRisk={[]}
        error={true}
        onRetry={onRetry}
      />
    );

    expect(
      screen.getByText("Failed to load supplier risk.")
    ).toBeInTheDocument();

    expect(screen.getByRole("button", { name: "Retry" })).toBeInTheDocument();
  });
});

