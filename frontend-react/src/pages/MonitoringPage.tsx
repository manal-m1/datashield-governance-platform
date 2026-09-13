import { useEffect, useState } from 'react';
import type { ElementType } from 'react';

import {
    BarChart3,
    Activity,
    Database,
    ShieldAlert,
    RefreshCw,
    CheckCircle2,
    Radio,
    Gauge,
} from 'lucide-react';

interface Risk {
    id?: string;
    dataset_name?: string;
    domain?: string;
    fields?: string[] | string;
    k?: number;
    score?: number;
    timestamp?: string;
}

interface PrometheusResult {
    metric: Record<string, string>;
    value?: [number, string];
}

interface MetricCardProps {
    title: string;
    value: string | number;
    unit?: string;
    icon: ElementType;
    status?: 'normal' | 'warning';
}

interface StatusBarProps {
    label: string;
    healthy: boolean;
}

const PROMETHEUS_URL = '/prometheus/api/v1/query';

const MonitoringPage = () => {
    const [activeTab, setActiveTab] = useState('overview');
    const [refreshing, setRefreshing] = useState(false);

    const [metrics, setMetrics] = useState({
        messagesProcessed: 0,
        riskAlerts: 0,
        latencyP95: 0,
        consumerLag: 0,
    });

    const [risks, setRisks] = useState<Risk[]>([]);

    const [systemStatus, setSystemStatus] = useState({
        prometheus: false,
        consumer: false,
        streamshieldApi: false,
    });

    const tabs = [
        {
            id: 'overview',
            label: 'Overview',
            icon: Activity,
        },
        {
            id: 'kafka',
            label: 'Kafka',
            icon: Radio,
        },
        {
            id: 'risks',
            label: 'Risk Detection',
            icon: ShieldAlert,
        },
        {
            id: 'performance',
            label: 'Performance',
            icon: Gauge,
        },
    ];

    // ========================================================================
    // PROMETHEUS QUERY
    // ========================================================================

    const queryPrometheus = async (
        query: string
    ): Promise<PrometheusResult[]> => {
        try {
            const url = `${PROMETHEUS_URL}?query=${encodeURIComponent(
                query
            )}`;

            console.log('[Prometheus] Query:', query);

            const response = await fetch(url);

            if (!response.ok) {
                console.error(
                    '[Prometheus] HTTP error:',
                    response.status,
                    response.statusText
                );

                return [];
            }

            const json = await response.json();

            console.log(
                '[Prometheus] Response:',
                json
            );

            if (json.status !== 'success') {
                console.error(
                    '[Prometheus] Query failed:',
                    json
                );

                return [];
            }

            return json.data?.result ?? [];
        } catch (error) {
            console.error(
                '[Prometheus] Connection error:',
                error
            );

            return [];
        }
    };

    // ========================================================================
    // CHECK PROMETHEUS
    // ========================================================================

    const checkPrometheus = async (): Promise<boolean> => {
        try {
            const response = await fetch(
                `${PROMETHEUS_URL}?query=${encodeURIComponent('up')}`
            );

            if (!response.ok) {
                return false;
            }

            const data = await response.json();

            return data.status === 'success';
        } catch {
            return false;
        }
    };

    // ========================================================================
    // CHECK CONSUMER
    // ========================================================================

    const checkConsumer = async (): Promise<boolean> => {
        const result = await queryPrometheus(`
            up{
                job="streamshield-consumer"
            }
        `);

        return result.some(
            (item) =>
                Number(item.value?.[1] ?? 0) === 1
        );
    };

    // ========================================================================
    // CHECK STREAMSHIELD API
    // ========================================================================

    const checkStreamShieldApi = async (): Promise<boolean> => {
        try {
            const response = await fetch(
                '/api/streamshield/health'
            );

            return response.ok;
        } catch {
            return false;
        }
    };

    // ========================================================================
    // LOAD METRICS
    // ========================================================================

    const loadMetrics = async () => {
        setRefreshing(true);

        try {
            // ================================================================
            // 1. SYSTEM STATUS
            // ================================================================

            const prometheusOk = await checkPrometheus();
            const consumerOk = await checkConsumer();
            const apiOk = await checkStreamShieldApi();

            setSystemStatus({
                prometheus: prometheusOk,
                consumer: consumerOk,
                streamshieldApi: apiOk,
            });

            // ================================================================
            // 2. MESSAGES PROCESSED
            // ================================================================

            /*
             * streamshield_kafka_messages_processed_total
             * is exposed by the Kafka consumer.
             *
             * The application-defined label is "topic".
             * We therefore avoid depending on the Prometheus "job"
             * label here.
             */

            const processedResults = await queryPrometheus(`
                sum(
                    streamshield_kafka_messages_processed_total
                )
            `);

            console.log(
                '[Kafka] Messages Processed raw:',
                processedResults
            );

            const processedValue = Number(
                processedResults[0]?.value?.[1] ?? 0
            );

            const messagesProcessed =
                Number.isFinite(processedValue)
                    ? processedValue
                    : 0;

            console.log(
                '[Kafka] Messages Processed:',
                messagesProcessed
            );

            // ================================================================
            // 3. RISK ALERTS
            // ================================================================

            /*
             * streamshield_risk_combinations_detected_total
             * is associated with the domain label.
             *
             * We aggregate all domains for the global monitoring card.
             */

            const riskResults = await queryPrometheus(`
                sum(
                    streamshield_risk_combinations_detected_total
                )
            `);

            console.log(
                '[Risk] Risk Alerts raw:',
                riskResults
            );

            const riskValue = Number(
                riskResults[0]?.value?.[1] ?? 0
            );

            const riskAlerts =
                Number.isFinite(riskValue)
                    ? riskValue
                    : 0;

            console.log(
                '[Risk] Risk Alerts:',
                riskAlerts
            );

            // ================================================================
            // 4. P95 LATENCY
            // ================================================================

            /*
             * StreamShield API exposes the latency histogram.
             *
             * No hard-coded job label is required here.
             */

            const latencyResults = await queryPrometheus(`
                histogram_quantile(
                    0.95,
                    sum(
                        rate(
                            streamshield_analysis_latency_seconds_bucket[5m]
                        )
                    ) by (le)
                )
            `);

            console.log(
                '[Performance] P95 raw:',
                latencyResults
            );

            const latencySeconds = Number(
                latencyResults[0]?.value?.[1] ?? 0
            );

            const latencyP95 =
                Number.isFinite(latencySeconds)
                    ? latencySeconds * 1000
                    : 0;

            console.log(
                '[Performance] P95:',
                latencyP95,
                'ms'
            );

            // ================================================================
            // 5. CONSUMER LAG
            // ================================================================

            /*
             * The consumer lag metric has:
             * - topic
             * - partition
             *
             * We aggregate all partitions/topics.
             */

            const lagResults = await queryPrometheus(`
                sum(
                    streamshield_kafka_consumer_lag
                )
            `);

            console.log(
                '[Kafka] Consumer Lag raw:',
                lagResults
            );

            const lagValue = Number(
                lagResults[0]?.value?.[1] ?? 0
            );

            const consumerLag =
                Number.isFinite(lagValue)
                    ? lagValue
                    : 0;

            console.log(
                '[Kafka] Consumer Lag:',
                consumerLag
            );

            // ================================================================
            // 6. RISKS FROM STREAMSHIELD API
            // ================================================================

            try {
                const response = await fetch(
                    '/api/streamshield/risks?limit=10'
                );

                if (response.ok) {
                    const data = await response.json();

                    console.log(
                        '[StreamShield API] Risks:',
                        data
                    );

                    setRisks(
                        Array.isArray(data.risks)
                            ? data.risks
                            : []
                    );
                } else {
                    console.error(
                        '[StreamShield API] HTTP error:',
                        response.status
                    );

                    setRisks([]);
                }
            } catch (error) {
                console.error(
                    '[StreamShield API] Connection error:',
                    error
                );

                setRisks([]);
            }

            // ================================================================
            // 7. UPDATE STATE
            // ================================================================

            setMetrics({
                messagesProcessed,
                riskAlerts,
                latencyP95,
                consumerLag,
            });

            // ================================================================
            // 8. DEBUG FINAL
            // ================================================================

            console.log(
                '[Monitoring] Final metrics:',
                {
                    messagesProcessed,
                    riskAlerts,
                    latencyP95,
                    consumerLag,
                    systemStatus: {
                        prometheus: prometheusOk,
                        consumer: consumerOk,
                        streamshieldApi: apiOk,
                    },
                }
            );
        } catch (error) {
            console.error(
                '[Monitoring] Error loading metrics:',
                error
            );
        } finally {
            setRefreshing(false);
        }
    };

    // ========================================================================
    // AUTO REFRESH
    // ========================================================================

    useEffect(() => {
        loadMetrics();

        const interval = setInterval(() => {
            loadMetrics();
        }, 15000);

        return () => clearInterval(interval);
    }, []);

    // ========================================================================
    // GLOBAL STATUS
    // ========================================================================

    const systemOnline =
        systemStatus.prometheus &&
        systemStatus.consumer &&
        systemStatus.streamshieldApi;

    // ========================================================================
    // METRIC CARD
    // ========================================================================

    const MetricCard = ({
        title,
        value,
        unit,
        icon: Icon,
        status = 'normal',
    }: MetricCardProps) => {
        return (
            <div className="glass rounded-2xl border border-white/5 p-5">
                <div className="flex items-center justify-between">
                    <div>
                        <p className="text-xs uppercase tracking-wider text-slate-500">
                            {title}
                        </p>

                        <div className="flex items-end gap-2 mt-2">
                            <span className="text-3xl font-black text-white">
                                {value}
                            </span>

                            {unit && (
                                <span className="text-xs text-slate-500 mb-1">
                                    {unit}
                                </span>
                            )}
                        </div>
                    </div>

                    <div className="p-3 rounded-xl bg-white/5">
                        <Icon
                            size={22}
                            className={
                                status === 'warning'
                                    ? 'text-yellow-400'
                                    : 'text-brand-primary'
                            }
                        />
                    </div>
                </div>
            </div>
        );
    };

    // ========================================================================
    // STATUS BAR
    // ========================================================================

    const StatusBar = ({
        label,
        healthy,
    }: StatusBarProps) => (
        <div>
            <div className="flex justify-between text-xs mb-2">
                <span className="text-slate-400">
                    {label}
                </span>

                <span
                    className={
                        healthy
                            ? 'text-emerald-400'
                            : 'text-red-400'
                    }
                >
                    {healthy ? 'Healthy' : 'Offline'}
                </span>
            </div>

            <div className="h-2 bg-white/5 rounded-full overflow-hidden">
                <div
                    className={`h-2 rounded-full transition-all ${
                        healthy
                            ? 'bg-emerald-500 w-full'
                            : 'bg-red-500 w-0'
                    }`}
                />
            </div>
        </div>
    );

    // ========================================================================
    // KAFKA PANEL
    // ========================================================================

    const KafkaPanel = () => (
        <div className="space-y-6">

            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">

                <MetricCard
                    title="Messages Processed"
                    value={Math.round(
                        metrics.messagesProcessed
                    )}
                    icon={Database}
                />

                <MetricCard
                    title="Consumer Lag"
                    value={metrics.consumerLag}
                    icon={Radio}
                    status={
                        metrics.consumerLag > 0
                            ? 'warning'
                            : 'normal'
                    }
                />

            </div>

            <div className="glass rounded-2xl border border-white/5 p-6">

                <div className="flex items-center justify-between mb-6">

                    <div>
                        <h2 className="font-bold text-white">
                            Kafka Topics
                        </h2>

                        <p className="text-xs text-slate-500 mt-1">
                            Kafka message processing
                        </p>
                    </div>

                    <Radio
                        size={20}
                        className={
                            systemStatus.consumer
                                ? 'text-brand-primary'
                                : 'text-red-400'
                        }
                    />

                </div>

                <div className="overflow-x-auto">

                    <table className="w-full text-sm">

                        <thead>
                            <tr className="border-b border-white/5 text-slate-500">

                                <th className="text-left py-3">
                                    Topic
                                </th>

                                <th className="text-right py-3">
                                    Consumer
                                </th>

                            </tr>
                        </thead>

                        <tbody>

                            <tr className="border-b border-white/5">

                                <td className="py-4 font-medium text-white">
                                    raw-clients
                                </td>

                                <td className="py-4 text-right">

                                    <span
                                        className={`inline-flex items-center gap-1 text-xs ${
                                            systemStatus.consumer
                                                ? 'text-emerald-400'
                                                : 'text-red-400'
                                        }`}
                                    >

                                        {systemStatus.consumer ? (
                                            <CheckCircle2
                                                size={14}
                                            />
                                        ) : (
                                            <ShieldAlert
                                                size={14}
                                            />
                                        )}

                                        {systemStatus.consumer
                                            ? 'Healthy'
                                            : 'Offline'}

                                    </span>

                                </td>

                            </tr>

                        </tbody>

                    </table>

                </div>

            </div>

            {/* Consumer status */}

            <div className="glass rounded-2xl border border-white/5 p-6">

                <h2 className="font-bold text-white">
                    Consumer Status
                </h2>

                <div className="mt-6 space-y-4">

                    <div className="flex items-center justify-between">

                        <span className="text-sm text-slate-400">
                            Kafka connection
                        </span>

                        <span
                            className={`flex items-center gap-1 text-xs ${
                                systemStatus.consumer
                                    ? 'text-emerald-400'
                                    : 'text-red-400'
                            }`}
                        >

                            {systemStatus.consumer ? (
                                <CheckCircle2 size={14} />
                            ) : (
                                <ShieldAlert size={14} />
                            )}

                            {systemStatus.consumer
                                ? 'Connected'
                                : 'Disconnected'}

                        </span>

                    </div>

                    <div className="flex items-center justify-between">

                        <span className="text-sm text-slate-400">
                            Consumer
                        </span>

                        <span
                            className={`flex items-center gap-1 text-xs ${
                                systemStatus.consumer
                                    ? 'text-emerald-400'
                                    : 'text-red-400'
                            }`}
                        >

                            {systemStatus.consumer ? (
                                <CheckCircle2 size={14} />
                            ) : (
                                <ShieldAlert size={14} />
                            )}

                            {systemStatus.consumer
                                ? 'Running'
                                : 'Stopped'}

                        </span>

                    </div>

                    <div className="flex items-center justify-between">

                        <span className="text-sm text-slate-400">
                            Consumer lag
                        </span>

                        <span className="text-white font-bold">
                            {metrics.consumerLag}
                        </span>

                    </div>

                    <div className="pt-4 border-t border-white/5">

                        <p className="text-xs text-slate-500">
                            Consumer group
                        </p>

                        <p className="text-sm text-white mt-1">
                            streamshield-detection
                        </p>

                    </div>

                </div>

            </div>

        </div>
    );

    // ========================================================================
    // RISK PANEL
    // ========================================================================

    const RiskPanel = () => (
        <div className="space-y-6">

            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">

                <MetricCard
                    title="Risk Combinations"
                    value={Math.round(
                        metrics.riskAlerts
                    )}
                    icon={ShieldAlert}
                    status={
                        metrics.riskAlerts > 0
                            ? 'warning'
                            : 'normal'
                    }
                />

                <MetricCard
                    title="P95 Latency"
                    value={metrics.latencyP95.toFixed(0)}
                    unit="ms"
                    icon={Gauge}
                />

            </div>

            <div className="glass rounded-2xl border border-white/5 p-6">

                <h2 className="font-bold text-white mb-5">
                    Recent Risk Alerts
                </h2>

                <div className="overflow-x-auto">

                    <table className="w-full text-sm">

                        <thead>

                            <tr className="border-b border-white/5 text-slate-500">

                                <th className="text-left py-3">
                                    Dataset
                                </th>

                                <th className="text-left py-3">
                                    Domain
                                </th>

                                <th className="text-left py-3">
                                    Combination
                                </th>

                                <th className="text-right py-3">
                                    Score
                                </th>

                            </tr>

                        </thead>

                        <tbody>

                            {risks.length === 0 ? (

                                <tr>

                                    <td
                                        colSpan={4}
                                        className="text-center py-8 text-slate-500"
                                    >
                                        No recent alerts
                                    </td>

                                </tr>

                            ) : (

                                risks.map(
                                    (risk, index) => {

                                        const score =
                                            Number(
                                                risk.score ?? 0
                                            );

                                        const scoreClass =
                                            score >= 0.90
                                                ? 'text-red-500'
                                                : score >= 0.70
                                                ? 'text-orange-400'
                                                : 'text-yellow-400';

                                        return (
                                            <tr
                                                key={
                                                    risk.id ||
                                                    index
                                                }
                                                className="border-b border-white/5"
                                            >

                                                <td className="py-4 text-white">
                                                    {risk.dataset_name ||
                                                        '-'}
                                                </td>

                                                <td className="py-4 text-slate-400">
                                                    {risk.domain ||
                                                        '-'}
                                                </td>

                                                <td className="py-4 text-slate-400">

                                                    {Array.isArray(
                                                        risk.fields
                                                    )
                                                        ? risk.fields.join(
                                                              ', '
                                                          )
                                                        : risk.fields ||
                                                          '-'}

                                                </td>

                                                <td className="py-4 text-right">

                                                    <span
                                                        className={`${scoreClass} font-bold`}
                                                    >
                                                        {score.toFixed(
                                                            2
                                                        )}
                                                    </span>

                                                </td>

                                            </tr>
                                        );
                                    }
                                )
                            )}

                        </tbody>

                    </table>

                </div>

            </div>

        </div>
    );

    // ========================================================================
    // PERFORMANCE PANEL
    // ========================================================================

    const PerformancePanel = () => (
        <div className="space-y-6">

            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">

                <MetricCard
                    title="P95 Latency"
                    value={metrics.latencyP95.toFixed(0)}
                    unit="ms"
                    icon={Gauge}
                />

                <MetricCard
                    title="Consumer Status"
                    value={
                        systemStatus.consumer
                            ? 'ONLINE'
                            : 'OFFLINE'
                    }
                    icon={
                        systemStatus.consumer
                            ? CheckCircle2
                            : ShieldAlert
                    }
                    status={
                        systemStatus.consumer
                            ? 'normal'
                            : 'warning'
                    }
                />

            </div>

            <div className="glass rounded-2xl border border-white/5 p-6">

                <h2 className="font-bold text-white">
                    System Performance
                </h2>

                <div className="mt-6 space-y-5">

                    <StatusBar
                        label="Kafka Consumer"
                        healthy={
                            systemStatus.consumer
                        }
                    />

                    <StatusBar
                        label="Prometheus"
                        healthy={
                            systemStatus.prometheus
                        }
                    />

                    <StatusBar
                        label="StreamShield API"
                        healthy={
                            systemStatus.streamshieldApi
                        }
                    />

                </div>

            </div>

        </div>
    );

    // ========================================================================
    // OVERVIEW PANEL
    // ========================================================================

    const OverviewPanel = () => (
        <div className="space-y-6">

            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">

                <MetricCard
                    title="Messages Processed"
                    value={Math.round(
                        metrics.messagesProcessed
                    )}
                    icon={Database}
                />

                <MetricCard
                    title="Risk Alerts"
                    value={Math.round(
                        metrics.riskAlerts
                    )}
                    icon={ShieldAlert}
                    status={
                        metrics.riskAlerts > 0
                            ? 'warning'
                            : 'normal'
                    }
                />

                <MetricCard
                    title="P95 Latency"
                    value={metrics.latencyP95.toFixed(0)}
                    unit="ms"
                    icon={Gauge}
                />

            </div>

            <KafkaPanel />

        </div>
    );

    // ========================================================================
    // CONTENT
    // ========================================================================

    const renderContent = () => {
        switch (activeTab) {
            case 'kafka':
                return <KafkaPanel />;

            case 'risks':
                return <RiskPanel />;

            case 'performance':
                return <PerformancePanel />;

            default:
                return <OverviewPanel />;
        }
    };

    // ========================================================================
    // RETURN
    // ========================================================================

    return (
        <div className="space-y-6">

            {/* Header */}

            <div className="flex flex-col lg:flex-row lg:items-center lg:justify-between gap-4">

                <div>

                    <h1 className="text-2xl font-black tracking-tight text-white flex items-center gap-3">

                        <BarChart3
                            className="text-brand-primary"
                            size={28}
                        />

                        Monitoring

                    </h1>

                    <p className="text-xs text-slate-400 mt-1">
                        Real-time monitoring of Kafka,
                        risk detection and
                        StreamShield performance
                    </p>

                </div>

                <div className="flex items-center gap-3">

                    {/* Global status */}

                    <div
                        className={`flex items-center gap-2 px-3 py-2 rounded-xl border ${
                            systemOnline
                                ? 'bg-emerald-500/10 border-emerald-500/20'
                                : 'bg-red-500/10 border-red-500/20'
                        }`}
                    >

                        <span
                            className={`w-2 h-2 rounded-full ${
                                systemOnline
                                    ? 'bg-emerald-400 animate-pulse'
                                    : 'bg-red-400'
                            }`}
                        />

                        <span
                            className={`text-xs font-semibold ${
                                systemOnline
                                    ? 'text-emerald-400'
                                    : 'text-red-400'
                            }`}
                        >
                            {systemOnline
                                ? 'LIVE'
                                : 'OFFLINE'}
                        </span>

                    </div>

                    {/* Refresh */}

                    <button
                        onClick={loadMetrics}
                        disabled={refreshing}
                        className="flex items-center gap-2 px-4 py-2 rounded-xl bg-white/5 border border-white/10 text-slate-300 hover:bg-white/10 transition disabled:opacity-50"
                    >

                        <RefreshCw
                            size={15}
                            className={
                                refreshing
                                    ? 'animate-spin'
                                    : ''
                            }
                        />

                        Refresh

                    </button>

                </div>

            </div>

            {/* Tabs */}

            <div className="flex gap-2 overflow-x-auto pb-1">

                {tabs.map((tab) => {

                    const Icon = tab.icon;

                    return (

                        <button
                            key={tab.id}
                            onClick={() =>
                                setActiveTab(tab.id)
                            }
                            className={`
                                flex items-center gap-2 px-4 py-2.5
                                rounded-xl text-sm font-semibold
                                whitespace-nowrap transition
                                ${
                                    activeTab === tab.id
                                        ? 'bg-brand-primary text-white'
                                        : 'bg-white/5 text-slate-400 hover:bg-white/10 hover:text-white'
                                }
                            `}
                        >

                            <Icon size={16} />

                            {tab.label}

                        </button>

                    );
                })}

            </div>

            {/* Content */}

            {renderContent()}

        </div>
    );
};

export default MonitoringPage;