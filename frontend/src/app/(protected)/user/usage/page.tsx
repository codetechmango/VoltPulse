"use client";

import { useEffect, useMemo, useState } from "react";

import DataTable from "@/components/ui/DataTable";
import EmptyState from "@/components/ui/EmptyState";
import ErrorMessage from "@/components/ui/ErrorMessage";
import PageHeader from "@/components/ui/PageHeader";
import { useAuth } from "@/context/AuthContext";
import { getUserReadings, toApiErrorMessage } from "@/services/api";
import type { Reading } from "@/types";

type ReadingRow = {
    id: number;
    date: string;
    units: string;
    voltage: string;
    current: string;
    power: string;
    anomaly: string;
};

export default function UserUsagePage() {
    const { user } = useAuth();
    const [readings, setReadings] = useState<Reading[]>([]);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState("");

    useEffect(() => {
        const load = async () => {
            if (!user) {
                return;
            }

            setLoading(true);
            setError("");
            try {
                setReadings(await getUserReadings(user.id));
            } catch (err) {
                setError(toApiErrorMessage(err));
            } finally {
                setLoading(false);
            }
        };

        void load();
    }, [user]);

    const rows = useMemo<ReadingRow[]>(
        () =>
            readings.map((reading) => ({
                id: reading.id,
                date: new Date(reading.timestamp).toLocaleString(),
                units: Number(reading.units).toFixed(4),
                voltage: reading.voltage != null ? `${Number(reading.voltage).toFixed(2)} V` : "-",
                current: reading.current_mA != null ? `${Number(reading.current_mA).toFixed(1)} mA` : "-",
                power: reading.power_w != null ? `${Number(reading.power_w).toFixed(2)} W` : "-",
                anomaly: reading.is_anomaly ? "Yes" : "No",
            })),
        [readings],
    );

    return (
        <section className="space-y-6">
            <PageHeader title="Usage & Hardware Telemetry" description="Live and historical meter readings, INA219 telemetry, and anomaly detections." />

            {error ? (
                <ErrorMessage
                    title="Unable to load usage history"
                    message={error || "We could not fetch your readings right now. Please retry."}
                />
            ) : null}

            {!loading && rows.length === 0 ? (
                <EmptyState
                    title="No readings yet"
                    description="Your meter readings will appear once captured by the system or transmitted by your ESP32."
                />
            ) : (
                <DataTable
                    title="Meter Reading & Hardware Sensor Log"
                    rows={rows}
                    loading={loading}
                    emptyMessage="No readings yet"
                    columns={[
                        { key: "date", header: "Timestamp" },
                        { key: "units", header: "Units Consumed (kWh)" },
                        { key: "voltage", header: "Voltage (V)" },
                        { key: "current", header: "Current (mA)" },
                        { key: "power", header: "Power (W)" },
                        {
                            key: "anomaly",
                            header: "Anomaly Flag",
                            render: (row) => (
                                <span
                                    className={`rounded-full px-2.5 py-1 text-xs font-semibold ${row.anomaly === "Yes" ? "bg-rose-100 text-rose-700" : "bg-emerald-100 text-emerald-700"
                                        }`}
                                >
                                    {row.anomaly}
                                </span>
                            ),
                        },
                    ]}
                />
            )}
        </section>
    );
}
