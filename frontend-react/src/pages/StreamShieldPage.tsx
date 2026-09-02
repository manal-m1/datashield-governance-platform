import { useState, useEffect } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import {
    Radar,
    RefreshCw,
    Filter,
    AlertTriangle,
    TrendingUp,
    Sliders,
    Save
    // X supprimé — inutilisé
} from 'lucide-react';
import { Button } from '../components/ui/Button';
import apiClient from '../services/api';
import { useAuthStore } from '../store/authStore';
import { useToast } from '../context/ToastContext';

const StreamShieldPage = () => {
    const user = useAuthStore((state) => state.user);
    const { addToast } = useToast();
    const isAdmin = (user?.role || '').toLowerCase().includes('admin');

    const [risks, setRisks] = useState<any[]>([]);
    const [summary, setSummary] = useState<any[]>([]);
    const [thresholds, setThresholds] = useState<any[]>([]);
    const [isLoading, setIsLoading] = useState(false);
    const [activeTab, setActiveTab] = useState<'live' | 'summary' | 'config'>('live');

    const [domainFilter, setDomainFilter] = useState('');
    const [minScore, setMinScore] = useState(0);

    // Config form (admin only)
    const [configDomain, setConfigDomain] = useState('');
    const [configValue, setConfigValue] = useState(0.5);

    const fetchRisks = async () => {
        setIsLoading(true);
        try {
            const params: any = { min_score: minScore, limit: 50 };
            if (domainFilter) params.domain = domainFilter;
            const resp = await apiClient.get('/streamshield/risks', { params });
            setRisks(resp.data.risks || []);
        } catch (err) {
            console.error('Failed to fetch StreamShield risks', err);
            addToast('Failed to load risk events', 'error');
        } finally {
            setIsLoading(false);
        }
    };

    const fetchSummary = async () => {
        setIsLoading(true);
        try {
            const params: any = {};
            if (domainFilter) params.domain = domainFilter;
            const resp = await apiClient.get('/streamshield/risks/summary', { params });
            setSummary(resp.data.summary || []);
        } catch (err) {
            console.error('Failed to fetch StreamShield summary', err);
        } finally {
            setIsLoading(false);
        }
    };

    const fetchThresholds = async () => {
        setIsLoading(true);
        try {
            const resp = await apiClient.get('/streamshield/config/thresholds');
            setThresholds(Object.entries(resp.data.thresholds || {}).map(([domain, threshold]) => ({ domain, threshold })));
        } catch (err) {
            console.error('Failed to fetch thresholds', err);
        } finally {
            setIsLoading(false);
        }
    };

    const handleSaveThreshold = async () => {
        if (!configDomain) {
            addToast('Domain is required', 'error');
            return;
        }
        try {
            await apiClient.post('/streamshield/config/threshold', {
                domain: configDomain,
                threshold: configValue
            });
            addToast(`Threshold updated for ${configDomain}`, 'success');
            setConfigDomain('');
            fetchThresholds();
        } catch (err: any) {
            addToast(err?.response?.data?.detail || 'Failed to update threshold', 'error');
        }
    };

    useEffect(() => {
        if (activeTab === 'live') fetchRisks();
        else if (activeTab === 'summary') fetchSummary();
        else fetchThresholds();
        // eslint-disable-next-line react-hooks/exhaustive-deps
    }, [activeTab]);

    // Rafraîchissement live toutes les 15s tant qu'on est sur l'onglet "live"
    useEffect(() => {
        if (activeTab !== 'live') return;
        const interval = setInterval(fetchRisks, 15000);
        return () => clearInterval(interval);
        // eslint-disable-next-line react-hooks/exhaustive-deps
    }, [activeTab, domainFilter, minScore]);

    const getScoreStyle = (score: number) => {
        if (score >= 0.8) return 'text-red-400 bg-red-500/10 border-red-500/30';
        if (score >= 0.5) return 'text-orange-400 bg-orange-500/10 border-orange-500/30';
        return 'text-emerald-400 bg-emerald-500/10 border-emerald-500/30';
    };

    return (
        <div className="space-y-10">
            <div className="flex items-center justify-between">
                <div>
                    <h2 className="text-2xl font-bold text-white flex items-center gap-3">
                        <Radar className="text-brand-primary" size={28} />
                        StreamShield
                    </h2>
                    <p className="text-slate-400 text-sm">Real-time re-identification risk monitoring</p>
                </div>
            </div>

            {/* Tabs */}
            <div className="flex bg-white/5 p-1 rounded-2xl border border-white/5 self-start w-fit">
                <button
                    onClick={() => setActiveTab('live')}
                    className={`flex items-center gap-2 px-6 py-3 rounded-xl transition-all font-bold text-sm ${activeTab === 'live' ? 'bg-brand-primary text-white shadow-lg shadow-brand-primary/20' : 'text-slate-500 hover:text-slate-300'}`}
                >
                    <AlertTriangle size={18} />
                    Live Risks
                </button>
                <button
                    onClick={() => setActiveTab('summary')}
                    className={`flex items-center gap-2 px-6 py-3 rounded-xl transition-all font-bold text-sm ${activeTab === 'summary' ? 'bg-brand-primary text-white shadow-lg shadow-brand-primary/20' : 'text-slate-500 hover:text-slate-300'}`}
                >
                    <TrendingUp size={18} />
                    Summary
                </button>
                {isAdmin && (
                    <button
                        onClick={() => setActiveTab('config')}
                        className={`flex items-center gap-2 px-6 py-3 rounded-xl transition-all font-bold text-sm ${activeTab === 'config' ? 'bg-brand-primary text-white shadow-lg shadow-brand-primary/20' : 'text-slate-500 hover:text-slate-300'}`}
                    >
                        <Sliders size={18} />
                        Thresholds
                    </button>
                )}
            </div>

            {/* Filters (live + summary) */}
            {activeTab !== 'config' && (
                <div className="flex items-center gap-3 bg-white/5 p-1.5 rounded-2xl border border-white/5 w-fit">
                    <div className="relative">
                        <Filter className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-500" size={14} />
                        <input
                            className="bg-transparent pl-9 pr-3 py-2 text-xs font-bold text-slate-300 focus:outline-none placeholder:text-slate-600"
                            placeholder="Domain (ex: RH, Finance)"
                            value={domainFilter}
                            onChange={(e) => setDomainFilter(e.target.value)}
                        />
                    </div>
                    {activeTab === 'live' && (
                        <>
                            <div className="w-px h-6 bg-white/10" />
                            <input
                                type="number"
                                min={0}
                                max={1}
                                step={0.05}
                                className="bg-transparent px-3 py-2 text-xs font-bold text-slate-300 focus:outline-none w-20"
                                placeholder="Min score"
                                value={minScore}
                                onChange={(e) => setMinScore(parseFloat(e.target.value) || 0)}
                            />
                        </>
                    )}
                    <button
                        onClick={activeTab === 'live' ? fetchRisks : fetchSummary}
                        className="p-2 ml-2 hover:bg-white/10 rounded-xl transition-colors text-slate-400"
                    >
                        <RefreshCw size={18} className={isLoading ? 'animate-spin' : ''} />
                    </button>
                </div>
            )}

            {/* LIVE RISKS */}
            {activeTab === 'live' && (
                <div className="space-y-4">
                    <AnimatePresence mode="popLayout">
                        {risks.length === 0 ? (
                            <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} className="p-20 glass rounded-[2.5rem] text-center border-dashed border-2 border-white/5">
                                <p className="text-slate-500 font-black uppercase text-[10px] tracking-widest">No Risk Events</p>
                                <p className="text-slate-600 text-xs">No combinations currently exceed the configured thresholds</p>
                            </motion.div>
                        ) : (
                            risks.map((risk, i) => (
                                <motion.div
                                    key={risk._id}
                                    layout
                                    initial={{ opacity: 0, x: -20 }}
                                    animate={{ opacity: 1, x: 0 }}
                                    transition={{ delay: i * 0.03 }}
                                    className="glass p-6 rounded-3xl flex items-center justify-between glass-hover"
                                >
                                    <div className="flex items-center gap-8">
                                        <div className="text-center min-w-[70px]">
                                            <p className="text-[10px] font-black text-slate-600 uppercase mb-1">Domain</p>
                                            <span className="text-sm font-bold text-white">{risk.domain || '—'}</span>
                                        </div>
                                        <div className="h-10 w-px bg-white/5" />
                                        <div>
                                            <div className="flex flex-wrap gap-1.5 mb-2">
                                                {(risk.fields || []).map((f: string) => (
                                                    <span key={f} className="font-mono text-[10px] text-white uppercase bg-slate-800 px-1.5 py-0.5 rounded">{f}</span>
                                                ))}
                                            </div>
                                            <div className="flex items-center gap-4 text-xs text-slate-500">
                                                <span>k = {risk.k}</span>
                                                <div className="w-1 h-1 rounded-full bg-slate-700" />
                                                <span>{new Date(risk.timestamp).toLocaleString()}</span>
                                            </div>
                                        </div>
                                    </div>
                                    <span className={`text-sm font-black px-3 py-1.5 rounded-xl border ${getScoreStyle(risk.score)}`}>
                                        {(risk.score * 100).toFixed(0)}%
                                    </span>
                                </motion.div>
                            ))
                        )}
                    </AnimatePresence>
                </div>
            )}

            {/* SUMMARY */}
            {activeTab === 'summary' && (
                <div className="space-y-4">
                    {summary.length === 0 ? (
                        <div className="p-20 glass rounded-[2.5rem] text-center border-dashed border-2 border-white/5">
                            <p className="text-slate-500 font-black uppercase text-[10px] tracking-widest">No Data</p>
                        </div>
                    ) : (
                        summary.map((s, i) => (
                            <motion.div key={i} initial={{ opacity: 0 }} animate={{ opacity: 1 }} className="glass p-6 rounded-3xl flex items-center justify-between">
                                <div className="flex flex-wrap gap-1.5">
                                    {(s.fields || []).map((f: string) => (
                                        <span key={f} className="font-mono text-[10px] text-white uppercase bg-slate-800 px-1.5 py-0.5 rounded">{f}</span>
                                    ))}
                                </div>
                                <div className="flex items-center gap-6 text-sm">
                                    <span className="text-slate-400">Occurrences: <span className="text-white font-bold">{s.occurrences}</span></span>
                                    <span className="text-slate-400">Avg score: <span className="text-white font-bold">{(s.avg_score * 100).toFixed(0)}%</span></span>
                                    <span className="text-slate-400">Min k: <span className="text-white font-bold">{s.min_k_observed}</span></span>
                                </div>
                            </motion.div>
                        ))
                    )}
                </div>
            )}

            {/* CONFIG (admin only) */}
            {activeTab === 'config' && isAdmin && (
                <div className="space-y-6">
                    <div className="glass p-6 rounded-3xl flex items-end gap-4">
                        <div className="flex-1 space-y-2">
                            <label className="text-[10px] font-black text-slate-400 uppercase tracking-widest ml-1">Domain</label>
                            <input
                                className="input-premium w-full"
                                placeholder="ex: RH, Finance, Sante"
                                value={configDomain}
                                onChange={(e) => setConfigDomain(e.target.value)}
                            />
                        </div>
                        <div className="w-40 space-y-2">
                            <label className="text-[10px] font-black text-slate-400 uppercase tracking-widest ml-1">Threshold (0-1)</label>
                            <input
                                type="number"
                                min={0}
                                max={1}
                                step={0.05}
                                className="input-premium w-full"
                                value={configValue}
                                onChange={(e) => setConfigValue(parseFloat(e.target.value) || 0)}
                            />
                        </div>
                        <Button variant="primary" onClick={handleSaveThreshold} className="h-12">
                            <Save size={18} className="mr-2" />
                            Save
                        </Button>
                    </div>

                    <div className="space-y-3">
                        {thresholds.length === 0 ? (
                            <p className="text-slate-500 text-sm italic">No thresholds configured yet.</p>
                        ) : (
                            thresholds.map((t) => (
                                <div key={t.domain} className="glass p-4 rounded-2xl flex items-center justify-between">
                                    <span className="font-bold text-white">{t.domain}</span>
                                    <span className="text-brand-primary font-mono">{t.threshold}</span>
                                </div>
                            ))
                        )}
                    </div>
                </div>
            )}
        </div>
    );
};

export default StreamShieldPage;