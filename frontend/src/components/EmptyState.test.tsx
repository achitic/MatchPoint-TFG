import { render, screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';
import { EmptyState } from './EmptyState';

describe('EmptyState', () => {
    it('renders the simulation guidance and all four steps', () => {
        render(<EmptyState mode="simulate" />);
        expect(screen.getByRole('heading', { name: /simula un partido/i })).toBeInTheDocument();
        expect(screen.getAllByRole('listitem')).toHaveLength(4);
        expect(screen.getByText(/puntos \(detallado\)/i)).toBeInTheDocument();
    });
});
