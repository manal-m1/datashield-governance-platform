import { useState, useEffect } from 'react';
import { X, CheckCircle2, AlertTriangle, Tag, ChevronDown, ChevronRight, ShieldCheck, Eye, EyeOff } from 'lucide-react';
import { motion, AnimatePresence } from 'framer-motion';
import { Button } from '../components/ui/Button';
import { useAuthStore } from '../store/authStore';

export type SensitivityLevel = 'faible' | 'moyen' | 'eleve' | 'critique' | '';

export interface DetectionEnrichment {
    entity_type: string;
    value: string;
    sensitivity_level: SensitivityLevel;
    context: string;
}

interface TaskDetailsModalProps {
    isOpen: boolean;
    onClose: () => void;
    task: any;
    onValidate: (id: string, enrichments?: DetectionEnrichment[]) => void;
    onReject: (id: string) => void;
}

const SENSITIVITY_OPTIONS: { value: SensitivityLevel; label: string; color: string }[] = [
    { value: 'faible', label: 'Faible', color: 'text-emerald-400 border-emerald-500/30 bg-emerald-500/10' },
    { value: 'moyen', label: 'Moyen', color: 'text-yellow-400 border-yellow-500/30 bg-yellow-500/10' },
    { value: 'eleve', label: 'Élevé', color: 'text-orange-400 border-orange-500/30 bg-orange-500/10' },
    { value: 'critique', label: 'Critique', color: 'text-red-400 border-red-500/30 bg-red-500/10' },
];

// Style du badge pour un niveau de sensibilité donné (utilisé côté Steward)
const getSensitivityStyle = (level: SensitivityLevel) => {
    const found = SENSITIVITY_OPTIONS.find(o => o.value === level);
    return found ? found.color : 'text-slate-500 border-slate-800 bg-slate-900/40';
};

// Masque une valeur selon la sensibilité proposée par l'Annotator.
// - critique / eleve : masquage fort (1er + dernier caractère seulement)
// - moyen : masquage partiel (2 caractères de chaque côté)
// - faible / non qualifié : affichage en clair
const maskValueBySensitivity = (value: string, level: SensitivityLevel): string => {
    if (!value) return '';
    if (level === 'critique' || level === 'eleve') {
        if (value.length <= 2) return '•'.repeat(Math.max(value.length, 4));
        return `${value[0]}${'•'.repeat(Math.max(value.length - 2, 3))}${value[value.length - 1]}`;
    }
    if (level === 'moyen') {
        if (value.length <= 4) return `${value[0]}${'•'.repeat(value.length - 1)}`;
        return `${value.slice(0, 2)}${'•'.repeat(value.length - 4)}${value.slice(-2)}`;
    }
    return value; // 'faible' ou pas encore qualifié -> valeur en clair
};

