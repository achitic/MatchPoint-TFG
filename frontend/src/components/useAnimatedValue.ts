import { useEffect, useRef, useState } from 'react';

function easeOutExpo(t: number): number {
    return t === 1 ? 1 : 1 - Math.pow(2, -10 * t);
}

export function useAnimatedValue(target: number, duration = 800, decimals = 1): string {
    const [display, setDisplay] = useState('0');
    const rafRef = useRef<number>(0);
    const startRef = useRef<number>(0);
    const previousTargetRef = useRef<number>(0);

    useEffect(() => {
        const from = previousTargetRef.current;
        previousTargetRef.current = target;
        startRef.current = 0;

        const animate = (timestamp: number) => {
            if (!startRef.current) startRef.current = timestamp;
            const progress = Math.min((timestamp - startRef.current) / duration, 1);
            const current = from + (target - from) * easeOutExpo(progress);
            setDisplay(current.toFixed(decimals));
            if (progress < 1) rafRef.current = requestAnimationFrame(animate);
        };

        rafRef.current = requestAnimationFrame(animate);
        return () => cancelAnimationFrame(rafRef.current);
    }, [target, duration, decimals]);

    return display;
}
