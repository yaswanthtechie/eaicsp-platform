
import type { SupplierScorecardRow } from "../api/supplierScoreCard";

export const supplierScorecardResponse: SupplierScorecardRow[] = [
  {
    supplier_id: "SUP-00001",
    supplier_name: "Alpha Technologies",
    on_time_delivery_percent: 96,
    risk_error: null,
    risk: {
      supplier_id: "SUP-00001",
      score: 85,
      tier: "Critical",
      top_reasons: [
        "High number of quality incidents in the last 12 months",
        "Repeated delays in supplier deliveries",
        "Multiple supplier disputes reported",
      ],
      client_risk_features: {
        quality_incidents_12m: 4,
        delay_incidents_12m: 3,
        dispute_incidents_12m: 2,
        other_incidents_12m: 0,
        days_since_last_incident: 5,
        on_time_delivery_pct: 96,
        on_time_delivery_missing: false,
      },
    },
  },
  {
    supplier_id: "SUP-00002",
    supplier_name: "Brightstar Components",
    on_time_delivery_percent: 88,
    risk_error: null,
    risk: {
      supplier_id: "SUP-00002",
      score: 72,
      tier: "High",
      top_reasons: [
        "Frequent delivery delays affecting order fulfilment",
        "Quality issues reported in recent shipments",
        "Supplier disputes recorded during the last 12 months",
      ],
      client_risk_features: {
        quality_incidents_12m: 2,
        delay_incidents_12m: 4,
        dispute_incidents_12m: 1,
        other_incidents_12m: 0,
        days_since_last_incident: 12,
        on_time_delivery_pct: 88,
        on_time_delivery_missing: false,
      },
    },
  },
  {
    supplier_id: "SUP-00007",
    supplier_name: "ALPHA SANCTIONS CORP",
    on_time_delivery_percent: 92,
    risk_error: null,
    risk: {
      supplier_id: "SUP-00007",
      score: 48,
      tier: "Medium",
      top_reasons: [
        "Occasional delays in purchase order deliveries",
        "Quality incidents reported during the last 12 months",
        "One supplier dispute requiring monitoring",
      ],
      client_risk_features: {
        quality_incidents_12m: 1,
        delay_incidents_12m: 2,
        dispute_incidents_12m: 1,
        other_incidents_12m: 0,
        days_since_last_incident: 35,
        on_time_delivery_pct: 92,
        on_time_delivery_missing: false,
      },
    },
  },
  {
    supplier_id: "SUP-00023",
    supplier_name: "TEST EU ENTITY 01",
    on_time_delivery_percent: 99,
    risk_error: null,
    risk: {
      supplier_id: "SUP-00023",
      score: 20,
      tier: "Low",
      top_reasons: [
        "No quality incidents reported in the last 12 months",
        "No delivery delay incidents recorded",
        "No supplier disputes reported",
      ],
      client_risk_features: {
        quality_incidents_12m: 0,
        delay_incidents_12m: 0,
        dispute_incidents_12m: 0,
        other_incidents_12m: 0,
        days_since_last_incident: 180,
        on_time_delivery_pct: 99,
        on_time_delivery_missing: false,
      },
    },
  },
  {
    supplier_id: "SUP-00045",
    supplier_name: "TEST UN ENTITY 01",
    on_time_delivery_percent: null,
    risk_error: null,
    risk: {
      supplier_id: "SUP-00045",
      score: null,
      tier: null,
      top_reasons: [
        "Risk assessment data is not available",
        "Supplier incident history has not been provided",
        "On-time delivery performance is not tracked",
      ],
      client_risk_features: null,
    },
  },
];
