export type UserRole = "user" | "admin";

export type AppUser = {
    id: number;
    name: string;
    email: string;
    area: string;
    role: UserRole;
};

export type RegisterPayload = {
    name: string;
    email: string;
    password: string;
    area: string;
    role?: UserRole;
};

export type LoginPayload = {
    email: string;
    password: string;
};

export type DashboardStat = {
    label: string;
    value: string | number;
    hint?: string;
};

export type Reading = {
    id: number;
    user_id: number;
    units: number;
    load_value: number;
    voltage?: number | null;
    current_mA?: number | null;
    power_w?: number | null;
    timestamp: string;
    is_anomaly: boolean;
};

export type HardwareTelemetry = {
    voltage?: number | null;
    current_mA?: number | null;
    power_w?: number | null;
    load_value?: number | null;
    units?: number | null;
    timestamp?: string | null;
};

export type TierSlab = {
    label: string;
    units: number;
    rate: number;
    amount: number;
};

export type TierBreakdown = {
    tier1: TierSlab;
    tier2: TierSlab;
    tier3: TierSlab;
    total_units: number;
    total_amount: number;
};

export type Bill = {
    id: string;
    user_id: number;
    units: number;
    bill_amount: number;
    status: string;
    generated_date: string;
    month: string;
};

export type Alert = {
    id: number;
    user_id: number;
    message: string;
    explanation: string;
    percentage_increase: number | null;
    status?: "open" | "resolved";
    resolved_at?: string | null;
    type: string;
    timestamp: string;
    resolved: boolean;
};
