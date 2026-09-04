import { useEffect, useState } from 'react';
import type { FormEvent } from 'react';
import type { ModelInfo, TournamentRequest, TournamentResponse } from '../api/client';
import { DEFAULT_MODELS, fetchModels, fetchPlayers, fetchSurfaces, simulateTournament } from '../api/client';
import { PlayerPicker } from './PlayerPicker';

interface TournamentFormProps {
    onResult: (result: TournamentResponse, request: TournamentRequest) => void;
    onError: (error: string) => void;
    onLoading: (loading: boolean) => void;
}

export function TournamentForm({ onResult, onError, onLoading }: TournamentFormProps) {
    const [players, setPlayers] = useState<string[]>([]);
    const [models, setModels] = useState<ModelInfo[]>(DEFAULT_MODELS);
    const [surfaces, setSurfaces] = useState<string[]>(['Hard', 'Clay', 'Grass']);
    const [dataLoaded, setDataLoaded] = useState(false);
    const [selectedPlayers, setSelectedPlayers] = useState<string[]>([]);
    const [playerToAdd, setPlayerToAdd] = useState('');
    const [size, setSize] = useState<8 | 16>(8);
    const [surface, setSurface] = useState('Hard');
    const [model, setModel] = useState('calibrated_logreg');
    const [bestOf, setBestOf] = useState<3 | 5>(3);
    const [seeding, setSeeding] = useState<'random' | 'elo'>('random');
    const [seed, setSeed] = useState('');
    const [timelineMode, setTimelineMode] = useState<'none' | 'games'>('none');
    const [isLoading, setIsLoading] = useState(false);
    const [formError, setFormError] = useState('');

    useEffect(() => {
        async function loadData() {
            try {
                const [playersData, modelsData, surfacesData] = await Promise.all([
                    fetchPlayers(), fetchModels(), fetchSurfaces(),
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

    const addPlayer = (player: string) => {
        if (selectedPlayers.length < size && !selectedPlayers.includes(player)) {
            setSelectedPlayers((current) => [...current, player]);
            setFormError('');
        }
        setPlayerToAdd('');
    };

    const removePlayer = (player: string) => {
        setSelectedPlayers((current) => current.filter((selected) => selected !== player));
    };

    const handleSubmit = async (event: FormEvent) => {
        event.preventDefault();
        setFormError('');
        if (selectedPlayers.length !== size) {
            const message = `Selecciona exactamente ${size} jugadores. Has seleccionado ${selectedPlayers.length}.`;
            setFormError(message);
            onError(message);
            return;
        }

        setIsLoading(true);
        onLoading(true);
        try {
            const request: TournamentRequest = {
                tournament_id: null,
                players: selectedPlayers,
                size,
                surface,
                as_of: null,
                model,
                best_of: bestOf,
                seed: seed ? parseInt(seed, 10) : null,
                timeline_mode: timelineMode,
                seeding,
            };
            const result = await simulateTournament(request);
            onResult(result, request);
        } catch (error) {
            onError(error instanceof Error ? error.message : 'No se pudo completar el torneo. Inténtalo de nuevo.');
        } finally {
            setIsLoading(false);
            onLoading(false);
        }
    };

    const canSubmit = selectedPlayers.length === size && !isLoading && dataLoaded;

    return (
        <form className="prediction-form tournament-form" onSubmit={handleSubmit} noValidate>
            <h3>Simulación de torneo</h3>

            <div className="form-row">
                <div className="form-group">
                    <label htmlFor="tournament-size">Tamaño del torneo</label>
                    <select id="tournament-size" name="size" value={size} onChange={(event) => {
                        const nextSize = parseInt(event.target.value) as 8 | 16;
                        setSize(nextSize);
                        setSelectedPlayers((current) => current.slice(0, nextSize));
                    }}>
                        <option value={8}>8 jugadores</option>
                        <option value={16}>16 jugadores</option>
                    </select>
                </div>
                <div className="form-group">
                    <label htmlFor="tournament-surface">Superficie</label>
                    <select id="tournament-surface" name="surface" value={surface} onChange={(event) => setSurface(event.target.value)}>
                        {surfaces.map((item) => <option key={item} value={item}>{item}</option>)}
                    </select>
                </div>
                <div className="form-group">
                    <label htmlFor="tournament-model">Modelo</label>
                    <select id="tournament-model" name="model" value={model} onChange={(event) => setModel(event.target.value)}>
                        {models.map((item) => <option key={item.id} value={item.id} title={item.description_es}>{item.label_es}</option>)}
                    </select>
                </div>
            </div>

            <div className="form-row">
                <PlayerPicker
                    label={`Añadir jugadores (${selectedPlayers.length}/${size})`}
                    players={players}
                    value={playerToAdd}
                    onChange={(player) => player ? addPlayer(player) : setPlayerToAdd('')}
                    disabled={!dataLoaded || selectedPlayers.length >= size}
                    excludePlayers={selectedPlayers}
                    minSearchLength={2}
                    placeholder="Buscar y añadir jugador..."
                    clearOnSelect
                    name="tournament_player"
                    invalid={Boolean(formError)}
                    describedBy={formError ? 'tournament-form-error' : undefined}
                />
            </div>

            {selectedPlayers.length > 0 && (
                <div className="selected-players" aria-label="Jugadores seleccionados">
                    <p className="selected-players-label">Jugadores seleccionados</p>
                    <div className="player-chips">
                        {selectedPlayers.map((player, index) => (
                            <span key={player} className="player-chip">
                                <span className="chip-seed">{index + 1}</span>
                                {player}
                                <button type="button" className="chip-remove" onClick={() => removePlayer(player)} aria-label={`Quitar a ${player}`}>×</button>
                            </span>
                        ))}
                    </div>
                </div>
            )}

            <div className="form-row">
                <div className="form-group">
                    <label htmlFor="tournament-best-of">Formato</label>
                    <select id="tournament-best-of" name="best_of" value={bestOf} onChange={(event) => setBestOf(parseInt(event.target.value) as 3 | 5)}>
                        <option value={3}>Al mejor de 3 sets</option>
                        <option value={5}>Al mejor de 5 sets</option>
                    </select>
                </div>
                <div className="form-group">
                    <label htmlFor="tournament-seeding">Orden inicial</label>
                    <select id="tournament-seeding" name="seeding" value={seeding} onChange={(event) => setSeeding(event.target.value as 'random' | 'elo')}>
                        <option value="random">Aleatorio por semilla</option>
                        <option value="elo">Por ELO</option>
                    </select>
                </div>
                <div className="form-group">
                    <label htmlFor="tournament-seed">Semilla opcional</label>
                    <input id="tournament-seed" name="seed" type="number" value={seed} onChange={(event) => setSeed(event.target.value)} placeholder="Aleatoria si se deja vacío" min={0} />
                </div>
                <div className="form-group">
                    <label htmlFor="tournament-detail">Detalle</label>
                    <select id="tournament-detail" name="timeline_mode" value={timelineMode} onChange={(event) => setTimelineMode(event.target.value as 'none' | 'games')}>
                        <option value="none">Solo resultados</option>
                        <option value="games">Incluir juegos</option>
                    </select>
                </div>
            </div>

            {formError && <p className="form-error" id="tournament-form-error" role="alert">{formError}</p>}

            <button type="submit" className="predict-button" disabled={!canSubmit}>
                {isLoading ? 'Simulando torneo...' : 'Simular torneo'}
            </button>

            {selectedPlayers.length !== size && selectedPlayers.length > 0 && (
                <p className="form-hint" role="status">Faltan {size - selectedPlayers.length} jugadores por seleccionar.</p>
            )}
        </form>
    );
}
