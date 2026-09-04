import { lazy, Suspense, useRef, useState } from 'react';
import { Navigate, NavLink, Route, Routes, useNavigate } from 'react-router-dom';
import { AnimatePresence, motion, useReducedMotion } from 'framer-motion';
import type { Variants } from 'framer-motion';
import { Activity, BarChart3, Home, Search, Sliders, Trophy, Waves } from 'lucide-react';
import { HeroLanding } from './components/HeroLanding';
import { SimulationHistory } from './components/SimulationHistory';
import { useSimulationHistory } from './components/useSimulationHistory';
import { ErrorBoundary } from './components/ErrorBoundary';
import { EmptyState } from './components/EmptyState';
import { useToast } from './components/toastContext';
import { PredictionSkeleton, SimulationSkeleton, TournamentSkeleton } from './components/SkeletonLoader';
import type { PredictResponse, SimulateRequest, SimulateResponse, TournamentRequest, TournamentResponse } from './api/client';
import { simulateMatch, simulateTournament } from './api/client';
import './App.css';

const PredictionForm = lazy(() => import('./components/PredictionForm').then((module) => ({ default: module.PredictionForm })));
const ResultsDisplay = lazy(() => import('./components/ResultsDisplay').then((module) => ({ default: module.ResultsDisplay })));
const SimulationForm = lazy(() => import('./components/SimulationForm').then((module) => ({ default: module.SimulationForm })));
const SimulationViewer = lazy(() => import('./components/SimulationViewer').then((module) => ({ default: module.SimulationViewer })));
const TournamentForm = lazy(() => import('./components/TournamentForm').then((module) => ({ default: module.TournamentForm })));
const TournamentViewer = lazy(() => import('./components/TournamentViewer').then((module) => ({ default: module.TournamentViewer })));
const PlayerProfile = lazy(() => import('./components/PlayerProfile').then((module) => ({ default: module.PlayerProfile })));
const HeadToHead = lazy(() => import('./components/HeadToHead').then((module) => ({ default: module.HeadToHead })));
const ModelComparison = lazy(() => import('./components/ModelComparison').then((module) => ({ default: module.ModelComparison })));
const RivalAnalysis = lazy(() => import('./components/RivalAnalysis').then((module) => ({ default: module.RivalAnalysis })));
const CoachMode = lazy(() => import('./components/CoachMode').then((module) => ({ default: module.CoachMode })));
const LiveTracker = lazy(() => import('./components/LiveTracker').then((module) => ({ default: module.LiveTracker })));

const pageVariants: Variants = {
    initial: { opacity: 0, y: 10 },
    animate: { opacity: 1, y: 0, transition: { duration: 0.22, ease: 'easeOut' as const } },
    exit: { opacity: 0, y: -6, transition: { duration: 0.12 } },
};

const reducedPageVariants: Variants = {
    initial: { opacity: 1, y: 0 },
    animate: { opacity: 1, y: 0 },
    exit: { opacity: 1, y: 0 },
};

const appNavItems = [
    { to: '/app/predict', label: 'Predicción', icon: BarChart3 },
    { to: '/app/simulate', label: 'Simulación', icon: Waves },
    { to: '/app/tournament', label: 'Torneo', icon: Trophy },
    { to: '/app/scouting', label: 'Scouting', icon: Search },
    { to: '/app/coach', label: 'Entrenador', icon: Sliders },
    { to: '/app/live', label: 'Tracker en vivo', icon: Activity },
];

function HeroPage() {
    const navigate = useNavigate();
    return <HeroLanding onEnter={() => navigate('/app/predict')} />;
}

function AppNavigation() {
    return (
        <>
            <aside className="app-sidebar" aria-label="Navegación principal">
                <div className="sidebar-brand">
                    <div className="sidebar-logo" aria-hidden="true">MP</div>
                    <div>
                        <h1>MatchPoint</h1>
                        <p>Análisis predictivo de tenis</p>
                    </div>
                </div>

                <nav className="sidebar-nav">
                    {appNavItems.map(({ to, label, icon: Icon }) => (
                        <NavLink key={to} to={to} className={({ isActive }) => `sidebar-link ${isActive ? 'active' : ''}`}>
                            <Icon size={18} strokeWidth={2} aria-hidden="true" />
                            <span>{label}</span>
                        </NavLink>
                    ))}
                </nav>

                <NavLink to="/" className="sidebar-home-link">
                    <Home size={17} strokeWidth={2} aria-hidden="true" />
                    <span>Inicio</span>
                </NavLink>

            </aside>

            <nav className="mobile-mode-tabs" aria-label="Navegación de secciones">
                {appNavItems.map(({ to, label, icon: Icon }) => (
                    <NavLink key={to} to={to} className={({ isActive }) => `mobile-mode-tab ${isActive ? 'active' : ''}`}>
                        <Icon size={17} strokeWidth={2} aria-hidden="true" />
                        <span>{label}</span>
                    </NavLink>
                ))}
            </nav>
        </>
    );
}

