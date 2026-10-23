import axios, { AxiosError } from "axios";

import type { Alert, AppUser, Bill, LoginPayload, Reading, RegisterPayload } from "@/types";

const API_BASE_URL = process.env.NEXT_PUBLIC_API_BASE_URL?.trim() || "http://localhost:8000";

const AUTH_TOKEN_KEY = "sems.auth.token";
const AUTH_USER_KEY = "sems.auth.user";

type ApiErrorPayload = {
    detail?: unknown;
    message?: string;
};

export type DashboardData = {
    total_users: number;
    total_units: number;
    total_readings: number;
    active_alerts: number;
};

export type ReadingPayload = {
    user_id: number;
    previous_reading: number;
    current_reading: number;
    reading_date?: string;
};

export type AuthResponse = {
    token: string;
    user: AppUser;
};

type RawAlert = {
    id: number;
    user_id: number;
    message?: string;
    explanation?: string;
    percentage_increase?: number | null;
    status?: string;
    resolved_at?: string | null;
    type?: string;
    timestamp: string;
    resolved?: boolean;
};

type RawBill = {
    id: number | string;
    user_id: number;
    total_units?: number;
    predicted_amount?: number;
    timestamp?: string;
    month: string;
};

type RawDashboardStats = {
    area_average_usage?: number;
    area_comparison_text?: string;
    peak_usage_text?: string;
    efficiency_score?: number;
    hardware_status?: "online" | "offline";
    last_sync_timestamp?: string | null;
    latest_telemetry?: import("@/types").HardwareTelemetry | null;
    tier_breakdown?: import("@/types").TierBreakdown | null;
    predicted_bill_this_month?: number;
};

const api = axios.create({
    baseURL: API_BASE_URL,
    timeout: 10000,
    headers: {
        "Content-Type": "application/json",
    },
});

const canUseStorage = () => typeof window !== "undefined";

api.interceptors.request.use((config) => {
    if (canUseStorage()) {
        const token = window.localStorage.getItem(AUTH_TOKEN_KEY);
        if (token) {
            config.headers.Authorization = `Bearer ${token}`;
        }
    }
    return config;
});

api.interceptors.response.use(
    (response) => response,
    (error) => Promise.reject(error),
);

export const toApiErrorMessage = (error: unknown): string => {
    if (axios.isAxiosError(error)) {
        const axiosError = error as AxiosError<ApiErrorPayload>;
        const status = axiosError.response?.status;
        const payload = axiosError.response?.data;

        if (Array.isArray(payload?.detail)) {
            const details = payload.detail
                .map((item) => {
                    if (typeof item === "object" && item !== null) {
                        const record = item as { msg?: string; loc?: Array<string | number> };
                        const fieldPath = Array.isArray(record.loc) ? record.loc.join(".") : "field";
                        return record.msg ? `${fieldPath}: ${record.msg}` : JSON.stringify(item);
                    }
                    return String(item);
                })
                .join("; ");
            return `${status ?? "HTTP"} ${details}`;
        }

        if (typeof payload?.detail === "string") {
            return `${status ?? "HTTP"} ${payload.detail}`;
        }

        if (typeof payload?.message === "string") {
            return `${status ?? "HTTP"} ${payload.message}`;
        }

        return axiosError.message;
    }

    if (error instanceof Error) {
        return error.message;
    }

    return "Unexpected API error";
};

const buildAnomalyReason = (percentageIncrease: number): string => {
    if (percentageIncrease > 0) {
        return `Your usage increased by ${percentageIncrease.toFixed(2)}% compared to your average.`;
    }
    if (percentageIncrease < 0) {
        return `Your usage decreased by ${Math.abs(percentageIncrease).toFixed(2)}% compared to your average.`;
    }
    return "Your usage is unchanged compared to your average.";
};

