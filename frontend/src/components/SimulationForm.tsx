import { useEffect, useState } from 'react';
import type { FormEvent } from 'react';
import { Activity } from 'lucide-react';
import type { ModelInfo, SimulateRequest, SimulateResponse } from '../api/client';
import { DEFAULT_MODELS, fetchModels, fetchPlayers, fetchSurfaces, simulateMatch } from '../api/client';
import { PlayerPicker } from './PlayerPicker';

interface SimulationFormProps {
    onResult: (result: SimulateResponse, request: SimulateRequest) => void;
    onError: (error: string) => void;
    onLoading: (loading: boolean) => void;
}

export function SimulationForm({ onResult, onError, onLoading }: SimulationFormProps) {
    const [players, setPlayers] = useState<string[]>([]);
    const [surfaces, setSurfaces] = useState<string[]>(['Hard', 'Clay', 'Grass']);
    const [models, setModels] = useState<ModelInfo[]>(DEFAULT_MODELS);
    const [playerA, setPlayerA] = useState('');
    const [playerB, setPlayerB] = useState('');
    const [surface, setSurface] = useState('Hard');
    const [model, setModel] = useState('calibrated_logreg');
    const [asOf, setAsOf] = useState('');
    const [useAutoDate, setUseAutoDate] = useState(true);
    const [bestOf, setBestOf] = useState<3 | 5>(3);
    const [seed, setSeed] = useState('');
    const [timelineMode, setTimelineMode] = useState<'none' | 'games' | 'points'>('games');
    const [engineMode, setEngineMode] = useState<'proxy_v0' | 'bayes_live_v1'>('bayes_live_v1');
    const [showVisualCourt, setShowVisualCourt] = useState(false);
    const [isLoading, setIsLoading] = useState(false);
    const [formError, setFormError] = useState('');

    useEffect(() => {
        void Promise.all([fetchPlayers(), fetchSurfaces(), fetchModels()])
            .then(([playersData, surfacesData, modelsData]) => {
                setPlayers(playersData);
                setSurfaces(surfacesData);
                setModels(modelsData);
            })
            .catch(() => onError('No se pudieron cargar los datos. Comprueba que la API esté disponible.'));
    }, [onError]);

    const handleSubmit = async (event: FormEvent) => {
        event.preventDefault();
        setFormError('');
        if (!playerA || !playerB) {
            const message = 'Selecciona los dos jugadores antes de simular el partido.';
            setFormError(message);
            onError(message);
            return;
        }

        setIsLoading(true);
        onLoading(true);
        try {
            const request: SimulateRequest = {
                player_a: playerA,
                player_b: playerB,
                surface,
                as_of: useAutoDate ? null : asOf || null,
                model,
                best_of: bestOf,
                seed: seed ? parseInt(seed, 10) : null,
                first_server: 'random',
                timeline_mode: showVisualCourt ? 'points' : timelineMode,
                engine_mode: engineMode,
            };
            const result = await simulateMatch(request);
            onResult(result, request);
        } catch (error) {
            onError(error instanceof Error ? error.message : 'No se pudo completar la simulación. Inténtalo de nuevo.');
        } finally {
            setIsLoading(false);
            onLoading(false);
        }
    };

    const canSubmit = Boolean(playerA && playerB && !isLoading);

    return (
        <form className="prediction-form" onSubmit={handleSubmit} noValidate>
            <h3>Simulación de partido</h3>

            <div className="form-row">
                <PlayerPicker
                    label="Jugador A"
                    players={players}
                    value={playerA}
                    onChange={(value) => { setPlayerA(value); setFormError(''); }}
                    minSearchLength={2}
                    placeholder="Buscar jugador..."
                    name="simulation_player_a"
                    invalid={Boolean(formError)}
                    describedBy={formError ? 'simulation-form-error' : undefined}
                />
                <span className="vs-label" aria-hidden="true">VS</span>
                <PlayerPicker
                    label="Jugador B"
                    players={players}
                    value={playerB}
                    onChange={(value) => { setPlayerB(value); setFormError(''); }}
                    excludePlayers={playerA ? [playerA] : []}
                    minSearchLength={2}
                    placeholder="Buscar jugador..."
                    name="simulation_player_b"
                    invalid={Boolean(formError)}
                    describedBy={formError ? 'simulation-form-error' : undefined}
                />
            </div>

            <div className="form-row">
                <div className="form-group">
                    <label htmlFor="simulation-surface">Superficie</label>
                    <select id="simulation-surface" name="surface" value={surface} onChange={(event) => setSurface(event.target.value)}>
                        {surfaces.map((item) => <option key={item} value={item}>{item}</option>)}
                    </select>
                </div>
                <div className="form-group">
                    <label htmlFor="simulation-model">Modelo</label>
                    <select id="simulation-model" name="model" value={model} onChange={(event) => setModel(event.target.value)}>
                        {models.map((item) => <option key={item.id} value={item.id} title={item.description_es}>{item.label_es}</option>)}
                    </select>
                </div>
                <div className="form-group">
                    <label htmlFor="simulation-best-of">Formato</label>
                    <select id="simulation-best-of" name="best_of" value={bestOf} onChange={(event) => setBestOf(parseInt(event.target.value) as 3 | 5)}>
                        <option value={3}>Al mejor de 3 sets</option>
                        <option value={5}>Al mejor de 5 sets</option>
                    </select>
                </div>
            </div>

            <div className="form-row">
                <div className="form-group date-group">
                    <label className="check-control">
                        <input type="checkbox" checked={useAutoDate} onChange={(event) => setUseAutoDate(event.target.checked)} />
                        Usar los datos más recientes
                    </label>
                    {!useAutoDate && <input id="simulation-date" name="as_of" type="date" value={asOf} onChange={(event) => setAsOf(event.target.value)} aria-label="Fecha de referencia" />}
                </div>
                <div className="form-group">
                    <label htmlFor="simulation-seed">Semilla opcional</label>
                    <input id="simulation-seed" name="seed" type="number" value={seed} onChange={(event) => setSeed(event.target.value)} placeholder="Aleatoria si se deja vacío" min={0} />
                </div>
                <div className="form-group">
                    <label htmlFor="simulation-timeline">Detalle de la simulación</label>
                    <select id="simulation-timeline" name="timeline_mode" value={showVisualCourt ? 'points' : timelineMode} onChange={(event) => setTimelineMode(event.target.value as 'none' | 'games' | 'points')} disabled={showVisualCourt}>
                        <option value="games">Juegos</option>
                        <option value="points">Puntos detallados</option>
                        <option value="none">Solo resultado</option>
                    </select>
                    {showVisualCourt && <span className="form-hint">La pista 2D necesita el detalle por puntos.</span>}
                </div>
            </div>

            <div className="form-row">
                <div className="form-group engine-group">
                    <label htmlFor="simulation-engine">Motor</label>
                    <select id="simulation-engine" name="engine_mode" value={engineMode} onChange={(event) => setEngineMode(event.target.value as 'proxy_v0' | 'bayes_live_v1')}>
                        <option value="bayes_live_v1">Bayes live v1 (recomendado)</option>
                        <option value="proxy_v0">Proxy v0 (anterior)</option>
                    </select>
                    <span className="form-hint">Bayes live genera momentum y una repetición explicable.</span>
                </div>
                <div className="form-group visual-replay-toggle">
                    <label className="check-control">
                        <input type="checkbox" checked={showVisualCourt} onChange={(event) => setShowVisualCourt(event.target.checked)} />
                        Mostrar pista 2D y narrativa del punto
                    </label>
                    <span className="form-hint">Añade una reconstrucción visual sintética al resumen.</span>
                </div>
            </div>

            {formError && <p className="form-error" id="simulation-form-error" role="alert">{formError}</p>}

            <button type="submit" className="predict-button" disabled={!canSubmit}>
                <Activity size={18} strokeWidth={2} aria-hidden="true" />
                <span>{isLoading ? 'Simulando partido...' : 'Simular partido'}</span>
            </button>
        </form>
    );
}
