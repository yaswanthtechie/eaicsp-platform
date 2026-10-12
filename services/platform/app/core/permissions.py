PERMISSIONS = {
    "inventory:read",
    "inventory:write",
    "compliance:read",
    "compliance:write",
    "supplier:read",
    "supplier:write",
    "logistics:read",
    "logistics:write",

    # -------------------------
    # Milestone 2 permissions
    # -------------------------
    "purchase_order:create",
    "purchase_order:read",
    "purchase_order:approve",
    "inventory:plan",
    "demand:read",
    "demand:write",
    "invoice:read",
    "invoice:approve",
    "payment:approve",
    "risk:read",
    "model:read",
    "model:retrain",
    "model:promote_staging",
    "audit:read",
    "user:read",
    "user:manage",
    "role:assign",
    "inventory:move",
    "shipment:read",
}

# ---------------------------------------------------------
# V1 ROLES — DO NOT CHANGE
# ---------------------------------------------------------
ROLE_PERMISSIONS = {
    "ceo": {
        "inventory:read",
        "inventory:write",
        "compliance:read",
        "compliance:write",
        "supplier:read",
        "supplier:write",
        "logistics:read",
        "logistics:write",
    },

    "vp_operations": {
        "inventory:read",
        "inventory:write",
        "compliance:read",
        "compliance:write",
        "supplier:read",
        "supplier:write",
        "logistics:read",
        "logistics:write",
    },

    "procurement_manager": {
        "supplier:read",
        "supplier:write",
    },

    "logistics_manager": {
        "logistics:read",
        "logistics:write",
    },

    "compliance_officer": {
        "compliance:read",
        "compliance:write",
    },

    "warehouse_manager": {
        "inventory:read",
        "inventory:write",
    },

    "analyst": {
        "inventory:read",
        "compliance:read",
        "supplier:read",
        "logistics:read",
    },

    "supplier": {
        "supplier:read",
        "supplier:write",
    },

    # ========================================================
    # V2 ROLES
    # ========================================================
    # Platform administration.
    # Manages platform users and role assignments.
    # Does NOT automatically receive business-data permissions.
    "platform_admin": {
        "audit:read",
        "user:read",
        "user:manage",
        "role:assign",
    },

    # Day-to-day procurement work.
    # Can create/read POs but cannot approve them.
    "procurement_officer": {
        "purchase_order:create",
        "purchase_order:read",
        "supplier:read",
    },

    # Inventory planning and reorder planning.
    "inventory_planner": {
        "inventory:read",
        "inventory:plan",
    },

    # Demand/forecast planning.
    "demand_planner": {
        "demand:read",
        "demand:write",
        "inventory:read",
    },

    # Finance operations.
    "finance_manager": {
        "invoice:read",
        "invoice:approve",
        "payment:approve",
    },

    # Supplier risk analysis.
    "risk_analyst": {
        "supplier:read",
        "risk:read",
    },

    # ML/data science activities.
    # Promotion is restricted to staging.
    "data_scientist": {
        "model:read",
        "model:retrain",
        "model:promote_staging",
    },

    # Read-only audit access.
    "auditor": {
        "audit:read",
        "inventory:read",
        "compliance:read",
        "supplier:read",
        "logistics:read",
        "purchase_order:read",
        "invoice:read",
        "risk:read",
        "model:read",
        "demand:read",
    },

    # Warehouse floor operations.
    # Only stock movement capability is added here.
    "warehouse_operator": {
        "inventory:read",
        "inventory:move",
    },

    # External carrier.
    # Shipment visibility only.
    "carrier": {
        "shipment:read",
    },
}
