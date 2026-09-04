import { useAnimatedValue } from './useAnimatedValue';

interface AnimatedCounterProps {
    value: number;
    duration?: number;
    decimals?: number;
    suffix?: string;
    className?: string;
}

export function AnimatedCounter({ value, duration = 800, decimals = 1, suffix = '%', className }: AnimatedCounterProps) {
    const display = useAnimatedValue(value, duration, decimals);
    return <span className={className}>{display}{suffix}</span>;
}