function RouteLoading() {
    return <div className="route-loading" role="status">Preparando la herramienta...</div>;
}

function SimulatorShell() {
    const toast = useToast();
    const prefersReducedMotion = useReducedMotion();
    const activePageVariants = prefersReducedMotion ? reducedPageVariants : pageVariants;
    const [predictResult, setPredictResult] = useState<PredictResponse | null>(null);
    const [predictLoading, setPredictLoading] = useState(false);
    const [showDebug, setShowDebug] = useState(false);
    const [simResult, setSimResult] = useState<SimulateResponse | null>(null);
    const [simLoading, setSimLoading] = useState(false);
    const [simVisualCourt, setSimVisualCourt] = useState(false);
    const lastSimRequestRef = useRef<SimulateRequest | null>(null);
    const { history, addToHistory } = useSimulationHistory();
    const [tournamentResult, setTournamentResult] = useState<TournamentResponse | null>(null);
    const [tournamentLoading, setTournamentLoading] = useState(false);
    const lastTournamentRequestRef = useRef<TournamentRequest | null>(null);

    const handleRerunSameSeed = async () => {
        if (!lastSimRequestRef.current || !simResult) return;
        setSimLoading(true);
        try {
            const request = { ...lastSimRequestRef.current, seed: simResult.seed_used };
            const result = await simulateMatch(request);
            setSimResult(result);
            setSimVisualCourt(request.timeline_mode === 'points');
            toast.success('Simulación repetida con éxito.');
        } catch (error) {
            toast.error(error instanceof Error ? error.message : 'No se pudo repetir la simulación.');
        } finally {
            setSimLoading(false);
        }
    };

    const handleRerunTournamentSameSeed = async () => {
        if (!lastTournamentRequestRef.current || !tournamentResult) return;
        setTournamentLoading(true);
        try {
            const request = { ...lastTournamentRequestRef.current, seed: tournamentResult.seed_used };
            const result = await simulateTournament(request);
            lastTournamentRequestRef.current = request;
            setTournamentResult(result);
            toast.success('Torneo repetido con éxito.');
        } catch (error) {
            toast.error(error instanceof Error ? error.message : 'No se pudo repetir el torneo.');
        } finally {
            setTournamentLoading(false);
        }
    };

    return (
        <div className="app app-shell">
            <AppNavigation />
            <div className="app-workspace">
                <header className="workspace-header">
                    <div>
                        <span className="workspace-kicker">Centro de análisis</span>
                        <h2>Predicción, simulación y torneos</h2>
                    </div>
                </header>

                <main className="app-main" id="contenido-principal">
                    <Suspense fallback={<RouteLoading />}>
                        <Routes>
                            <Route index element={<Navigate to="predict" replace />} />

                            <Route path="player/:playerName" element={<ErrorBoundary><PlayerProfile /></ErrorBoundary>} />

                            <Route path="predict" element={
                                <ErrorBoundary>
                                    <section className="form-section">
                                        <PredictionForm
                                            onResult={(result, wasDebug) => {
                                                setPredictResult(result);
                                                setShowDebug(wasDebug);
                                                toast.success(`Predicción completada: ${result.player_a} vs ${result.player_b}.`);
                                            }}
                                            onError={(message) => { if (message.trim()) toast.error(message); }}
                                            onLoading={setPredictLoading}
                                        />
                                    </section>
                                    <AnimatePresence mode="wait">
                                        {predictLoading && <PredictionSkeleton key="prediction-skeleton" />}
                                        {!predictResult && !predictLoading && (
                                            <motion.div key="prediction-empty" variants={activePageVariants} initial="initial" animate="animate" exit="exit"><EmptyState mode="predict" /></motion.div>
                                        )}
                                        {predictResult && !predictLoading && (
                                            <motion.section key="prediction-results" className="results-section" variants={activePageVariants} initial="initial" animate="animate" exit="exit">
                                                <ResultsDisplay result={predictResult} showDebug={showDebug} />
                                                <HeadToHead playerA={predictResult.player_a} playerB={predictResult.player_b} />
                                                <ModelComparison baseRequest={{ player_a: predictResult.player_a, player_b: predictResult.player_b, surface: predictResult.surface, as_of: predictResult.as_of_used, debug: false }} playerA={predictResult.player_a} playerB={predictResult.player_b} />
                                            </motion.section>
                                        )}
                                    </AnimatePresence>
                                </ErrorBoundary>
                            } />

                            <Route path="simulate" element={
                                <ErrorBoundary>
                                    {history.length > 0 && <section className="form-section"><SimulationHistory history={history} onSelect={(entry) => {
                                        setSimResult(entry);
                                        setSimVisualCourt(Boolean(entry.timeline?.some((set) => set.games?.some((game) => game.points && game.points.length > 0))));
                                    }} /></section>}
                                    <section className="form-section">
                                        <SimulationForm
                                            onResult={(result, request) => {
                                                setSimResult(result);
                                                lastSimRequestRef.current = request;
                                                setSimVisualCourt(request.timeline_mode === 'points');
                                                addToHistory(result);
                                                toast.success(`Partido simulado: ${result.player_a} vs ${result.player_b}.`);
                                            }}
                                            onError={(message) => { if (message.trim()) toast.error(message); }}
                                            onLoading={setSimLoading}
                                        />
                                    </section>
                                    <AnimatePresence mode="wait">
                                        {simLoading && <SimulationSkeleton key="simulation-skeleton" />}
                                        {!simResult && !simLoading && <motion.div key="simulation-empty" variants={activePageVariants} initial="initial" animate="animate" exit="exit"><EmptyState mode="simulate" /></motion.div>}
                                        {simResult && !simLoading && <motion.section key="simulation-results" className="results-section" variants={activePageVariants} initial="initial" animate="animate" exit="exit"><SimulationViewer result={simResult} showVisualCourt={simVisualCourt} onRerunSameSeed={handleRerunSameSeed} /></motion.section>}
                                    </AnimatePresence>
                                </ErrorBoundary>
                            } />

                            <Route path="tournament" element={
                                <ErrorBoundary>
                                    <section className="form-section">
                                        <TournamentForm
                                            onResult={(result, request) => {
                                                setTournamentResult(result);
                                                lastTournamentRequestRef.current = request;
                                                toast.success(`Torneo completado. Campeón: ${result.champion}.`);
                                            }}
                                            onError={(message) => { if (message.trim()) toast.error(message); }}
                                            onLoading={setTournamentLoading}
                                        />
                                    </section>
                                    <AnimatePresence mode="wait">
                                        {tournamentLoading && <TournamentSkeleton key="tournament-skeleton" />}
                                        {!tournamentResult && !tournamentLoading && <motion.div key="tournament-empty" variants={activePageVariants} initial="initial" animate="animate" exit="exit"><EmptyState mode="tournament" /></motion.div>}
                                        {tournamentResult && !tournamentLoading && <motion.section key="tournament-results" className="results-section" variants={activePageVariants} initial="initial" animate="animate" exit="exit"><TournamentViewer result={tournamentResult} baseRequest={lastTournamentRequestRef.current} onRerunSameSeed={handleRerunTournamentSameSeed} /></motion.section>}
                                    </AnimatePresence>
                                </ErrorBoundary>
                            } />

                            <Route path="scouting" element={<ErrorBoundary><motion.div variants={activePageVariants} initial="initial" animate="animate" exit="exit"><RivalAnalysis /></motion.div></ErrorBoundary>} />
                            <Route path="coach" element={<ErrorBoundary><motion.div variants={activePageVariants} initial="initial" animate="animate" exit="exit"><CoachMode /></motion.div></ErrorBoundary>} />
                            <Route path="live" element={<ErrorBoundary><motion.div variants={activePageVariants} initial="initial" animate="animate" exit="exit"><LiveTracker /></motion.div></ErrorBoundary>} />
                        </Routes>
                    </Suspense>
                </main>
            </div>
        </div>
    );
}

export default function App() {
    return (
        <Routes>
            <Route path="/" element={<HeroPage />} />
            <Route path="/app/*" element={<SimulatorShell />} />
            <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
    );
}
