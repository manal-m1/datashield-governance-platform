
import React, { useState, useEffect } from 'react';
import { motion } from 'framer-motion';
import {
    Radar, Filter, RefreshCw, Save, ShieldAlert, Layers, Sliders,
    Database, ChevronDown, ChevronUp, CheckCircle2, History
} from 'lucide-react';
import { Button } from '../components/ui/Button';
import apiClient from '../services/api';
import { useToast } from '../context/ToastContext';
import { useAuthStore } from '../store/authStore';

// ============================================================================
// TYPES
// ============================================================================

interface Dataset {
    id: string;
    name: string;
    rows?: number;
    columns?: number;
    domain?: string;
    owner?: string;
}

interface RiskEvent {
    _id?: string;
    dataset_id?: string;
    dataset_name?: string;
    domain: string;
    domain_source?: string;
    fields: string[];
    k: number;
    uniqueness?: number;
    avg_sensitivity?: number;
    score: number;
    sample_size?: number;
    triggered?: boolean;
    atlas_metadata_available?: boolean;
    timestamp: string;
}

interface Threshold {
    domain: string;
    threshold: number;
}

interface AnalysisResponse {
    dataset_id: string;
    dataset_name: string;
    domain: string;
    domain_source: string;
    records_analyzed: number;
    combinations_tested: number;
    combinations_at_risk: number;
    threshold: number;
    max_score: number;
    average_score: number;
    atlas_metadata: any | null;
    results: RiskEvent[];
}
interface DatasetScoreSummary {
    dataset_id: string;
    dataset_name: string;
    domain: string;
    risks: RiskEvent[];
    max_score: number;
    average_score: number;
    combinations_at_risk: number;
    last_timestamp: string;
}

// Détecte un UUID brut, pas lisible pour l'utilisateur (dataset_name ou domain
// peuvent y retomber quand le backend n'a pas de vrai libellé disponible).
const looksLikeUuid = (value?: string) =>
    !!value && /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i.test(value);

