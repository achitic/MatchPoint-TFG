import { useCallback, useState } from 'react';
import type { SimulateResponse } from '../api/client';

const STORAGE_KEY = 'matchpoint_sim_history';
const MAX_ENTRIES = 10;

export interface HistoryEntry {
    id: string;
    timestamp: string;
    playerA: string;
    playerB: string;
    surface: string;
    model: string;
    winner: string;
    sets: string[];
    seed: number;
    result: SimulateResponse;
}

function loadHistory(): HistoryEntry[] {
    try {
        const raw = localStorage.getItem(STORAGE_KEY);
        return raw ? JSON.parse(raw) : [];
    } catch {
        return [];
    }
}

export function useSimulationHistory() {
    const [history, setHistory] = useState<HistoryEntry[]>(loadHistory);

    const addToHistory = useCallback((result: SimulateResponse) => {
        const entry: HistoryEntry = {
            id: `${Date.now()}-${result.seed_used}`,
            timestamp: new Date().toLocaleString('es-ES'),
            playerA: result.player_a,
            playerB: result.player_b,
            surface: result.surface,
            model: result.model,
            winner: result.result.winner === 'A' ? result.player_a : result.player_b,
            sets: result.result.sets,
            seed: result.seed_used,
            result,
        };

        setHistory((current) => {
            const updated = [entry, ...current].slice(0, MAX_ENTRIES);
            try { localStorage.setItem(STORAGE_KEY, JSON.stringify(updated)); } catch { /* Storage may be unavailable. */ }
            return updated;
        });
    }, []);

    const clearHistory = useCallback(() => {
        localStorage.removeItem(STORAGE_KEY);
        setHistory([]);
    }, []);

    return { history, addToHistory, clearHistory };
}
