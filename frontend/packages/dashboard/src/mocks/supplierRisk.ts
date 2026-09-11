import type { SupplierRiskItem } from "../types/dashboard";

export const supplierRisk: SupplierRiskItem[] = [
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