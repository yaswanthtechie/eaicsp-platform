export type UserRole = "ceo" | "warehouse_manager";

export interface MockUser {
    role: UserRole;
    warehouse?: string;
}

export const mockUser: MockUser = {
    role: "ceo",
    warehouse: "WH001"
};