const normalizeAlert = (alert: RawAlert): Alert => {
    const rawPercentage = alert.percentage_increase;
    const percentageIncrease =
        typeof rawPercentage === "number" && Number.isFinite(rawPercentage)
            ? Number(rawPercentage.toFixed(2))
            : null;
    const explanation =
        alert.explanation ||
        (percentageIncrease === null ? "Insufficient data" : buildAnomalyReason(percentageIncrease));

    const resolvedFromStatus = alert.status === "resolved";

    return {
        id: alert.id,
        user_id: alert.user_id,
        message: alert.message || "Unusual high consumption detected",
        explanation,
        percentage_increase: percentageIncrease,
        status: alert.status === "resolved" ? "resolved" : "open",
        resolved_at: alert.resolved_at ?? null,
        type: alert.type || "high-usage",
        timestamp: alert.timestamp,
        resolved: resolvedFromStatus || Boolean(alert.resolved),
    };
};

export const authStorage = {
    tokenKey: AUTH_TOKEN_KEY,
    userKey: AUTH_USER_KEY,
};

export const loginUser = async (payload: LoginPayload): Promise<AuthResponse> => {
    const response = await api.post<{ access_token?: string; token?: string; user?: AppUser }>("/auth/login", payload);
    const token = response.data.access_token || response.data.token;
    if (!token || !response.data.user) {
        throw new Error("Authentication response is invalid");
    }

    return {
        token,
        user: response.data.user,
    };
};

export const registerUser = async (payload: RegisterPayload): Promise<AuthResponse> => {
    if (payload.role && payload.role !== "user") {
        throw new Error("New admin accounts cannot be created from the frontend.");
    }

    const response = await api.post<{ access_token?: string; token?: string; user?: AppUser }>("/auth/register", {
        ...payload,
        role: "user" as const,
    });
    const token = response.data.access_token || response.data.token;
    if (!token || !response.data.user) {
        throw new Error("Authentication response is invalid");
    }

    return {
        token,
        user: {
            ...response.data.user,
            role: response.data.user.role || "user",
        },
    };
};

export const getUsers = async (): Promise<AppUser[]> => {
    const response = await api.get<AppUser[]>("/users");
    return response.data;
};

export const createUser = async (payload: RegisterPayload): Promise<AppUser> => {
    if (payload.role && payload.role !== "user") {
        throw new Error("New admin accounts cannot be created from the frontend.");
    }

    const response = await api.post<AppUser>("/users", {
        ...payload,
        role: "user" as const,
    });
    return response.data;
};

export const getAllReadings = async (): Promise<Reading[]> => {
    const response = await api.get<Reading[]>("/readings");
    return response.data;
};

export const getUserReadings = async (userId: number): Promise<Reading[]> => {
    const response = await api.get<Reading[]>(`/meter/history/${userId}`);
    return response.data;
};

export const addMeterReading = async (payload: ReadingPayload): Promise<Reading> => {
    const response = await api.post<{ units_consumed?: number; is_anomaly?: boolean }>("/meter/add-reading", {
        user_id: payload.user_id,
        previous_reading: payload.previous_reading,
        current_reading: payload.current_reading,
        reading_date: payload.reading_date,
    });

    return {
        id: Date.now(),
        user_id: payload.user_id,
        units: response.data.units_consumed ?? (payload.current_reading - payload.previous_reading),
        load_value: payload.current_reading,
        timestamp: payload.reading_date || new Date().toISOString(),
        is_anomaly: response.data.is_anomaly ?? false,
    };
};

export const getAllBills = async (): Promise<Bill[]> => {
    return [];
};

export const getUserBills = async (userId: number): Promise<Bill[]> => {
    const response = await api.get<RawBill[]>(`/meter/bills/${userId}`);
    return response.data.map((bill) => ({
        id: String(bill.id),
        user_id: bill.user_id,
        units: bill.total_units ?? 0,
        bill_amount: bill.predicted_amount ?? 0,
        status: "generated",
        generated_date: bill.timestamp || new Date(bill.month + "-02").toISOString(),
        month: bill.month,
    }));
};

