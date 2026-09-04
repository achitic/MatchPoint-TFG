// frontend/src/components/SkeletonLoader.tsx
import { motion } from 'framer-motion';

/* ------------------------------------------------------------------ */
/*  Reusable shimmer skeleton — matches the glass-panel style          */
/* ------------------------------------------------------------------ */

interface SkeletonBlockProps {
  width?: string;
  height?: string;
  borderRadius?: string;
  style?: React.CSSProperties;
}

function SkeletonBlock({
  width = '100%',
  height = '1rem',
  borderRadius = '8px',
  style,
}: SkeletonBlockProps) {
  return (
    <div
      className="skeleton-block"
      style={{ width, height, borderRadius, ...style }}
    />
  );
}

/* ── Prediction skeleton: mimics ResultsDisplay layout ── */
export function PredictionSkeleton() {
  return (
    <motion.div
      className="skeleton-container results-container"
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      exit={{ opacity: 0 }}
      transition={{ duration: 0.3 }}
    >
      {/* Header */}
      <div className="skeleton-header">
        <SkeletonBlock width="220px" height="1.4rem" />
        <div className="skeleton-badges">
          <SkeletonBlock width="60px" height="1.4rem" borderRadius="20px" />
          <SkeletonBlock width="90px" height="1.4rem" borderRadius="20px" />
          <SkeletonBlock width="110px" height="1.4rem" borderRadius="20px" />
        </div>
      </div>

      {/* Probability cards */}
      <div className="skeleton-probability">
        <div className="skeleton-player-card skeleton-card-a">
          <SkeletonBlock width="140px" height="1rem" style={{ margin: '0 auto 0.75rem' }} />
          <SkeletonBlock width="100px" height="2.8rem" style={{ margin: '0 auto 0.75rem' }} />
          <SkeletonBlock width="100%" height="6px" borderRadius="3px" />
        </div>

        <div className="skeleton-vs">
          <SkeletonBlock width="32px" height="32px" borderRadius="50%" style={{ margin: '0 auto' }} />
        </div>

        <div className="skeleton-player-card skeleton-card-b">
          <SkeletonBlock width="140px" height="1rem" style={{ margin: '0 auto 0.75rem' }} />
          <SkeletonBlock width="100px" height="2.8rem" style={{ margin: '0 auto 0.75rem' }} />
          <SkeletonBlock width="100%" height="6px" borderRadius="3px" />
        </div>
      </div>

      {/* Winner summary */}
      <div className="skeleton-summary">
        <SkeletonBlock width="120px" height="0.8rem" style={{ margin: '0 auto 0.5rem' }} />
        <SkeletonBlock width="200px" height="1.6rem" style={{ margin: '0 auto 0.3rem' }} />
        <SkeletonBlock width="150px" height="0.8rem" style={{ margin: '0 auto' }} />
      </div>
    </motion.div>
  );
}

/* ── Simulation skeleton: mimics scoreboard layout ── */
export function SimulationSkeleton() {
  return (
    <motion.div
      className="skeleton-container results-container"
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      exit={{ opacity: 0 }}
      transition={{ duration: 0.3 }}
    >
      {/* Header */}
      <div className="skeleton-header">
        <SkeletonBlock width="200px" height="1.4rem" />
        <div className="skeleton-badges">
          <SkeletonBlock width="50px" height="1.4rem" borderRadius="20px" />
          <SkeletonBlock width="80px" height="1.4rem" borderRadius="20px" />
        </div>
      </div>

      {/* Scoreboard */}
      <div className="skeleton-scoreboard">
        <div className="skeleton-score-row">
          <SkeletonBlock width="140px" height="1.2rem" />
          <SkeletonBlock width="30px" height="1.2rem" />
          <SkeletonBlock width="30px" height="1.2rem" />
          <SkeletonBlock width="30px" height="1.2rem" />
        </div>
        <div className="skeleton-score-row">
          <SkeletonBlock width="140px" height="1.2rem" />
          <SkeletonBlock width="30px" height="1.2rem" />
          <SkeletonBlock width="30px" height="1.2rem" />
          <SkeletonBlock width="30px" height="1.2rem" />
        </div>
      </div>

      {/* Chart area */}
      <SkeletonBlock width="100%" height="180px" borderRadius="12px" style={{ marginTop: '1.5rem' }} />

      {/* Controls */}
      <div className="skeleton-controls">
        <SkeletonBlock width="36px" height="36px" borderRadius="50%" />
        <SkeletonBlock width="200px" height="8px" borderRadius="4px" />
        <SkeletonBlock width="60px" height="28px" borderRadius="6px" />
      </div>
    </motion.div>
  );
}

/* ── Tournament skeleton: mimics bracket layout ── */
export function TournamentSkeleton() {
  return (
    <motion.div
      className="skeleton-container results-container"
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      exit={{ opacity: 0 }}
      transition={{ duration: 0.3 }}
    >
      {/* Champion banner */}
      <div className="skeleton-champion">
        <SkeletonBlock width="24px" height="24px" borderRadius="50%" style={{ margin: '0 auto 0.5rem' }} />
        <SkeletonBlock width="180px" height="1.6rem" style={{ margin: '0 auto 0.3rem' }} />
        <SkeletonBlock width="100px" height="0.8rem" style={{ margin: '0 auto' }} />
      </div>

      {/* Bracket rounds */}
      <div className="skeleton-bracket">
        {[0, 1, 2, 3].map((i) => (
          <div key={i} className="skeleton-match-slot">
            <SkeletonBlock width="160px" height="28px" borderRadius="6px" />
            <SkeletonBlock width="160px" height="28px" borderRadius="6px" />
          </div>
        ))}
      </div>

      {/* Standings table */}
      <div className="skeleton-table">
        {[0, 1, 2, 3, 4].map((i) => (
          <div key={i} className="skeleton-table-row">
            <SkeletonBlock width="20px" height="1rem" />
            <SkeletonBlock width="140px" height="1rem" />
            <SkeletonBlock width="40px" height="1rem" />
            <SkeletonBlock width="40px" height="1rem" />
          </div>
        ))}
      </div>
    </motion.div>
  );
}
