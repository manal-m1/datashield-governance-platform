import { useState, useEffect } from 'react';
import {
    X,
    CheckCircle2,
    AlertTriangle,
    Tag,
    ChevronDown,
    ChevronRight,
    ShieldCheck,
    Eye,
    EyeOff,
    Edit3
} from 'lucide-react';
import { motion, AnimatePresence } from 'framer-motion';
import { Button } from '../components/ui/Button';
import { useAuthStore } from '../store/authStore';

export type SensitivityLevel =
    | 'faible'
    | 'moyen'
    | 'eleve'
    | 'critique'
    | '';

export interface DetectionEnrichment {
    key?: string;

    /**
     * Type originally returned by the automatic PII detector.
     */
    original_entity_type: string;

    /**
     * Current entity type.
     * For Labeler this can be changed.
     * For Annotator/Steward it remains read-only.
     */
    entity_type: string;

    value: string;

    /**
     * Added by the Data Annotator.
     */
    sensitivity_level: SensitivityLevel;

    /**
     * Added by the Data Annotator.
     */
    context: string;
}

interface TaskDetailsModalProps {
    isOpen: boolean;
    onClose: () => void;
    task: any;

    onValidate: (
        id: string,
        enrichments?: DetectionEnrichment[],
        applyMasking?: boolean
    ) => void;

    onReject: (id: string) => void;
}

/**
 * Sensitivity levels used by the Data Annotator.
 */
const SENSITIVITY_OPTIONS: {
    value: SensitivityLevel;
    label: string;
    color: string;
}[] = [
    {
        value: 'faible',
        label: 'Faible',
        color: 'text-emerald-400 border-emerald-500/30 bg-emerald-500/10'
    },
    {
        value: 'moyen',
        label: 'Moyen',
        color: 'text-yellow-400 border-yellow-500/30 bg-yellow-500/10'
    },
    {
        value: 'eleve',
        label: 'Élevé',
        color: 'text-orange-400 border-orange-500/30 bg-orange-500/10'
    },
    {
        value: 'critique',
        label: 'Critique',
        color: 'text-red-400 border-red-500/30 bg-red-500/10'
    }
];

/**
 * Entity types available to the Data Labeler.
 *
 * Add/remove values here according to the recognizers
 * actually configured in the PII Detection service.
 */
const ENTITY_TYPE_OPTIONS = [
    'PERSON',
    'EMAIL_ADDRESS',
    'PHONE_NUMBER',
    'IBAN',
    'CREDIT_CARD',
    'IP_ADDRESS',
    'LOCATION',
    'DATE_TIME',

    // Moroccan PII
    'CIN_MAROC',
    'PHONE_MA',
    'IBAN_MA',
    'CNSS',
    'PASSPORT_MA',
    'PERMIS_MA',
    'ARABIC_MOROCCAN_PII'
];

/**
 * Badge style for sensitivity.
 */
const getSensitivityStyle = (
    level: SensitivityLevel
): string => {
    const found = SENSITIVITY_OPTIONS.find(
        option => option.value === level
    );

    return found
        ? found.color
        : 'text-slate-500 border-slate-800 bg-slate-900/40';
};

/**
 * Privacy-safe display only.
 *
 * IMPORTANT:
 * This is NOT the actual EthiMask policy.
 * It is only used to avoid exposing sensitive values
 * unnecessarily in the Steward interface.
 */
const maskValueForPreview = (
    value: string,
    level: SensitivityLevel
): string => {
    if (!value) return '';

    if (level === 'critique' || level === 'eleve') {
        if (value.length <= 2) {
            return '•'.repeat(Math.max(value.length, 4));
        }

        return `${value[0]}${'•'.repeat(
            Math.max(value.length - 2, 3)
        )}${value[value.length - 1]}`;
    }

    if (level === 'moyen') {
        if (value.length <= 4) {
            return `${value[0]}${'•'.repeat(
                Math.max(value.length - 1, 1)
            )}`;
        }

        return `${value.slice(0, 2)}${'•'.repeat(
            value.length - 4
        )}${value.slice(-2)}`;
    }

    return value;
};