export const clearAllBillsData = async (): Promise<{ message: string }> => {
    const response = await api.delete<{ message: string }>("/admin/clear-bills");
    return response.data;
};

export const resetDemoSystem = async (): Promise<{ message: string }> => {
    const response = await api.delete<{ message: string }>("/admin/reset-system");
    return response.data;
};

export const generateDemoData = async (): Promise<{ message: string }> => {
    const response = await api.post<{ message: string }>("/admin/generate-demo-data", {});
    return response.data;
};

export const generateBillForUser = async (userId: number): Promise<Bill> => {
    const now = new Date();
    const year = now.getFullYear();
    const targetMonth = now.getMonth() + 1;

    const response = await api.post<{
        month?: string;
        total_units?: number;
        predicted_amount?: number;
        amount?: number;
    }>(`/meter/generate-bill/${userId}?year=${year}&month=${targetMonth}`);

    const month = response.data.month || `${year}-${String(targetMonth).padStart(2, "0")}`;
    const units = Number(response.data.total_units ?? 0);
    const amount = Number(response.data.predicted_amount ?? response.data.amount ?? 0);

    return {
        id: `B-${Date.now()}`,
        user_id: userId,
        units,
        bill_amount: Number(amount.toFixed(2)),
        status: "generated",
        generated_date: new Date().toISOString(),
        month,
    };
};

export const getAllAlerts = async (): Promise<Alert[]> => {
    const response = await api.get<RawAlert[]>("/alerts");
    return response.data.map((alert) => normalizeAlert(alert));
};

export const getUserAlerts = async (userId: number): Promise<Alert[]> => {
    const response = await api.get<RawAlert[]>(`/meter/alerts/${userId}`);
    return response.data.map((alert) => normalizeAlert(alert));
};

export const resolveAlert = async (alertId: number): Promise<void> => {
    await api.put(`/admin/alerts/${alertId}/resolve`);
};

export const getDashboardData = async (): Promise<DashboardData> => {
    const response = await api.get<DashboardData>("/dashboard");
    return response.data;
};

export const getUserDashboard = async (userId: number) => {
    const [readings, bills, alerts, statsRes] = await Promise.all([
        getUserReadings(userId),
        getUserBills(userId),
        getUserAlerts(userId),
        api.get<RawDashboardStats>(`/meter/dashboard/${userId}`),
    ]);

    const totalUnits = readings.reduce((sum, item) => sum + Number(item.units), 0);
    const currentMonth = new Date().getMonth();
    const currentYear = new Date().getFullYear();

    const currentMonthUsage = readings
        .filter((reading) => {
            const date = new Date(reading.timestamp);
            return date.getMonth() === currentMonth && date.getFullYear() === currentYear;
        })
        .reduce((sum, item) => sum + Number(item.units), 0);

    const sortedBills = [...bills].sort(
        (a, b) => new Date(b.generated_date).getTime() - new Date(a.generated_date).getTime(),
    );

    return {
        totalUnits,
        currentMonthUsage,
        lastBillAmount: sortedBills[0]?.bill_amount ?? 0,
        predictedBillThisMonth: statsRes.data.predicted_bill_this_month ?? 0,
        readings,
        bills,
        alerts,
        areaAverageUsage: statsRes.data.area_average_usage ?? 0,
        areaComparisonText: statsRes.data.area_comparison_text ?? "No data available",
        peakUsageText: statsRes.data.peak_usage_text ?? "No data available",
        efficiencyScore: statsRes.data.efficiency_score ?? 100,
        hardwareStatus: statsRes.data.hardware_status ?? "offline",
        lastSyncTimestamp: statsRes.data.last_sync_timestamp ?? null,
        latestTelemetry: statsRes.data.latest_telemetry ?? null,
        tierBreakdown: statsRes.data.tier_breakdown ?? null,
    };
};
