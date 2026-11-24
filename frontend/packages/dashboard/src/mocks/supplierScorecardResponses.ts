import type { SupplierScorecardRow } from "../api/supplierScorecard";

// Suppliers, names and sanctions status come from
// data-platform/seed/samples/suppliers.csv. Sanctioned suppliers get the
// Critical / 85 result the real risk endpoint returns for them.
export const supplierScorecardResponse: SupplierScorecardRow[] = [
  {
    supplier_id: "SUP-00007",
    supplier_name: "ALPHA SANCTIONS CORP",
    on_time_delivery_percent: 81,
    risk_error: null,
    risk: {
      supplier_id: "SUP-00007",
      score: 85,
      tier: "Critical",
      top_reasons: [
        "Designated on OFAC-SDN (critical compliance risk)",
        "3 delay incidents in 12 months",
        "Recent incident occurred 9 days ago",
      ],
      client_risk_features: {
        quality_incidents_12m: 1,
        delay_incidents_12m: 3,
        dispute_incidents_12m: 0,
        other_incidents_12m: 0,
        days_since_last_incident: 9,
        on_time_delivery_pct: 81,
        on_time_delivery_missing: false,
      },
    },
  },
  {
    supplier_id: "SUP-00023",
    supplier_name: "TEST EU ENTITY 01",
    on_time_delivery_percent: null,
    risk_error: null,
    risk: {
      supplier_id: "SUP-00023",
      score: 85,
      tier: "Critical",
      top_reasons: ["Designated on EU-CONSOLIDATED (critical compliance risk)"],
      client_risk_features: null,
    },
  },
  {
    supplier_id: "SUP-00022",
    supplier_name: "Bluepeak Enterprises Inc",
    on_time_delivery_percent: 88,
    risk_error: null,
    risk: {
      supplier_id: "SUP-00022",
      score: 48,
      tier: "Medium",
      top_reasons: [
        "4 delay incidents in 12 months",
        "On-time delivery rate is 88%",
        "1 dispute incident in 12 months",
      ],
      client_risk_features: {
        quality_incidents_12m: 0,
        delay_incidents_12m: 4,
        dispute_incidents_12m: 1,
        other_incidents_12m: 0,
        days_since_last_incident: 21,
        on_time_delivery_pct: 88,
        on_time_delivery_missing: false,
      },
    },
  },
  {
    supplier_id: "SUP-00019",
    supplier_name: "Unity Manufacturing GmbH",
    on_time_delivery_percent: 98,
    risk_error: null,
    risk: {
      supplier_id: "SUP-00019",
      score: 18,
      tier: "Low",
      top_reasons: ["No incidents in 12 months", "On-time delivery rate is 98%"],
      client_risk_features: {
        quality_incidents_12m: 0,
        delay_incidents_12m: 0,
        dispute_incidents_12m: 0,
        other_incidents_12m: 0,
        days_since_last_incident: null,
        on_time_delivery_pct: 98,
        on_time_delivery_missing: false,
      },
    },
  },
  {
    // Known supplier with no evidence: the contract returns score and tier null.
    supplier_id: "SUP-00021",
    supplier_name: "Evergreen Supplies GmbH",
    on_time_delivery_percent: null,
    risk_error: null,
    risk: {
      supplier_id: "SUP-00021",
      score: null,
      tier: null,
      top_reasons: [],
      client_risk_features: null,
    },
  },
];