const StreamShieldPage = () => {
    const user = useAuthStore((state) => state.user);
    const { addToast } = useToast();
    const isAdmin = (user?.role || '').toLowerCase().includes('admin');

    const [activeTab, setActiveTab] = useState<'live' | 'summary' | 'config'>('live');

    // Datasets
    const [datasets, setDatasets] = useState<Dataset[]>([]);
    const [selectedDatasetId, setSelectedDatasetId] = useState<string>('');
    const [domainOverride, setDomainOverride] = useState<string>('');
    const [isLoadingDatasets, setIsLoadingDatasets] = useState<boolean>(false);

    // Analyse à la demande — seule source de vérité pour l'onglet "Live"
    const [isAnalyzing, setIsAnalyzing] = useState<boolean>(false);
    const [lastAnalysis, setLastAnalysis] = useState<AnalysisResponse | null>(null);
    const [showOnlyTriggered, setShowOnlyTriggered] = useState<boolean>(true);

    // Historique global — masqué par défaut, chargé uniquement à la demande
    const [showHistory, setShowHistory] = useState<boolean>(false);
    const [risks, setRisks] = useState<RiskEvent[]>([]);
    const [isLoadingHistory, setIsLoadingHistory] = useState<boolean>(false);
    const [domainFilter, setDomainFilter] = useState<string>('');
    const [minScore, setMinScore] = useState<number>(0);

    // Summary
    const [isLoadingSummary, setIsLoadingSummary] = useState<boolean>(false);

    // Config
    const [thresholds, setThresholds] = useState<Threshold[]>([]);
    const [configDomain, setConfigDomain] = useState<string>('');
    const [configValue, setConfigValue] = useState<number>(0.5);

    const selectedDataset = datasets.find((d) => d.id === selectedDatasetId);

    // ------------------------------------------------------------------
    useEffect(() => {
        fetchDatasets();
        // eslint-disable-next-line react-hooks/exhaustive-deps
    }, []);

    useEffect(() => {
        if (activeTab === 'summary') fetchDatasetHistory();
        if (activeTab === 'config') fetchThresholds();
        // Pas de fetch auto pour 'live' : reste vide tant qu'aucune analyse
        // n'a été lancée, ou tant que l'historique n'est pas demandé explicitement.
        // eslint-disable-next-line react-hooks/exhaustive-deps
    }, [activeTab]);

    useEffect(() => {
        if (activeTab === 'live' && showHistory) fetchHistory();
        // eslint-disable-next-line react-hooks/exhaustive-deps
    }, [showHistory, domainFilter, minScore]);

    const [datasetHistory, setDatasetHistory] = useState<RiskEvent[]>([]);
    const fetchDatasetHistory = async () => {
        setIsLoadingSummary(true);

        try {
            const resp = await apiClient.get('/streamshield/risks', {
                params: {
                    limit: 500
                }
            });

            setDatasetHistory(resp.data.risks || []);
        } catch (err) {
            console.error('Erreur récupération historique des scores:', err);
            addToast(
                "Impossible de récupérer l'historique des scores",
                'error'
            );
        } finally {
            setIsLoadingSummary(false);
        }
    };
    // ------------------------------------------------------------------
    // Datasets
    // ------------------------------------------------------------------
    const fetchDatasets = async () => {
        setIsLoadingDatasets(true);
        try {
            const resp = await apiClient.get('/streamshield/datasets');
            const list: Dataset[] = resp.data.datasets || [];
            setDatasets(list);
            if (list.length > 0 && !selectedDatasetId) setSelectedDatasetId(list[0].id);
        } catch (err) {
            console.error('Erreur chargement datasets:', err);
            addToast('Impossible de charger la liste des datasets (Cleaning Service)', 'error');
        } finally {
            setIsLoadingDatasets(false);
        }
    };

    // ------------------------------------------------------------------
    // Historique global (masqué par défaut)
    // ------------------------------------------------------------------
    const fetchHistory = async () => {
        setIsLoadingHistory(true);
        try {
            const params: any = { min_score: minScore, limit: 50 };
            if (domainFilter) params.domain = domainFilter;
            const resp = await apiClient.get('/streamshield/risks', { params });
            setRisks(resp.data.risks || []);
        } catch (err) {
            console.error('Erreur chargement historique:', err);
            addToast("Impossible de charger l'historique", 'error');
        } finally {
            setIsLoadingHistory(false);
        }
    };
    // ------------------------------------------------------------------
    // Thresholds
    // ------------------------------------------------------------------
    const fetchThresholds = async () => {
        try {
            const resp = await apiClient.get('/streamshield/config/thresholds');
            const entries = Object.entries(resp.data.thresholds || {}) as [string, number][];
            setThresholds(entries.map(([domain, threshold]) => ({ domain, threshold })));
        } catch (err) {
            console.error('Erreur chargement seuils:', err);
        }
    };

    const handleSaveThreshold = async () => {
        if (!configDomain) {
            addToast('Le domaine est requis', 'error');
            return;
        }
        try {
            await apiClient.post('/streamshield/config/threshold', {
                domain: configDomain,
                threshold: configValue,
            });
            addToast(`Seuil mis à jour pour ${configDomain}`, 'success');
            setConfigDomain('');
            fetchThresholds();
        } catch (err: any) {
            addToast(err?.response?.data?.detail || 'Échec de la mise à jour du seuil', 'error');
        }
    };
    

    // ------------------------------------------------------------------
    // Analyse à la demande
    // ------------------------------------------------------------------
    const handleAnalyzeDataset = async () => {
        if (!selectedDatasetId) return;
        setIsAnalyzing(true);
        setLastAnalysis(null);

        try {
            const params: any = {};
            if (domainOverride) params.domain = domainOverride;

            const resp = await apiClient.post<AnalysisResponse>(
                `/streamshield/analyze/${selectedDatasetId}`,
                null,
                { params }
            );

            setLastAnalysis(resp.data);
            setShowOnlyTriggered(resp.data.combinations_at_risk > 0);
            addToast(
                `${resp.data.combinations_at_risk} combinaison(s) à risque sur ${resp.data.combinations_tested} testée(s)`,
                resp.data.combinations_at_risk > 0 ? 'success' : 'info'
            );
        } catch (err: any) {
            addToast(err?.response?.data?.detail || 'Analyse échouée', 'error');
        } finally {
            setIsAnalyzing(false);
        }
    };

    // ------------------------------------------------------------------
    // Helpers d'affichage
    // ------------------------------------------------------------------
    const getScoreColor = (score: number) => {
        if (score >= 0.75) return '#f87171'; // red-400
        if (score >= 0.5) return '#fbbf24'; // amber-400
        return '#34d399'; // emerald-400
    };

    const getScoreStyle = (score: number) => {
        if (score >= 0.75) return 'bg-red-500/10 text-red-400 border-red-500/20';
        if (score >= 0.5) return 'bg-amber-500/10 text-amber-400 border-amber-500/20';
        return 'bg-emerald-500/10 text-emerald-400 border-emerald-500/20';
    };

    // Nom de dataset propre : préfère le nom connu côté /datasets, jamais un UUID brut
    const friendlyDatasetName = (r: { dataset_id?: string; dataset_name?: string }) => {
        const known = datasets.find((d) => d.id === r.dataset_id)?.name;
        if (known) return known;
        if (r.dataset_name && !looksLikeUuid(r.dataset_name)) return r.dataset_name;
        return 'Dataset sans nom';
    };

    // Nom de domaine propre : jamais un identifiant brut.
    const friendlyDomain = (a: { domain: string; domain_source?: string }) => {
        if (a.domain_source === 'atlas' || a.domain_source === 'manual') {
            return looksLikeUuid(a.domain) ? 'Domaine non nommé' : a.domain;
        }
        return 'Non classifié';
    };

    const displayedResults = lastAnalysis
        ? (showOnlyTriggered ? lastAnalysis.results.filter((r) => r.triggered) : lastAnalysis.results)
        : [];

    const atlasAttrs = lastAnalysis?.atlas_metadata?.attributes || lastAnalysis?.atlas_metadata || null;
    const groupedDatasetHistory: DatasetScoreSummary[] = Object.values(
        datasetHistory.reduce((groups, risk) => {
            const key = risk.dataset_id || risk.dataset_name || 'unknown';

            if (!groups[key]) {
                groups[key] = {
                    dataset_id: risk.dataset_id || '',
                    dataset_name: friendlyDatasetName(risk),
                    domain: friendlyDomain(risk),
                    risks: [],
                    max_score: 0,
                    average_score: 0,
                    combinations_at_risk: 0,
                    last_timestamp: risk.timestamp,
                };
            }

            groups[key].risks.push(risk);

            groups[key].max_score = Math.max(
                groups[key].max_score,
                risk.score
            );

            if (risk.triggered) {
                groups[key].combinations_at_risk += 1;
            }

            if (
                new Date(risk.timestamp).getTime() >
                new Date(groups[key].last_timestamp).getTime()
            ) {
                groups[key].last_timestamp = risk.timestamp;
            }

            return groups;
        }, {} as Record<string, DatasetScoreSummary>)
    ).map((group) => ({
        ...group,
        average_score:
            group.risks.length > 0
                ? group.risks.reduce((sum, r) => sum + r.score, 0) /
                group.risks.length
                : 0,
    }));
    return (
        <div className="space-y-8">
            {/* En-tête */}
            <div className="flex items-center justify-between flex-wrap gap-4">
                <div>
                    <h1 className="text-2xl font-black tracking-tight text-white flex items-center gap-3">
                        <ShieldAlert className="text-brand-primary" size={28} />
                        StreamShield — Risk Engine
                    </h1>
                    <p className="text-xs text-slate-400 mt-1">
                        Analyse dynamique des risques de ré-identification et suivi du score k-anonymat
                    </p>
                </div>

                <div className="flex bg-slate-900 p-1.5 rounded-2xl border border-white/5 gap-1">
                    <button
                        onClick={() => setActiveTab('live')}
                        className={`flex items-center gap-2 px-4 py-2 rounded-xl text-xs font-bold transition-all ${activeTab === 'live' ? 'bg-brand-primary text-black shadow-lg shadow-brand-primary/20' : 'text-slate-400 hover:text-white'}`}
                    >
                        <Radar size={16} /> Live Risks
                    </button>
                    <button
                        onClick={() => setActiveTab('summary')}
                        className={`flex items-center gap-2 px-4 py-2 rounded-xl text-xs font-bold transition-all ${activeTab === 'summary' ? 'bg-brand-primary text-black shadow-lg shadow-brand-primary/20' : 'text-slate-400 hover:text-white'}`}
                    >
                        <Layers size={16} /> Summary
                    </button>
                    {isAdmin && (
                        <button
                            onClick={() => setActiveTab('config')}
                            className={`flex items-center gap-2 px-4 py-2 rounded-xl text-xs font-bold transition-all ${activeTab === 'config' ? 'bg-brand-primary text-black shadow-lg shadow-brand-primary/20' : 'text-slate-400 hover:text-white'}`}
                        >
                            <Sliders size={16} /> Configuration
                        </button>
                    )}
                </div>
            </div>

            {/* ================================================================ */}
            {/* ONGLET LIVE — vide par défaut, piloté par l'analyse à la demande  */}
            {/* ================================================================ */}
            {activeTab === 'live' && (
                <div className="space-y-8">
                    {/* Sélection dataset + lancement analyse */}
                    <div className="glass p-6 rounded-3xl border border-white/5 space-y-4">
                        <div className="grid grid-cols-1 md:grid-cols-3 gap-4 items-end">
                            <div className="space-y-2">
                                <label className="text-[10px] font-black text-slate-400 uppercase tracking-widest ml-1">
                                    Jeu de données
                                </label>
                                <div className="relative">
                                    <Database className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-500" size={16} />
                                    <select
                                        className="input-premium w-full pl-10 appearance-none text-xs font-medium"
                                        value={selectedDatasetId}
                                        onChange={(e) => setSelectedDatasetId(e.target.value)}
                                        disabled={isLoadingDatasets}
                                        style={{ backgroundColor: '#000000', color: '#ffffff' }}
                                    >
                                        {datasets.length === 0 && (
                                            <option value="" style={{ backgroundColor: '#000000', color: '#ffffff' }}>
                                                Aucun dataset disponible
                                            </option>
                                        )}
                                        {datasets.map((d) => (
                                            <option
                                                key={d.id}
                                                value={d.id}
                                                style={{ backgroundColor: '#000000', color: '#ffffff' }}
                                            >
                                                {d.name}{d.rows ? ` (${d.rows} lignes)` : ''}
                                            </option>
                                        ))}
                                    </select>
                                </div>
                            </div>

                            <div className="space-y-2">
                                <label className="text-[10px] font-black text-slate-400 uppercase tracking-widest ml-1">
                                    Domaine (optionnel)
                                </label>
                                <input
                                    className="input-premium w-full placeholder:text-slate-600 text-xs"
                                    placeholder="Auto (Atlas)"
                                    value={domainOverride}
                                    onChange={(e) => setDomainOverride(e.target.value)}
                                />
                            </div>

                            <Button
                                variant="primary"
                                onClick={handleAnalyzeDataset}
                                isLoading={isAnalyzing}
                                disabled={!selectedDatasetId}
                                className="h-11 px-6 text-xs"
                            >
                                <Radar size={18} className="mr-2" />
                                Analyser
                            </Button>
                        </div>

                        {selectedDataset && (selectedDataset.rows || selectedDataset.columns || selectedDataset.domain || selectedDataset.owner) && (
                            <div className="pt-4 border-t border-white/5 grid grid-cols-2 sm:grid-cols-4 gap-4 text-xs">
                                {selectedDataset.rows !== undefined && (
                                    <div>
                                        <p className="text-slate-500 font-medium">Lignes</p>
                                        <p className="text-white font-bold">{selectedDataset.rows}</p>
                                    </div>
                                )}
                                {selectedDataset.columns !== undefined && (
                                    <div>
                                        <p className="text-slate-500 font-medium">Colonnes</p>
                                        <p className="text-white font-bold">{selectedDataset.columns}</p>
                                    </div>
                                )}
                                {selectedDataset.domain && (
                                    <div>
                                        <p className="text-slate-500 font-medium">Domaine détecté</p>
                                        <p className="text-brand-primary font-bold">{selectedDataset.domain}</p>
                                    </div>
                                )}
                                {selectedDataset.owner && (
                                    <div>
                                        <p className="text-slate-500 font-medium">Propriétaire</p>
                                        <p className="text-white font-bold">{selectedDataset.owner}</p>
                                    </div>
                                )}
                            </div>
                        )}
                    </div>

                    {/* État vide — tant qu'aucune analyse n'a été lancée */}
                    {!lastAnalysis && !isAnalyzing && (
                        <div className="p-16 glass rounded-[2.5rem] text-center border-dashed border-2 border-white/5">
                            <div className="w-14 h-14 mx-auto mb-4 rounded-2xl bg-brand-primary/10 flex items-center justify-center">
                                <Radar className="text-brand-primary" size={26} />
                            </div>
                            <p className="text-slate-400 font-bold text-sm">Choisissez un dataset et cliquez sur "Analyser"</p>
                            <p className="text-slate-600 text-xs mt-1">Les combinaisons à risque et leurs scores s'afficheront ici</p>
                        </div>
                    )}

                    {/* ============================================================ */}
                    {/* RÉSULTATS — carte de synthèse + stats + nuage + tableau      */}
                    {/* ============================================================ */}
                    {lastAnalysis && (
                        <div className="space-y-6">
                            {/* Carte de synthèse */}
                            <div className="glass p-6 rounded-3xl border border-emerald-500/20 bg-emerald-500/5">
                                <div className="flex items-center justify-between flex-wrap gap-2">
                                    <div>
                                        <h3 className="text-lg font-bold text-white">{friendlyDatasetName(lastAnalysis)}</h3>
                                        <p className="text-xs text-slate-400 mt-1">
                                            {lastAnalysis.records_analyzed} enregistrement(s) analysé(s) — Domaine : <span className="text-brand-primary font-bold">{friendlyDomain(lastAnalysis)}</span>
                                        </p>
                                    </div>
                                    <span className="flex items-center gap-2 text-emerald-400 text-sm font-bold">
                                        <CheckCircle2 size={18} />
                                        Analyse terminée
                                    </span>
                                </div>
                            </div>

                            {/* Cartes statistiques */}
                            <div className="grid grid-cols-2 md:grid-cols-3 gap-4">
                                <div className="glass p-5 rounded-2xl border border-white/5 text-center">
                                    <p className="text-[10px] font-black text-slate-500 uppercase tracking-wider">Combinaisons</p>
                                    <p className="text-2xl font-extrabold text-white mt-1">{lastAnalysis.combinations_tested}</p>
                                </div>
                                <div className="glass p-5 rounded-2xl border border-white/5 text-center">
                                    <p className="text-[10px] font-black text-slate-500 uppercase tracking-wider">À risque</p>
                                    <p className="text-2xl font-extrabold text-red-400 mt-1">{lastAnalysis.combinations_at_risk}</p>
                                </div>
                                <div className="glass p-5 rounded-2xl border border-white/5 text-center">
                                    <p className="text-[10px] font-black text-slate-500 uppercase tracking-wider">Score max</p>
                                    <p className="text-2xl font-extrabold text-brand-primary mt-1">{(lastAnalysis.max_score * 100).toFixed(0)}%</p>
                                </div>
                            </div>

                            {/* Métadonnées Apache Atlas (si disponibles) */}
                            {lastAnalysis.atlas_metadata && (
                                <div className="glass p-6 rounded-3xl border border-white/5">
                                    <div className="flex items-center justify-between mb-4">
                                        <h3 className="text-sm font-bold text-white">Métadonnées Apache Atlas</h3>
                                        <span className="text-[10px] font-black uppercase text-emerald-400 bg-emerald-500/10 px-2 py-1 rounded-md border border-emerald-500/20 flex items-center gap-1">
                                            <CheckCircle2 size={12} /> Connecté
                                        </span>
                                    </div>
                                    <div className="grid grid-cols-2 md:grid-cols-4 gap-4 text-xs">
                                        <div>
                                            <p className="text-slate-500">Dataset</p>
                                            <p className="text-white font-bold">{atlasAttrs?.name || friendlyDatasetName(lastAnalysis)}</p>
                                        </div>
                                        <div>
                                            <p className="text-slate-500">Propriétaire</p>
                                            <p className="text-white font-bold">{atlasAttrs?.owner || '—'}</p>
                                        </div>
                                        <div>
                                            <p className="text-slate-500">Qualified Name</p>
                                            <p className="text-white font-mono text-[10px] truncate">{atlasAttrs?.qualifiedName || '—'}</p>
                                        </div>
                                        <div>
                                            <p className="text-slate-500">Quality Score</p>
                                            <p className="text-brand-primary font-bold">{atlasAttrs?.qualityScore ?? '—'}</p>
                                        </div>
                                    </div>
                                </div>
                            )}

                            {/* Nuage de points — distribution des scores */}
                            {lastAnalysis.results.length > 0 && (
                                <div className="glass p-6 rounded-3xl border border-white/5">
                                    <h3 className="text-xs font-black text-slate-400 uppercase tracking-widest mb-6">
                                        Distribution des scores de risque
                                    </h3>
                                    <RiskScatterChart
                                        results={lastAnalysis.results}
                                        getColor={getScoreColor}
                                    />
                                </div>
                            )}

                            {/* Tableau des combinaisons */}
                            <div className="glass rounded-3xl border border-white/5 overflow-hidden">
                                <div className="flex items-center justify-between p-6 pb-4 flex-wrap gap-3">
                                    <h3 className="text-xs font-black text-slate-400 uppercase tracking-widest">
                                        Combinaisons {showOnlyTriggered ? 'à risque' : 'testées'}
                                    </h3>
                                    <div className="flex bg-white/5 p-1 rounded-xl border border-white/5">
                                        <button
                                            onClick={() => setShowOnlyTriggered(true)}
                                            className={`px-3 py-1.5 rounded-lg text-[10px] font-black uppercase transition-all ${showOnlyTriggered ? 'bg-brand-primary text-black' : 'text-slate-400'}`}
                                        >
                                            À risque ({lastAnalysis.combinations_at_risk})
                                        </button>
                                        <button
                                            onClick={() => setShowOnlyTriggered(false)}
                                            className={`px-3 py-1.5 rounded-lg text-[10px] font-black uppercase transition-all ${!showOnlyTriggered ? 'bg-brand-primary text-black' : 'text-slate-400'}`}
                                        >
                                            Toutes ({lastAnalysis.combinations_tested})
                                        </button>
                                    </div>
                                </div>

                                {displayedResults.length === 0 ? (
                                    <div className="p-10 text-center border-t border-white/5">
                                        <p className="text-slate-500 font-black uppercase text-[10px] tracking-widest">Aucune combinaison à risque</p>
                                        <p className="text-slate-600 text-xs mt-1">Toutes les combinaisons testées restent sous le seuil configuré</p>
                                    </div>
                                ) : (
                                    <div className="overflow-x-auto">
                                        <table className="w-full text-sm">
                                            <thead>
                                                <tr className="border-t border-white/5 text-slate-500 text-[10px] uppercase font-black tracking-wider">
                                                    <th className="text-left px-6 py-3">Combinaison</th>
                                                    <th className="text-center px-4 py-3">k</th>
                                                    <th className="text-center px-4 py-3">Unicité</th>
                                                    <th className="text-right px-6 py-3">Score</th>
                                                </tr>
                                            </thead>
                                            <tbody>
                                                {displayedResults
                                                    .slice()
                                                    .sort((a, b) => b.score - a.score)
                                                    .map((risk, i) => (
                                                        <tr key={risk.fields.join('|')} className={`border-t border-white/5 ${i % 2 === 0 ? 'bg-white/[0.02]' : ''}`}>
                                                            <td className="px-6 py-3 text-white font-medium">{risk.fields.join(' + ')}</td>
                                                            <td className="px-4 py-3 text-center text-slate-300">{risk.k}</td>
                                                            <td className="px-4 py-3 text-center text-slate-300">{((risk.uniqueness ?? 0)).toFixed(2)}</td>
                                                            <td className="px-6 py-3 text-right">
                                                                <span className={`inline-block px-3 py-1 rounded-lg border font-black text-xs ${getScoreStyle(risk.score)}`}>
                                                                    {risk.score.toFixed(2)}
                                                                </span>
                                                            </td>
                                                        </tr>
                                                    ))}
                                            </tbody>
                                        </table>
                                    </div>
                                )}
                            </div>
                        </div>
                    )}

                    {/* Historique global — replié par défaut, masqué tant que non demandé */}
                    <div className="pt-2">
                        <button
                            onClick={() => setShowHistory(!showHistory)}
                            className="flex items-center gap-2 text-xs font-bold text-slate-500 hover:text-slate-300 transition-colors"
                        >
                            <History size={14} />
                            {showHistory ? 'Masquer' : 'Afficher'} l'historique complet (tous datasets)
                            {showHistory ? <ChevronUp size={14} /> : <ChevronDown size={14} />}
                        </button>

                        {showHistory && (
                            <div className="mt-4 space-y-4">
                                <div className="flex items-center gap-3 bg-white/5 p-1.5 rounded-2xl border border-white/5 w-fit flex-wrap">
                                    <div className="relative">
                                        <Filter className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-500" size={14} />
                                        <input
                                            className="bg-transparent pl-9 pr-3 py-2 text-xs font-bold text-slate-300 focus:outline-none placeholder:text-slate-600"
                                            placeholder="Filtre domaine"
                                            value={domainFilter}
                                            onChange={(e) => setDomainFilter(e.target.value)}
                                        />
                                    </div>
                                    <div className="w-px h-6 bg-white/10" />
                                    <input
                                        type="number"
                                        min={0}
                                        max={1}
                                        step={0.05}
                                        className="bg-transparent px-3 py-2 text-xs font-bold text-slate-300 focus:outline-none w-24 placeholder:text-slate-600"
                                        placeholder="Score min"
                                        value={minScore || ''}
                                        onChange={(e) => setMinScore(parseFloat(e.target.value) || 0)}
                                    />
                                    <button
                                        onClick={fetchHistory}
                                        className="p-2 ml-2 hover:bg-white/10 rounded-xl transition-colors text-slate-400"
                                    >
                                        <RefreshCw size={18} className={isLoadingHistory ? 'animate-spin' : ''} />
                                    </button>
                                </div>

                                {risks.length === 0 ? (
                                    <div className="p-10 glass rounded-[2rem] text-center border-dashed border-2 border-white/5">
                                        <p className="text-slate-500 font-black uppercase text-[10px] tracking-widest">Aucun événement historique</p>
                                    </div>
                                ) : (
                                    <div className="space-y-2">
                                        {risks.map((risk, i) => (
                                            <div key={risk._id || i} className="glass p-4 rounded-2xl flex items-center justify-between border border-white/5 text-xs">
                                                <div className="flex items-center gap-4">
                                                    <span className="text-slate-400 font-bold">{friendlyDatasetName(risk)}</span>
                                                    <div className="flex flex-wrap gap-1">
                                                        {(risk.fields || []).map((f) => (
                                                            <span key={f} className="font-mono text-[9px] text-white uppercase bg-slate-800 px-1.5 py-0.5 rounded">{f}</span>
                                                        ))}
                                                    </div>
                                                    <span className="text-slate-600">{new Date(risk.timestamp).toLocaleString()}</span>
                                                </div>
                                                <span className={`font-black px-2 py-1 rounded-lg border ${getScoreStyle(risk.score)}`}>
                                                    {(risk.score * 100).toFixed(0)}%
                                                </span>
                                            </div>
                                        ))}
                                    </div>
                                )}
                            </div>
                        )}
                    </div>
                </div>
            )}

            {/* ================================================================ */}
            {/* ONGLET SUMMARY                                                    */}
            {/* ================================================================ */}
            {activeTab === 'summary' && (
                <div className="space-y-6">

                    {/* En-tête Summary */}
                    <div className="flex items-center justify-between flex-wrap gap-3">
                        <div>
                            <h2 className="text-lg font-bold text-white">
                                Historique des scores
                            </h2>
                            <p className="text-xs text-slate-500 mt-1">
                                Scores de risque déjà calculés et enregistrés pour les datasets
                            </p>
                        </div>

                        <button
                            onClick={fetchDatasetHistory}
                            className="flex items-center gap-2 px-3 py-2 bg-white/5 hover:bg-white/10 rounded-xl border border-white/5 text-xs font-bold text-slate-300"
                        >
                            <RefreshCw
                                size={16}
                                className={isLoadingSummary ? 'animate-spin' : ''}
                            />
                            Actualiser
                        </button>
                    </div>

                    {/* Filtre domaine */}
                    <div className="flex items-center gap-3 bg-white/5 p-1.5 rounded-2xl border border-white/5 w-fit">
                        <div className="relative">
                            <Filter
                                className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-500"
                                size={14}
                            />

                            <input
                                className="bg-transparent pl-9 pr-3 py-2 text-xs font-bold text-slate-300 focus:outline-none placeholder:text-slate-600"
                                placeholder="Filtre domaine"
                                value={domainFilter}
                                onChange={(e) => setDomainFilter(e.target.value)}
                            />
                        </div>
                    </div>

                    {/* Chargement */}
                    {isLoadingSummary && (
                        <div className="p-16 glass rounded-[2.5rem] text-center">
                            <RefreshCw
                                size={28}
                                className="mx-auto text-brand-primary animate-spin"
                            />

                            <p className="text-slate-400 text-xs font-bold mt-4">
                                Récupération des scores historiques...
                            </p>
                        </div>
                    )}

                    {/* Aucun historique */}
                    {!isLoadingSummary && groupedDatasetHistory.length === 0 && (
                        <div className="p-20 glass rounded-[2.5rem] text-center border-dashed border-2 border-white/5">
                            <History
                                size={32}
                                className="mx-auto text-slate-600 mb-4"
                            />

                            <p className="text-slate-500 font-black uppercase text-[10px] tracking-widest">
                                Aucun historique de scores
                            </p>

                            <p className="text-slate-600 text-xs mt-2">
                                Les scores apparaîtront ici après l'analyse des datasets.
                            </p>
                        </div>
                    )}

                    {/* Datasets */}
                    {!isLoadingSummary &&
                        groupedDatasetHistory
                            .filter((dataset) =>
                                !domainFilter ||
                                dataset.domain
                                    .toLowerCase()
                                    .includes(domainFilter.toLowerCase())
                            )
                            .map((dataset, index) => (

                                <motion.div
                                    key={dataset.dataset_id || index}
                                    initial={{ opacity: 0, y: 10 }}
                                    animate={{ opacity: 1, y: 0 }}
                                    className="glass rounded-3xl border border-white/5 overflow-hidden"
                                >

                                    {/* Header dataset */}
                                    <div className="p-6 border-b border-white/5">

                                        <div className="flex items-center justify-between flex-wrap gap-3">

                                            <div>
                                                <h3 className="text-lg font-bold text-white">
                                                    {dataset.dataset_name}
                                                </h3>

                                                <p className="text-xs text-slate-500 mt-1">
                                                    Domaine :{' '}
                                                    <span className="text-brand-primary font-bold">
                                                        {dataset.domain}
                                                    </span>
                                                </p>
                                            </div>

                                            <div className="flex items-center gap-2 text-xs text-slate-500">
                                                <History size={14} />

                                                Dernière analyse :{' '}
                                                <span className="text-slate-300 font-bold">
                                                    {new Date(
                                                        dataset.last_timestamp
                                                    ).toLocaleString()}
                                                </span>
                                            </div>

                                        </div>

                                        {/* Statistiques */}
                                        <div className="grid grid-cols-2 md:grid-cols-4 gap-3 mt-5">

                                            <div className="bg-white/[0.03] p-4 rounded-2xl border border-white/5">
                                                <p className="text-[9px] font-black uppercase tracking-wider text-slate-500">
                                                    Combinaisons
                                                </p>

                                                <p className="text-xl font-extrabold text-white mt-1">
                                                    {dataset.risks.length}
                                                </p>
                                            </div>

                                            <div className="bg-white/[0.03] p-4 rounded-2xl border border-white/5">
                                                <p className="text-[9px] font-black uppercase tracking-wider text-slate-500">
                                                    À risque
                                                </p>

                                                <p className="text-xl font-extrabold text-red-400 mt-1">
                                                    {dataset.combinations_at_risk}
                                                </p>
                                            </div>

                                            <div className="bg-white/[0.03] p-4 rounded-2xl border border-white/5">
                                                <p className="text-[9px] font-black uppercase tracking-wider text-slate-500">
                                                    Score maximum
                                                </p>

                                                <p className="text-xl font-extrabold text-brand-primary mt-1">
                                                    {(dataset.max_score * 100).toFixed(0)}%
                                                </p>
                                            </div>

                                            <div className="bg-white/[0.03] p-4 rounded-2xl border border-white/5">
                                                <p className="text-[9px] font-black uppercase tracking-wider text-slate-500">
                                                    Score moyen
                                                </p>

                                                <p className="text-xl font-extrabold text-white mt-1">
                                                    {(dataset.average_score * 100).toFixed(0)}%
                                                </p>
                                            </div>

                                        </div>
                                    </div>

                                    {/* Scores historiques */}
                                    <div className="overflow-x-auto">

                                        <table className="w-full text-sm">

                                            <thead>
                                                <tr className="border-b border-white/5 text-slate-500 text-[10px] uppercase font-black tracking-wider">

                                                    <th className="text-left px-6 py-3">
                                                        Combinaison
                                                    </th>

                                                    <th className="text-center px-4 py-3">
                                                        k
                                                    </th>

                                                    <th className="text-center px-4 py-3">
                                                        Unicité
                                                    </th>

                                                    <th className="text-center px-4 py-3">
                                                        Sensibilité
                                                    </th>

                                                    <th className="text-center px-4 py-3">
                                                        État
                                                    </th>

                                                    <th className="text-right px-6 py-3">
                                                        Risk Score
                                                    </th>

                                                </tr>
                                            </thead>

                                            <tbody>

                                                {dataset.risks
                                                    .slice()
                                                    .sort((a, b) => b.score - a.score)
                                                    .slice(0, 5)
                                                    .map((risk, i) => (

                                                        <tr
                                                            key={risk._id || `${risk.fields.join('|')}-${i}`}
                                                            className={`border-t border-white/5 ${
                                                                i % 2 === 0
                                                                    ? 'bg-white/[0.02]'
                                                                    : ''
                                                            }`}
                                                        >

                                                            <td className="px-6 py-3">

                                                                <div className="flex flex-wrap gap-1">
                                                                    {risk.fields.map((field) => (
                                                                        <span
                                                                            key={field}
                                                                            className="font-mono text-[9px] text-white uppercase bg-slate-800 px-1.5 py-0.5 rounded"
                                                                        >
                                                                            {field}
                                                                        </span>
                                                                    ))}
                                                                </div>

                                                            </td>

                                                            <td className="px-4 py-3 text-center text-slate-300 font-bold">
                                                                {risk.k}
                                                            </td>

                                                            <td className="px-4 py-3 text-center text-slate-300">
                                                                {(risk.uniqueness ?? 0).toFixed(2)}
                                                            </td>

                                                            <td className="px-4 py-3 text-center text-slate-300">
                                                                {risk.avg_sensitivity !== undefined
                                                                    ? risk.avg_sensitivity.toFixed(2)
                                                                    : '—'}
                                                            </td>

                                                            <td className="px-4 py-3 text-center">

                                                                {risk.triggered ? (
                                                                    <span className="inline-flex items-center gap-1 px-2 py-1 rounded-lg bg-red-500/10 text-red-400 border border-red-500/20 text-[9px] font-black uppercase">
                                                                        <ShieldAlert size={11} />
                                                                        À risque
                                                                    </span>
                                                                ) : (
                                                                    <span className="inline-flex items-center gap-1 px-2 py-1 rounded-lg bg-emerald-500/10 text-emerald-400 border border-emerald-500/20 text-[9px] font-black uppercase">
                                                                        <CheckCircle2 size={11} />
                                                                        Faible
                                                                    </span>
                                                                )}

                                                            </td>

                                                            <td className="px-6 py-3 text-right">

                                                                <span
                                                                    className={`inline-block px-3 py-1 rounded-lg border font-black text-xs ${getScoreStyle(
                                                                        risk.score
                                                                    )}`}
                                                                >
                                                                    {risk.score.toFixed(2)}
                                                                </span>

                                                            </td>

                                                        </tr>

                                                    ))}

                                            </tbody>

                                        </table>

                                    </div>

                                </motion.div>

                            ))}

                </div>
            )}


                        {/* ================================================================ */}
                        {/* ONGLET CONFIGURATION (admin uniquement)                          */}
                        {/* ================================================================ */}
                        {activeTab === 'config' && isAdmin && (
                            <div className="space-y-6">
                                <div className="glass p-6 rounded-3xl flex items-end gap-4 border border-white/5 flex-wrap">
                                    <div className="flex-1 space-y-2 min-w-[200px]">
                                        <label className="text-[10px] font-black text-slate-400 uppercase tracking-widest ml-1">Domaine</label>
                                        <input
                                            className="input-premium w-full placeholder:text-slate-600 text-xs"
                                            placeholder="ex: RH, Finance, Sante"
                                            value={configDomain}
                                            onChange={(e) => setConfigDomain(e.target.value)}
                                        />
                                    </div>
                                    <div className="w-40 space-y-2">
                                        <label className="text-[10px] font-black text-slate-400 uppercase tracking-widest ml-1">Seuil (0-1)</label>
                                        <input
                                            type="number"
                                            min={0}
                                            max={1}
                                            step={0.05}
                                            className="input-premium w-full text-xs"
                                            value={configValue}
                                            onChange={(e) => setConfigValue(parseFloat(e.target.value) || 0)}
                                        />
                                    </div>
                                    <Button variant="primary" onClick={handleSaveThreshold} className="h-11 px-6 text-xs">
                                        <Save size={18} className="mr-2" />
                                        Enregistrer
                                    </Button>
                                </div>

                                <div className="space-y-3">
                                    {thresholds.length === 0 ? (
                                        <p className="text-slate-500 text-sm italic">Aucun seuil configuré pour le moment.</p>
                                    ) : (
                                        thresholds.map((t) => (
                                            <div key={t.domain} className="glass p-4 rounded-2xl flex items-center justify-between border border-white/5">
                                                <span className="font-bold text-white text-xs">{t.domain}</span>
                                                <span className="text-brand-primary font-mono bg-brand-primary/10 px-3 py-1 rounded-lg border border-brand-primary/20 text-xs">
                                                    {t.threshold}
                                                </span>
                                            </div>
                                        ))
                                    )}
                                </div>
                            </div>
                        )}
                    </div>
                );
            };

