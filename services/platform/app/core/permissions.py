PERMISSIONS = {
    "inventory:read",
    "inventory:write",
    "compliance:read",
    "compliance:write",
    "supplier:read",
    "supplier:write",
    "logistics:read",
    "logistics:write",
}

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
}
