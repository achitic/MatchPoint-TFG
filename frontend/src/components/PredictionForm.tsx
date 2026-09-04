import { useEffect, useState } from 'react';
import type { FormEvent } from 'react';
import { BarChart3 } from 'lucide-react';
import type { ModelInfo, PredictResponse } from '../api/client';
import { DEFAULT_MODELS, fetchModels, fetchPlayers, fetchSurfaces, predict } from '../api/client';
import { PlayerPicker } from './PlayerPicker';

interface PredictionFormProps {
    onResult: (result: PredictResponse, wasDebug: boolean) => void;
    onError: (error: string) => void;
    onLoading: (loading: boolean) => void;
}

export function PredictionForm({ onResult, onError, onLoading }: PredictionFormProps) {
    const [players, setPlayers] = useState<string[]>([]);
    const [models, setModels] = useState<ModelInfo[]>(DEFAULT_MODELS);
    const [surfaces, setSurfaces] = useState<string[]>(['Hard', 'Clay', 'Grass']);
    const [playerA, setPlayerA] = useState('');
    const [playerB, setPlayerB] = useState('');
    const [surface, setSurface] = useState('Hard');
    const [model, setModel] = useState('calibrated_logreg');
    const [asOf, setAsOf] = useState('');
    const [useAutoDate, setUseAutoDate] = useState(true);
    const [debug, setDebug] = useState(false);
    const [dataLoaded, setDataLoaded] = useState(false);
    const [formError, setFormError] = useState('');

    useEffect(() => {
        async function loadData() {
            try {
                const [playersData, modelsData, surfacesData] = await Promise.all([
                    fetchPlayers(),
                    fetchModels(),
                    fetchSurfaces(),
                ]);
                setPlayers(playersData);
                setModels(modelsData);
                setSurfaces(surfacesData);
                setDataLoaded(true);
            } catch {
                onError('No se pudieron cargar los datos. Comprueba que la API esté disponible.');
            }
        }
        void loadData();
    }, [onError]);

    const handleSubmit = async (event: FormEvent) => {
        event.preventDefault();
        setFormError('');

        if (!playerA || !playerB) {
            const message = 'Selecciona los dos jugadores antes de continuar.';
            setFormError(message);
            onError(message);
            return;
        }
        if (playerA === playerB) {
            const message = 'Selecciona dos jugadores diferentes.';
            setFormError(message);
            onError(message);
            return;
        }

        onLoading(true);
        try {
            const result = await predict({
                player_a: playerA,
                player_b: playerB,
                surface,
                as_of: useAutoDate ? null : asOf || null,
                model,
                debug,
            });
            onResult(result, debug);
        } catch (error) {
            onError(error instanceof Error ? error.message : 'No se pudo completar la predicción. Inténtalo de nuevo.');
        } finally {
            onLoading(false);
        }
    };

    const hasPlayerError = Boolean(formError);

    return (
        <form className="prediction-form" onSubmit={handleSubmit} noValidate>
            <div className="form-row">
                <PlayerPicker
                    label="Jugador A"
                    players={players}
                    value={playerA}
                    onChange={(value) => { setPlayerA(value); setFormError(''); }}
                    disabled={!dataLoaded}
                    minSearchLength={1}
                    placeholder="Buscar jugador..."
                    name="player_a"
                    invalid={hasPlayerError}
                    describedBy={hasPlayerError ? 'prediction-form-error' : undefined}
                />

                <div className="vs-label" aria-hidden="true">vs</div>

                <PlayerPicker
                    label="Jugador B"
                    players={players}
                    value={playerB}
                    onChange={(value) => { setPlayerB(value); setFormError(''); }}
                    disabled={!dataLoaded}
                    excludePlayers={playerA ? [playerA] : []}
                    minSearchLength={1}
                    placeholder="Buscar jugador..."
                    name="player_b"
                    invalid={hasPlayerError}
                    describedBy={hasPlayerError ? 'prediction-form-error' : undefined}
                />
            </div>

            <div className="form-row">
                <div className="form-group">
                    <label htmlFor="prediction-surface">Superficie</label>
                    <select id="prediction-surface" name="surface" value={surface} onChange={(event) => setSurface(event.target.value)}>
                        {surfaces.map((item) => <option key={item} value={item}>{item}</option>)}
                    </select>
                </div>

                <div className="form-group">
                    <label htmlFor="prediction-model">Modelo</label>
                    <select id="prediction-model" name="model" value={model} onChange={(event) => setModel(event.target.value)}>
                        {models.map((item) => (
                            <option key={item.id} value={item.id} title={item.description_es}>{item.label_es}</option>
                        ))}
                    </select>
                </div>
            </div>

            <div className="form-row">
                <div className="form-group date-group">
                    <label className="check-control">
                        <input type="checkbox" checked={useAutoDate} onChange={(event) => setUseAutoDate(event.target.checked)} />
                        Usar la fecha más reciente
                    </label>
                    {!useAutoDate && (
                        <input
                            id="prediction-date"
                            name="as_of"
                            type="date"
                            value={asOf}
                            onChange={(event) => setAsOf(event.target.value)}
                            aria-label="Fecha de referencia"
                        />
                    )}
                </div>

                <div className="form-group debug-toggle">
                    <label className="check-control">
                        <input type="checkbox" checked={debug} onChange={(event) => setDebug(event.target.checked)} />
                        Mostrar explicación del modelo
                    </label>
                </div>
            </div>

            {formError && <p className="form-error" id="prediction-form-error" role="alert">{formError}</p>}

            <button type="submit" className="predict-button" disabled={!dataLoaded}>
                <BarChart3 size={18} strokeWidth={2} aria-hidden="true" />
                <span>Predecir partido</span>
            </button>
        </form>
    );
}