// ============================================================================
// Nuage de points — style croquis : axes fléchés, labels "Risk Score" /
// "Combinaisons", annotation sur le point le plus haut ("← combinaison N")
// ============================================================================

interface RiskScatterChartProps {
    results: RiskEvent[];
    getColor: (score: number) => string;
}

const RiskScatterChart: React.FC<RiskScatterChartProps> = ({ results, getColor }) => {
    const width = 760;
    const height = 260;
    const padding = { top: 30, right: 40, bottom: 40, left: 50 };
    const plotWidth = width - padding.left - padding.right;
    const plotHeight = height - padding.top - padding.bottom;

    // Ordre d'affichage : ordre naturel des combinaisons testées (index = position X),
    // pas trié par score, pour que "combinaison N" corresponde à un numéro stable.
    const points = results;
    const n = points.length;

    const yMin = 0.4;
    const yMax = 1.0;
    const yTicks = [0.4, 0.6, 0.8, 1.0];

    const xFor = (i: number) => padding.left + (n <= 1 ? plotWidth / 2 : (i / Math.max(n - 1, 1)) * plotWidth);
    const yFor = (score: number) => {
        const clamped = Math.max(yMin, Math.min(yMax, score));
        return padding.top + (1 - (clamped - yMin) / (yMax - yMin)) * plotHeight;
    };

    // Point le plus haut (score max) — annoté par une flèche, comme dans le croquis
    const maxIndex = points.reduce((best, p, i) => (p.score > points[best].score ? i : best), 0);

    return (
        <svg viewBox={`0 0 ${width} ${height}`} className="w-full h-auto" style={{ maxHeight: 300 }}>
            {/* Axe Y fléché + label "Risk Score" */}
            <line
                x1={padding.left}
                x2={padding.left}
                y1={padding.top - 15}
                y2={height - padding.bottom}
                stroke="#94a3b8"
                strokeWidth={1.5}
            />
            <polygon
                points={`${padding.left - 5},${padding.top - 15} ${padding.left + 5},${padding.top - 15} ${padding.left},${padding.top - 24}`}
                fill="#94a3b8"
            />
            <text x={padding.left - 8} y={padding.top - 26} fontSize={12} fill="#e2e8f0" fontWeight={600}>
                Risk Score
            </text>

            {/* Ticks Y */}
            {yTicks.map((t) => (
                <g key={t}>
                    <line x1={padding.left - 4} x2={padding.left} y1={yFor(t)} y2={yFor(t)} stroke="#94a3b8" strokeWidth={1.5} />
                    <text x={padding.left - 10} y={yFor(t) + 4} textAnchor="end" fontSize={11} fill="#94a3b8">
                        {t.toFixed(1)}
                    </text>
                </g>
            ))}

            {/* Axe X fléché + label "Combinaisons" */}
            <line
                x1={padding.left}
                x2={width - padding.right + 15}
                y1={height - padding.bottom}
                y2={height - padding.bottom}
                stroke="#94a3b8"
                strokeWidth={1.5}
            />
            <polygon
                points={`${width - padding.right + 15},${height - padding.bottom - 5} ${width - padding.right + 15},${height - padding.bottom + 5} ${width - padding.right + 24},${height - padding.bottom}`}
                fill="#94a3b8"
            />
            <text x={width - padding.right + 30} y={height - padding.bottom + 4} fontSize={12} fill="#e2e8f0" fontWeight={600}>
                Combinaisons
            </text>

            {/* Points + labels X */}
            {points.map((r, i) => (
                <g key={r.fields.join('|')}>
                    <circle cx={xFor(i)} cy={yFor(r.score)} r={5} fill={getColor(r.score)} opacity={0.95}>
                        <title>{`Combinaison ${i + 1} : ${r.fields.join(' + ')} — score ${r.score.toFixed(2)} (k=${r.k})`}</title>
                    </circle>
                    <text x={xFor(i)} y={height - padding.bottom + 18} textAnchor="middle" fontSize={11} fill="#94a3b8">
                        {i + 1}
                    </text>
                </g>
            ))}

            {/* Annotation flèche sur le point le plus à risque */}
            {n > 0 && (
                <g>
                    <line
                        x1={xFor(maxIndex) + 10}
                        x2={xFor(maxIndex) + 28}
                        y1={yFor(points[maxIndex].score)}
                        y2={yFor(points[maxIndex].score)}
                        stroke="#f87171"
                        strokeWidth={1.5}
                    />
                    <polygon
                        points={`${xFor(maxIndex) + 10},${yFor(points[maxIndex].score) - 4} ${xFor(maxIndex) + 10},${yFor(points[maxIndex].score) + 4} ${xFor(maxIndex) + 2},${yFor(points[maxIndex].score)}`}
                        fill="#f87171"
                    />
                    <text
                        x={xFor(maxIndex) + 32}
                        y={yFor(points[maxIndex].score) + 4}
                        fontSize={11}
                        fill="#f87171"
                        fontWeight={600}
                    >
                        combinaison {maxIndex + 1}
                    </text>
                </g>
            )}
        </svg>
    );
};

export default StreamShieldPage;
