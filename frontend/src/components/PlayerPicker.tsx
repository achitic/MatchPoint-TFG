import { useId, useMemo, useRef, useState } from 'react';
import type { KeyboardEvent } from 'react';

interface PlayerPickerProps {
    label: string;
    players: string[];
    value: string;
    onChange: (player: string) => void;
    disabled?: boolean;
    excludePlayers?: string[];
    minSearchLength?: number;
    maxResults?: number;
    placeholder?: string;
    clearOnSelect?: boolean;
    invalid?: boolean;
    describedBy?: string;
    name?: string;
}

function highlightMatch(player: string, query: string) {
    if (!query) return player;

    const matchIndex = player.toLowerCase().indexOf(query.toLowerCase());
    if (matchIndex < 0) return player;

    const before = player.slice(0, matchIndex);
    const match = player.slice(matchIndex, matchIndex + query.length);
    const after = player.slice(matchIndex + query.length);

    return (
        <>
            {before}
            <mark>{match}</mark>
            {after}
        </>
    );
}

export function PlayerPicker({
    label,
    players,
    value,
    onChange,
    disabled = false,
    excludePlayers = [],
    minSearchLength = 2,
    maxResults = 10,
    placeholder = 'Buscar jugador...',
    clearOnSelect = false,
    invalid = false,
    describedBy,
    name,
}: PlayerPickerProps) {
    const [query, setQuery] = useState(value);
    const [isOpen, setIsOpen] = useState(false);
    const [activeIndex, setActiveIndex] = useState(0);
    const inputRef = useRef<HTMLInputElement | null>(null);
    const generatedId = useId();
    const inputId = `player-${generatedId}`;
    const listboxId = `${inputId}-options`;

    const excluded = useMemo(() => new Set(excludePlayers), [excludePlayers]);
    const trimmedQuery = query.trim();
    const canSearch = trimmedQuery.length >= minSearchLength;

    const filteredPlayers = useMemo(() => {
        if (!canSearch) return [];
        const search = trimmedQuery.toLowerCase();
        return players
            .filter((player) => !excluded.has(player))
            .filter((player) => player.toLowerCase().includes(search))
            .slice(0, maxResults);
    }, [canSearch, excluded, maxResults, players, trimmedQuery]);

    const showPopup = isOpen && canSearch;

    const selectPlayer = (player: string) => {
        onChange(player);
        setQuery(clearOnSelect ? '' : player);
        setIsOpen(false);
        setActiveIndex(0);
    };

    const handleQueryChange = (nextQuery: string) => {
        setQuery(nextQuery);
        setIsOpen(true);
        setActiveIndex(0);
        if (value) {
            onChange('');
        }
    };

    const handleKeyDown = (event: KeyboardEvent<HTMLInputElement>) => {
        if (event.key === 'Escape') {
            setIsOpen(false);
            return;
        }

        if (!isOpen && (event.key === 'ArrowDown' || event.key === 'ArrowUp')) {
            setIsOpen(true);
            return;
        }

        if (event.key === 'ArrowDown') {
            event.preventDefault();
            setActiveIndex((current) =>
                filteredPlayers.length === 0 ? 0 : (current + 1) % filteredPlayers.length,
            );
            return;
        }

        if (event.key === 'ArrowUp') {
            event.preventDefault();
            setActiveIndex((current) =>
                filteredPlayers.length === 0
                    ? 0
                    : (current - 1 + filteredPlayers.length) % filteredPlayers.length,
            );
            return;
        }

        if (event.key === 'Enter' && isOpen && filteredPlayers[activeIndex]) {
            event.preventDefault();
            selectPlayer(filteredPlayers[activeIndex]);
        }
    };

    return (
        <div className="form-group player-input">
            <label htmlFor={inputId}>{label}</label>
            <div className="autocomplete-container">
                <input
                    ref={inputRef}
                    type="text"
                    id={inputId}
                    name={name}
                    value={query}
                    onChange={(event) => handleQueryChange(event.target.value)}
                    onFocus={() => setIsOpen(true)}
                    onBlur={() => setIsOpen(false)}
                    onKeyDown={handleKeyDown}
                    placeholder={placeholder}
                    disabled={disabled}
                    role="combobox"
                    aria-expanded={showPopup}
                    aria-autocomplete="list"
                    aria-controls={showPopup ? listboxId : undefined}
                    aria-activedescendant={showPopup && filteredPlayers[activeIndex] ? `${listboxId}-${activeIndex}` : undefined}
                    aria-invalid={invalid || undefined}
                    aria-describedby={describedBy}
                />
                {showPopup && (
                    <ul className="autocomplete-dropdown" role="listbox" id={listboxId}>
                        {filteredPlayers.map((player, index) => (
                            <li
                                key={player}
                                id={`${listboxId}-${index}`}
                                className={index === activeIndex ? 'active' : ''}
                                onMouseEnter={() => setActiveIndex(index)}
                                onMouseDown={(event) => {
                                    event.preventDefault();
                                    selectPlayer(player);
                                }}
                                role="option"
                                aria-selected={index === activeIndex}
                            >
                                {highlightMatch(player, trimmedQuery)}
                            </li>
                        ))}
                        {filteredPlayers.length === 0 && (
                            <li className="autocomplete-empty" role="option" aria-disabled="true">
                                Sin resultados
                            </li>
                        )}
                    </ul>
                )}
            </div>
        </div>
    );
}