const TaskDetailsModal = ({ isOpen, onClose, task, onValidate, onReject }: TaskDetailsModalProps) => {
    const [isDetectionsOpen, setIsDetectionsOpen] = useState(true);
    const [enrichments, setEnrichments] = useState<Record<string, DetectionEnrichment & { key: string }>>({});
    const [revealedKeys, setRevealedKeys] = useState<Record<string, boolean>>({});

    const currentRole = (useAuthStore.getState().user?.role || '').toLowerCase();
    // Seul l'annotator qualifie les détections (sensibilité + contexte)
    const canAnnotate = currentRole.includes('annotator');
    // Le Data Steward consulte la qualification déjà faite par l'Annotator, en lecture seule, avec masquage
    const canReview = currentRole.includes('steward');

    useEffect(() => {
        if (task) {
            // Les annotations soumises par l'Annotator ont "field" = entity_type (pas de clé unique),
            // donc on les regroupe par type et on les redistribue DANS L'ORDRE aux détections du même type
            // (même ordre que celui utilisé lors de la soumission côté TaskQueuePage).
            const annotationsByField: Record<string, any[]> = {};
            (task.annotations || []).forEach((a: any) => {
                if (!a || !a.field) return;
                if (!annotationsByField[a.field]) annotationsByField[a.field] = [];
                annotationsByField[a.field].push(a);
            });

            const initial: Record<string, DetectionEnrichment & { key: string }> = {};
            (task.detections || []).forEach((det: any, idx: number) => {
                const type = det.entity_type || 'Unknown';
                const key = `${type}__${idx}`;
                const queue = annotationsByField[type];
                const matched = queue && queue.length ? queue.shift() : null;

                initial[key] = {
                    key,
                    entity_type: type,
                    value: det.value,
                    sensitivity_level: (matched?.sensitivity_level as SensitivityLevel) || '',
                    context: matched?.context || '',
                };
            });
            setEnrichments(initial);
            setRevealedKeys({});
        }
    }, [task]);

    if (!isOpen || !task) return null;

    const groupedDetections = (task.detections || []).reduce((acc: any, det: any) => {
        const type = det.entity_type || 'Unknown';
        if (!acc[type]) acc[type] = [];
        acc[type].push(det);
        return acc;
    }, {});

    const handleSensitivityChange = (key: string, level: SensitivityLevel) => {
        setEnrichments(prev => ({ ...prev, [key]: { ...prev[key], sensitivity_level: level } }));
    };

    const handleContextChange = (key: string, context: string) => {
        setEnrichments(prev => ({ ...prev, [key]: { ...prev[key], context } }));
    };

    const toggleReveal = (key: string) => {
        setRevealedKeys(prev => ({ ...prev, [key]: !prev[key] }));
    };

    const buildEnrichmentsList = (): DetectionEnrichment[] =>
        Object.values(enrichments).map(({ key, ...rest }) => rest);

    const handleSave = () => {
        onValidate(task.id, buildEnrichmentsList());
    };

    return (
        <AnimatePresence>
            {isOpen && (
                <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
                    <motion.div
                        initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}
                        onClick={onClose}
                        className="fixed inset-0 bg-black/60 backdrop-blur-sm"
                        aria-hidden="true"
                    />

                    <motion.div
                        initial={{ scale: 0.95, opacity: 0, y: 20 }}
                        animate={{ scale: 1, opacity: 1, y: 0 }}
                        exit={{ scale: 0.95, opacity: 0, y: 20 }}
                        className="relative bg-[#0f172a] border border-white/10 rounded-3xl p-8 max-w-2xl w-full shadow-2xl overflow-hidden z-10 flex flex-col max-h-[90vh]"
                    >
                        <div className="flex justify-between items-start mb-6 flex-shrink-0">
                            <div>
                                <h3 className="text-2xl font-bold text-white mb-2">Task Analysis</h3>
                                <p className="text-slate-400 text-sm">Reviewing detection for <span className="text-brand-primary font-mono">{task.id.split('-')[0]}</span></p>
                            </div>
                            <button onClick={onClose} className="p-2 hover:bg-white/5 rounded-full text-slate-400 transition-colors">
                                <X size={20} />
                            </button>
                        </div>

                        <div className="space-y-6 overflow-y-auto pr-2 custom-scrollbar">
                            {/* Detections Panel - résumé */}
                            <div className={`rounded-lg border ${isDetectionsOpen ? 'border-red-500/30 bg-red-500/5' : 'border-slate-800 bg-slate-900/50 hover:border-slate-700'} transition-colors overflow-hidden flex-shrink-0`}>
                                <button
                                    onClick={() => setIsDetectionsOpen(!isDetectionsOpen)}
                                    className="w-full flex items-center justify-between p-4"
                                >
                                    <div className="flex items-center gap-3">
                                        <AlertTriangle className={`w-5 h-5 ${task.detections?.length > 0 ? 'text-red-400' : 'text-slate-400'}`} />
                                        <span className={`font-medium ${task.detections?.length > 0 ? 'text-red-200' : 'text-slate-400'}`}>
                                            DETECTED ISSUES ({task.detections?.length || 0})
                                        </span>
                                    </div>
                                    {isDetectionsOpen ? <ChevronDown className="w-4 h-4 text-slate-500" /> : <ChevronRight className="w-4 h-4 text-slate-500" />}
                                </button>

                                <AnimatePresence>
                                    {isDetectionsOpen && (
                                        <motion.div
                                            initial={{ height: 0 }}
                                            animate={{ height: 'auto' }}
                                            exit={{ height: 0 }}
                                            className="overflow-hidden"
                                        >
                                            <div className="p-4 pt-0 space-y-2 border-t border-red-500/10">
                                                {Object.entries(groupedDetections || {}).map(([type, items]: [string, any]) => (
                                                    <div key={type} className="flex items-center justify-between p-2 bg-slate-950/50 rounded border border-slate-800/50">
                                                        <div className="flex items-center gap-2">
                                                            <span className="font-mono text-xs text-white uppercase bg-slate-800 px-1.5 py-0.5 rounded">{type}</span>
                                                            {items.length > 1 && <span className="text-xs text-slate-500">x{items.length}</span>}
                                                        </div>
                                                        <span className="text-xs font-mono text-red-300 bg-red-500/10 px-1.5 py-0.5 rounded">
                                                            {Math.round(Math.max(...items.map((i: any) => i.score || 0)) * 100)}% Conf.
                                                        </span>
                                                    </div>
                                                ))}
                                                {(!task.detections || task.detections.length === 0) && (
                                                    <p className="text-sm text-slate-500 italic p-2">No issues detected automatically.</p>
                                                )}
                                            </div>
                                        </motion.div>
                                    )}
                                </AnimatePresence>
                            </div>

                            {/* Annotation - sensibilité + contexte par détection (rôle Annotator) */}
                            {canAnnotate && (
                                <div className="space-y-3">
                                    <div className="flex items-center gap-2">
                                        <Tag size={14} className="text-slate-500" />
                                        <h4 className="text-slate-500 font-bold text-xs uppercase tracking-wider">Qualification des détections</h4>
                                    </div>

                                    <div className="space-y-3">
                                        {Object.values(enrichments).length === 0 && (
                                            <p className="text-xs text-slate-500 italic">Aucune détection à qualifier pour cette tâche.</p>
                                        )}
                                        {Object.values(enrichments).map((e) => (
                                            <div key={e.key} className="flex flex-col gap-2.5 p-3 bg-slate-900/60 border border-slate-800 rounded-lg">
                                                <div className="flex items-center justify-between">
                                                    <span className="font-mono text-[10px] text-white uppercase bg-slate-800 px-1.5 py-0.5 rounded">
                                                        {e.entity_type}
                                                    </span>
                                                    <code className="text-[10px] text-slate-500 truncate max-w-[180px]" title={e.value}>
                                                        {e.value}
                                                    </code>
                                                </div>

                                                <div className="flex gap-2">
                                                    {SENSITIVITY_OPTIONS.map(opt => (
                                                        <button
                                                            key={opt.value}
                                                            onClick={() => handleSensitivityChange(e.key, opt.value)}
                                                            className={`flex-1 text-[10px] font-bold py-1.5 rounded border transition-colors ${
                                                                e.sensitivity_level === opt.value
                                                                    ? opt.color
                                                                    : 'text-slate-500 border-slate-800 hover:border-slate-700'
                                                            }`}
                                                        >
                                                            {opt.label}
                                                        </button>
                                                    ))}
                                                </div>

                                                <textarea
                                                    value={e.context}
                                                    onChange={(ev) => handleContextChange(e.key, ev.target.value)}
                                                    placeholder="Contexte (ex: donnée client visible dans un export interne, usage RH...)"
                                                    className="bg-slate-900 border border-slate-700 rounded px-3 py-2 text-slate-200 focus:border-brand-primary focus:outline-none min-h-[60px] text-xs leading-relaxed"
                                                />
                                            </div>
                                        ))}
                                    </div>
                                </div>
                            )}

                            {/* Revue Steward - sensibilité + contexte en lecture seule, valeur masquée */}
                            {canReview && (
                                <div className="space-y-3">
                                    <div className="flex items-center gap-2">
                                        <ShieldCheck size={14} className="text-slate-500" />
                                        <h4 className="text-slate-500 font-bold text-xs uppercase tracking-wider">Sensibilité proposée par l'Annotator</h4>
                                    </div>

                                    <div className="space-y-3">
                                        {Object.values(enrichments).length === 0 && (
                                            <p className="text-xs text-slate-500 italic">Aucune détection à examiner pour cette tâche.</p>
                                        )}
                                        {Object.values(enrichments).map((e) => {
                                            const isRevealed = !!revealedKeys[e.key];
                                            const displayValue = isRevealed ? e.value : maskValueBySensitivity(e.value, e.sensitivity_level);
                                            const notQualified = !e.sensitivity_level;

                                            return (
                                                <div key={e.key} className="flex flex-col gap-2.5 p-3 bg-slate-900/60 border border-slate-800 rounded-lg">
                                                    <div className="flex items-center justify-between">
                                                        <div className="flex items-center gap-2">
                                                            <span className="font-mono text-[10px] text-white uppercase bg-slate-800 px-1.5 py-0.5 rounded">
                                                                {e.entity_type}
                                                            </span>
                                                            <span className={`text-[10px] font-bold px-1.5 py-0.5 rounded border ${getSensitivityStyle(e.sensitivity_level)}`}>
                                                                {notQualified ? 'Non qualifié' : SENSITIVITY_OPTIONS.find(o => o.value === e.sensitivity_level)?.label}
                                                            </span>
                                                        </div>
                                                        <button
                                                            onClick={() => toggleReveal(e.key)}
                                                            className="flex items-center gap-1 text-[10px] text-slate-400 hover:text-slate-200 transition-colors"
                                                            title={isRevealed ? 'Masquer la valeur' : 'Voir la valeur en clair'}
                                                        >
                                                            {isRevealed ? <EyeOff size={12} /> : <Eye size={12} />}
                                                            {isRevealed ? 'Masquer' : 'Voir'}
                                                        </button>
                                                    </div>

                                                    <code className="text-xs text-slate-300 bg-slate-950/50 px-2 py-1.5 rounded border border-slate-800 break-all">
                                                        {displayValue}
                                                    </code>

                                                    {e.context ? (
                                                        <p className="text-xs text-slate-400 leading-relaxed italic border-l-2 border-slate-700 pl-2">
                                                            {e.context}
                                                        </p>
                                                    ) : (
                                                        <p className="text-xs text-slate-600 italic">Aucun contexte renseigné.</p>
                                                    )}
                                                </div>
                                            );
                                        })}
                                    </div>
                                </div>
                            )}
                        </div>

                        {/* Actions */}
                        <div className="flex gap-4 mt-8 pt-6 border-t border-white/5">
                            <Button
                                variant="ghost"
                                className="flex-1 bg-red-500/10 text-red-500 hover:bg-red-500/20 border-red-500/20"
                                onClick={() => onReject(task.id)}
                            >
                                <X size={18} className="mr-2" />
                                {canReview ? 'Send Back' : 'Reject (Not PII)'}
                            </Button>

                            <Button
                                variant="primary"
                                className="flex-1 bg-green-500 hover:bg-green-600 border-green-500"
                                onClick={handleSave}
                            >
                                <CheckCircle2 size={18} className="mr-2" />
                                {canReview ? 'Approve' : 'Confirm & Submit'}
                            </Button>
                        </div>
                    </motion.div>
                </div>
            )}
        </AnimatePresence>
    );
};

export default TaskDetailsModal;