const TaskDetailsModal = ({
    isOpen,
    onClose,
    task,
    onValidate,
    onReject
}: TaskDetailsModalProps) => {
    const [isDetectionsOpen, setIsDetectionsOpen] =
        useState(true);

    const [enrichments, setEnrichments] = useState<
        Record<string, DetectionEnrichment & { key: string }>
    >({});

    const [revealedKeys, setRevealedKeys] = useState<
        Record<string, boolean>
    >({});

    const [applyMasking, setApplyMasking] = useState(false);

    /**
     * Reactive role.
     *
     * Do not use useAuthStore.getState() here because
     * the component would not react to role changes.
     */
    const currentRole = useAuthStore(
        state => (state.user?.role || '').toLowerCase()
    );

    const isLabeler = currentRole.includes('labeler');
    const isAnnotator = currentRole.includes('annotator');
    const isSteward = currentRole.includes('steward');

    useEffect(() => {
        if (!task) {
            setEnrichments({});
            setRevealedKeys({});
            setApplyMasking(false);
            return;
        }

        /**
         * Existing annotations are grouped by field.
         *
         * This preserves compatibility with the existing backend
         * where annotations are associated with entity_type.
         */
        const annotationsByField: Record<string, any[]> = {};

        (task.annotations || []).forEach((annotation: any) => {
            if (!annotation || !annotation.field) return;

            if (!annotationsByField[annotation.field]) {
                annotationsByField[annotation.field] = [];
            }

            annotationsByField[annotation.field].push(annotation);
        });

        const initial: Record<
            string,
            DetectionEnrichment & { key: string }
        > = {};

        (task.detections || []).forEach(
            (det: any, index: number) => {
                const detectedType =
                    det.entity_type || 'Unknown';

                const key = `${detectedType}__${index}`;

                const queue =
                    annotationsByField[detectedType];

                const matched =
                    queue && queue.length
                        ? queue.shift()
                        : null;

                /**
                 * If a previous Labeler correction exists,
                 * restore it.
                 */
                const correctedType =
                    matched?.corrected_entity_type ||
                    matched?.corrected_data ||
                    detectedType;

                initial[key] = {
                    key,

                    original_entity_type: detectedType,

                    entity_type: correctedType,

                    value: det.value || '',

                    sensitivity_level:
                        (matched?.sensitivity_level as SensitivityLevel) ||
                        '',

                    context: matched?.context || ''
                };
            }
        );

        setEnrichments(initial);
        setRevealedKeys({});
        setApplyMasking(false);
    }, [task]);

    if (!isOpen || !task) {
        return null;
    }

    /**
     * Detection summary.
     */
    const detectionsByType: Record<string, any[]> = (
        task.detections || []
    ).reduce(
        (acc: Record<string, any[]>, det: any) => {
            const type = det.entity_type || 'Unknown';

            if (!acc[type]) {
                acc[type] = [];
            }

            acc[type].push(det);

            return acc;
        },
        {} as Record<string, any[]>
    );

    /**
     * Labeler changes the entity type.
     */
    const handleEntityTypeChange = (
        key: string,
        entityType: string
    ) => {
        setEnrichments(prev => ({
            ...prev,
            [key]: {
                ...prev[key],
                entity_type: entityType
            }
        }));
    };

    /**
     * Annotator changes sensitivity.
     */
    const handleSensitivityChange = (
        key: string,
        level: SensitivityLevel
    ) => {
        setEnrichments(prev => ({
            ...prev,
            [key]: {
                ...prev[key],
                sensitivity_level: level
            }
        }));
    };

    /**
     * Annotator changes business/context information.
     */
    const handleContextChange = (
        key: string,
        context: string
    ) => {
        setEnrichments(prev => ({
            ...prev,
            [key]: {
                ...prev[key],
                context
            }
        }));
    };

    const toggleReveal = (key: string) => {
        setRevealedKeys(prev => ({
            ...prev,
            [key]: !prev[key]
        }));
    };

    const buildEnrichmentsList =
        (): DetectionEnrichment[] =>
            Object.values(enrichments).map(
                ({ key, ...rest }) => rest
            );

    const handleSave = () => {
        onValidate(
            task.id,
            buildEnrichmentsList(),
            isSteward ? applyMasking : false
        );
    };

    /**
     * Determine which role is currently operating.
     */
    const getRoleTitle = () => {
        if (isLabeler) return 'Labeler Review';
        if (isAnnotator) return 'Annotation Review';
        if (isSteward) return 'Steward Review';

        return 'Task Analysis';
    };

    const getRoleDescription = () => {
        if (isLabeler) {
            return 'Verify and correct the detected entity category.';
        }

        if (isAnnotator) {
            return 'Add sensitivity and business context to validated entities.';
        }

        if (isSteward) {
            return 'Review the qualification before final approval.';
        }

        return 'Reviewing the detected data.';
    };

    return (
        <AnimatePresence>
            {isOpen && (
                <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
                    <motion.div
                        initial={{ opacity: 0 }}
                        animate={{ opacity: 1 }}
                        exit={{ opacity: 0 }}
                        onClick={onClose}
                        className="fixed inset-0 bg-black/60 backdrop-blur-sm"
                        aria-hidden="true"
                    />

                    <motion.div
                        initial={{
                            scale: 0.95,
                            opacity: 0,
                            y: 20
                        }}
                        animate={{
                            scale: 1,
                            opacity: 1,
                            y: 0
                        }}
                        exit={{
                            scale: 0.95,
                            opacity: 0,
                            y: 20
                        }}
                        className="relative bg-[#0f172a] border border-white/10 rounded-3xl p-8 max-w-2xl w-full shadow-2xl overflow-hidden z-10 flex flex-col max-h-[90vh]"
                    >
                        {/* HEADER */}
                        <div className="flex justify-between items-start mb-6 flex-shrink-0">
                            <div>
                                <h3 className="text-2xl font-bold text-white mb-2">
                                    {getRoleTitle()}
                                </h3>

                                <p className="text-slate-400 text-sm">
                                    {getRoleDescription()}
                                </p>

                                <p className="text-slate-500 text-xs mt-2">
                                    Task:{' '}
                                    <span className="text-brand-primary font-mono">
                                        {task.id.split('-')[0]}
                                    </span>
                                </p>
                            </div>

                            <button
                                onClick={onClose}
                                className="p-2 hover:bg-white/5 rounded-full text-slate-400 transition-colors"
                            >
                                <X size={20} />
                            </button>
                        </div>

                        <div className="space-y-6 overflow-y-auto pr-2 custom-scrollbar">

                            {/* DETECTION SUMMARY */}
                            <div
                                className={`rounded-lg border ${
                                    isDetectionsOpen
                                        ? 'border-red-500/30 bg-red-500/5'
                                        : 'border-slate-800 bg-slate-900/50 hover:border-slate-700'
                                } transition-colors overflow-hidden flex-shrink-0`}
                            >
                                <button
                                    onClick={() =>
                                        setIsDetectionsOpen(
                                            !isDetectionsOpen
                                        )
                                    }
                                    className="w-full flex items-center justify-between p-4"
                                >
                                    <div className="flex items-center gap-3">
                                        <AlertTriangle
                                            className={`w-5 h-5 ${
                                                task.detections?.length > 0
                                                    ? 'text-red-400'
                                                    : 'text-slate-400'
                                            }`}
                                        />

                                        <span
                                            className={`font-medium ${
                                                task.detections?.length > 0
                                                    ? 'text-red-200'
                                                    : 'text-slate-400'
                                            }`}
                                        >
                                            DETECTED ISSUES (
                                            {task.detections?.length || 0}
                                            )
                                        </span>
                                    </div>

                                    {isDetectionsOpen ? (
                                        <ChevronDown
                                            className="w-4 h-4 text-slate-500"
                                        />
                                    ) : (
                                        <ChevronRight
                                            className="w-4 h-4 text-slate-500"
                                        />
                                    )}
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
                                                {(Object.entries(detectionsByType) as [string, any[]][]).map(
    ([type, items]) => (
                                                        <div
                                                            key={type}
                                                            className="flex items-center justify-between p-2 bg-slate-950/50 rounded border border-slate-800/50"
                                                        >
                                                            <div className="flex items-center gap-2">
                                                                <span className="font-mono text-xs text-white uppercase bg-slate-800 px-1.5 py-0.5 rounded">
                                                                    {type}
                                                                </span>

                                                                {items.length >
                                                                    1 && (
                                                                    <span className="text-xs text-slate-500">
                                                                        x
                                                                        {
                                                                            items.length
                                                                        }
                                                                    </span>
                                                                )}
                                                            </div>

                                                            <span className="text-xs font-mono text-red-300 bg-red-500/10 px-1.5 py-0.5 rounded">
                                                                {Math.round(
                                                                    Math.max(
                                                                        ...items.map(
                                                                            (
                                                                                item: any
                                                                            ) =>
                                                                                item.score ||
                                                                                0
                                                                        )
                                                                    ) * 100
                                                                )}
                                                                % Conf.
                                                            </span>
                                                        </div>
                                                    )
                                                )}

                                                {(!task.detections ||
                                                    task.detections.length ===
                                                        0) && (
                                                    <p className="text-sm text-slate-500 italic p-2">
                                                        No issues detected
                                                        automatically.
                                                    </p>
                                                )}
                                            </div>
                                        </motion.div>
                                    )}
                                </AnimatePresence>
                            </div>

                            {/* =====================================================
                                LABELER
                               ===================================================== */}
                            {isLabeler && (
                                <div className="space-y-3">
                                    <div className="flex items-center gap-2">
                                        <Edit3
                                            size={14}
                                            className="text-brand-primary"
                                        />

                                        <h4 className="text-slate-300 font-bold text-xs uppercase tracking-wider">
                                            Entity Type Verification
                                        </h4>
                                    </div>

                                    <p className="text-xs text-slate-500">
                                        Verify the entity category assigned
                                        by the automatic PII detector and
                                        correct it when necessary.
                                    </p>

                                    <div className="space-y-3">
                                        {Object.values(
                                            enrichments
                                        ).map(e => {
                                            const isCorrected =
                                                e.entity_type !==
                                                e.original_entity_type;

                                            return (
                                                <div
                                                    key={e.key}
                                                    className="p-4 bg-slate-900/60 border border-slate-800 rounded-lg space-y-3"
                                                >
                                                    <div className="flex items-center justify-between">
                                                        <span className="text-[10px] uppercase font-black tracking-wider text-slate-500">
                                                            Detected value
                                                        </span>

                                                        <code
                                                            className="text-xs text-slate-300 truncate max-w-[260px]"
                                                            title={e.value}
                                                        >
                                                            {e.value}
                                                        </code>
                                                    </div>

                                                    <div className="grid grid-cols-2 gap-3">
                                                        <div>
                                                            <label className="text-[10px] uppercase font-black text-slate-600 block mb-1">
                                                                Original type
                                                            </label>

                                                            <div className="font-mono text-xs text-red-300 bg-red-500/10 border border-red-500/20 rounded px-3 py-2">
                                                                {
                                                                    e.original_entity_type
                                                                }
                                                            </div>
                                                        </div>

                                                        <div>
                                                            <label className="text-[10px] uppercase font-black text-slate-600 block mb-1">
                                                                Verified type
                                                            </label>

                                                            <select
                                                                value={
                                                                    e.entity_type
                                                                }
                                                                onChange={ev =>
                                                                    handleEntityTypeChange(
                                                                        e.key,
                                                                        ev.target
                                                                            .value
                                                                    )
                                                                }
                                                                className="w-full bg-slate-900 border border-slate-700 rounded px-3 py-2 text-xs text-white focus:border-brand-primary focus:outline-none"
                                                            >
                                                                {!ENTITY_TYPE_OPTIONS.includes(
                                                                    e.entity_type
                                                                ) && (
                                                                    <option
                                                                        value={
                                                                            e.entity_type
                                                                        }
                                                                    >
                                                                        {
                                                                            e.entity_type
                                                                        }
                                                                    </option>
                                                                )}

                                                                {ENTITY_TYPE_OPTIONS.map(
                                                                    type => (
                                                                        <option
                                                                            key={
                                                                                type
                                                                            }
                                                                            value={
                                                                                type
                                                                            }
                                                                        >
                                                                            {
                                                                                type
                                                                            }
                                                                        </option>
                                                                    )
                                                                )}
                                                            </select>
                                                        </div>
                                                    </div>

                                                    {isCorrected && (
                                                        <div className="flex items-center gap-2 text-xs text-yellow-400 bg-yellow-500/5 border border-yellow-500/10 rounded px-3 py-2">
                                                            <AlertTriangle
                                                                size={13}
                                                            />

                                                            <span>
                                                                Entity type
                                                                corrected from{' '}
                                                                <strong>
                                                                    {
                                                                        e.original_entity_type
                                                                    }
                                                                </strong>{' '}
                                                                to{' '}
                                                                <strong>
                                                                    {
                                                                        e.entity_type
                                                                    }
                                                                </strong>
                                                                .
                                                            </span>
                                                        </div>
                                                    )}
                                                </div>
                                            );
                                        })}
                                    </div>
                                </div>
                            )}

                            {/* =====================================================
                                ANNOTATOR
                               ===================================================== */}
                            {isAnnotator && (
                                <div className="space-y-3">
                                    <div className="flex items-center gap-2">
                                        <Tag
                                            size={14}
                                            className="text-brand-primary"
                                        />

                                        <h4 className="text-slate-300 font-bold text-xs uppercase tracking-wider">
                                            Sensitivity & Context
                                        </h4>
                                    </div>

                                    <p className="text-xs text-slate-500">
                                        Assign the sensitivity level and
                                        provide the business context for
                                        each validated entity.
                                    </p>

                                    <div className="space-y-3">
                                        {Object.values(
                                            enrichments
                                        ).map(e => (
                                            <div
                                                key={e.key}
                                                className="flex flex-col gap-2.5 p-4 bg-slate-900/60 border border-slate-800 rounded-lg"
                                            >
                                                <div className="flex items-center justify-between">
                                                    <div className="flex items-center gap-2">
                                                        <span className="font-mono text-[10px] text-white uppercase bg-slate-800 px-1.5 py-0.5 rounded">
                                                            {
                                                                e.entity_type
                                                            }
                                                        </span>

                                                        {e.entity_type !==
                                                            e.original_entity_type && (
                                                            <span className="text-[9px] text-yellow-400">
                                                                corrected
                                                            </span>
                                                        )}
                                                    </div>

                                                    <code
                                                        className="text-[10px] text-slate-500 truncate max-w-[180px]"
                                                        title={e.value}
                                                    >
                                                        {e.value}
                                                    </code>
                                                </div>

                                                <div className="flex gap-2">
                                                    {SENSITIVITY_OPTIONS.map(
                                                        opt => (
                                                            <button
                                                                key={
                                                                    opt.value
                                                                }
                                                                onClick={() =>
                                                                    handleSensitivityChange(
                                                                        e.key,
                                                                        opt.value
                                                                    )
                                                                }
                                                                className={`flex-1 text-[10px] font-bold py-1.5 rounded border transition-colors ${
                                                                    e.sensitivity_level ===
                                                                    opt.value
                                                                        ? opt.color
                                                                        : 'text-slate-500 border-slate-800 hover:border-slate-700'
                                                                }`}
                                                            >
                                                                {
                                                                    opt.label
                                                                }
                                                            </button>
                                                        )
                                                    )}
                                                </div>

                                                <textarea
                                                    value={
                                                        e.context
                                                    }
                                                    onChange={ev =>
                                                        handleContextChange(
                                                            e.key,
                                                            ev.target.value
                                                        )
                                                    }
                                                    placeholder="Business context (e.g. customer data used in an internal HR export...)"
                                                    className="bg-slate-900 border border-slate-700 rounded px-3 py-2 text-slate-200 focus:border-brand-primary focus:outline-none min-h-[70px] text-xs leading-relaxed"
                                                />
                                            </div>
                                        ))}
                                    </div>
                                </div>
                            )}

                            {/* =====================================================
                                STEWARD
                               ===================================================== */}
                            {isSteward && (
                                <div className="space-y-3">
                                    <div className="flex items-center gap-2">
                                        <ShieldCheck
                                            size={14}
                                            className="text-brand-primary"
                                        />

                                        <h4 className="text-slate-300 font-bold text-xs uppercase tracking-wider">
                                            Steward Review
                                        </h4>
                                    </div>

                                    <p className="text-xs text-slate-500">
                                        Review the entity classification,
                                        sensitivity level and context before
                                        approving the task.
                                    </p>

                                    <div className="space-y-3">
                                        {Object.values(
                                            enrichments
                                        ).map(e => {
                                            const isRevealed =
                                                !!revealedKeys[
                                                    e.key
                                                ];

                                            const displayValue =
                                                isRevealed
                                                    ? e.value
                                                    : maskValueForPreview(
                                                          e.value,
                                                          e.sensitivity_level
                                                      );

                                            const notQualified =
                                                !e.sensitivity_level;

                                            const corrected =
                                                e.entity_type !==
                                                e.original_entity_type;

                                            return (
                                                <div
                                                    key={e.key}
                                                    className="flex flex-col gap-3 p-4 bg-slate-900/60 border border-slate-800 rounded-lg"
                                                >
                                                    <div className="flex items-center justify-between">
                                                        <div className="flex items-center gap-2 flex-wrap">
                                                            <span className="font-mono text-[10px] text-white uppercase bg-slate-800 px-1.5 py-0.5 rounded">
                                                                {
                                                                    e.entity_type
                                                                }
                                                            </span>

                                                            {corrected && (
                                                                <span className="text-[9px] text-yellow-400 bg-yellow-500/10 border border-yellow-500/20 px-1.5 py-0.5 rounded">
                                                                    corrected
                                                                </span>
                                                            )}

                                                            <span
                                                                className={`text-[10px] font-bold px-1.5 py-0.5 rounded border ${getSensitivityStyle(
                                                                    e.sensitivity_level
                                                                )}`}
                                                            >
                                                                {notQualified
                                                                    ? 'Not qualified'
                                                                    : SENSITIVITY_OPTIONS.find(
                                                                          o =>
                                                                              o.value ===
                                                                              e.sensitivity_level
                                                                      )?.label}
                                                            </span>
                                                        </div>

                                                        <button
                                                            onClick={() =>
                                                                toggleReveal(
                                                                    e.key
                                                                )
                                                            }
                                                            className="flex items-center gap-1 text-[10px] text-slate-400 hover:text-slate-200 transition-colors"
                                                        >
                                                            {isRevealed ? (
                                                                <EyeOff
                                                                    size={
                                                                        12
                                                                    }
                                                                />
                                                            ) : (
                                                                <Eye
                                                                    size={
                                                                        12
                                                                    }
                                                                />
                                                            )}

                                                            {isRevealed
                                                                ? 'Hide'
                                                                : 'Reveal'}
                                                        </button>
                                                    </div>

                                                    {corrected && (
                                                        <div className="text-[10px] text-slate-500">
                                                            Automatic detection:{' '}
                                                            <span className="text-red-300 font-mono">
                                                                {
                                                                    e.original_entity_type
                                                                }
                                                            </span>{' '}
                                                            → Labeler:{' '}
                                                            <span className="text-green-300 font-mono">
                                                                {
                                                                    e.entity_type
                                                                }
                                                            </span>
                                                        </div>
                                                    )}

                                                    <code className="text-xs text-slate-300 bg-slate-950/50 px-2 py-1.5 rounded border border-slate-800 break-all">
                                                        {displayValue}
                                                    </code>

                                                    {e.context ? (
                                                        <p className="text-xs text-slate-400 leading-relaxed italic border-l-2 border-slate-700 pl-2">
                                                            {e.context}
                                                        </p>
                                                    ) : (
                                                        <p className="text-xs text-slate-600 italic">
                                                            No context provided.
                                                        </p>
                                                    )}
                                                </div>
                                            );
                                        })}
                                    </div>
                                </div>
                            )}

                            {/* FALLBACK */}
                            {!isLabeler &&
                                !isAnnotator &&
                                !isSteward && (
                                    <div className="p-4 bg-slate-900/60 border border-slate-800 rounded-lg">
                                        <p className="text-sm text-slate-400">
                                            No annotation permissions are
                                            associated with the current role.
                                        </p>
                                    </div>
                                )}
                        </div>

                        {/* STEWARD MASKING DECISION */}
                        {isSteward && (
                            <div className="mt-6 rounded-xl border border-slate-800 bg-slate-900/60 p-4">
                                <div className="flex items-center justify-between gap-4">
                                    <div>
                                        <div className="flex items-center gap-2">
                                            <ShieldCheck size={15} className="text-brand-primary" />
                                            <h4 className="text-slate-200 font-bold text-xs uppercase tracking-wider">
                                                Masking Decision
                                            </h4>
                                        </div>
                                        <p className="text-xs text-slate-500 mt-1">
                                            The Steward decides whether EthiMask should be applied.
                                        </p>
                                    </div>
                                    <button
                                        type="button"
                                        onClick={() => setApplyMasking(prev => !prev)}
                                        className={`relative inline-flex h-6 w-11 flex-shrink-0 items-center rounded-full transition-colors ${applyMasking ? 'bg-emerald-600' : 'bg-slate-700'}`}
                                        aria-label="Toggle masking"
                                    >
                                        <span className={`inline-block h-4 w-4 transform rounded-full bg-white transition-transform ${applyMasking ? 'translate-x-6' : 'translate-x-1'}`} />
                                    </button>
                                </div>
                                <div className={`mt-3 text-xs font-medium ${applyMasking ? 'text-emerald-400' : 'text-slate-500'}`}>
                                    {applyMasking ? 'Masking will be applied after approval.' : 'No masking will be applied.'}
                                </div>
                            </div>
                        )}

                        {/* ACTIONS */}
                        <div className="flex gap-4 mt-8 pt-6 border-t border-white/5">
                            <Button
                                variant="ghost"
                                className="flex-1 bg-red-500/10 text-red-500 hover:bg-red-500/20 border-red-500/20"
                                onClick={() =>
                                    onReject(task.id)
                                }
                            >
                                <X
                                    size={18}
                                    className="mr-2"
                                />

                                {isSteward
                                    ? 'Send Back'
                                    : isLabeler
                                    ? 'Reject Detection'
                                    : 'Reject (Not PII)'}
                            </Button>

                            <Button
                                variant="primary"
                                className="flex-1 bg-green-500 hover:bg-green-600 border-green-500"
                                onClick={handleSave}
                            >
                                <CheckCircle2
                                    size={18}
                                    className="mr-2"
                                />

                                {isSteward
                                    ? 'Approve'
                                    : isLabeler
                                    ? 'Confirm Classification'
                                    : 'Confirm & Submit'}
                            </Button>
                        </div>
                    </motion.div>
                </div>
            )}
        </AnimatePresence>
    );
};

export default TaskDetailsModal;