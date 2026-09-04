interface PlaybackControlsProps {
    isPlaying: boolean;
    isFinished: boolean;
    speed: number;
    onPlay: () => void;
    onPause: () => void;
    onReset: () => void;
    onSpeedChange: (speed: number) => void;
}

export function PlaybackControls({
    isPlaying,
    isFinished,
    speed,
    onPlay,
    onPause,
    onReset,
    onSpeedChange,
}: PlaybackControlsProps) {
    return (
        <div className="playback-controls">
            <button type="button" onClick={onReset} className="control-btn">
                <RotateCcw size={16} aria-hidden="true" /> Reiniciar
            </button>
            {isPlaying ? (
                <button type="button" onClick={onPause} className="control-btn control-primary">
                    <Pause size={16} aria-hidden="true" /> Pausar
                </button>
            ) : (
                <button type="button" onClick={onPlay} className="control-btn control-primary">
                    {isFinished ? <Repeat2 size={16} aria-hidden="true" /> : <Play size={16} aria-hidden="true" />}
                    {isFinished ? 'Repetir' : 'Reproducir'}
                </button>
            )}
            <div className="speed-control">
                <label htmlFor="playback-speed">Velocidad:</label>
                <select id="playback-speed" name="playback_speed" value={speed} onChange={(e) => onSpeedChange(Number(e.target.value))}>
                    <option value={1}>1x</option>
                    <option value={2}>2x</option>
                    <option value={5}>5x</option>
                    <option value={10}>10x</option>
                    <option value={20}>20x</option>
                </select>
            </div>
        </div>
    );
}
import { Pause, Play, Repeat2, RotateCcw } from 'lucide-react';
