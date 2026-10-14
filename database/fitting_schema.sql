-- Measured fitting data is separate from reviews and retained only with consent.
CREATE TABLE IF NOT EXISTS fitting_outcomes (
    id BIGSERIAL PRIMARY KEY,
    golfer_id UUID NOT NULL,
    golf_club_id INTEGER NOT NULL REFERENCES golf_clubs(id),
    profile JSONB NOT NULL CHECK (jsonb_typeof(profile) = 'object'),
    club_snapshot JSONB NOT NULL CHECK (jsonb_typeof(club_snapshot) = 'object'),
    carry_yards DOUBLE PRECISION NOT NULL CHECK (carry_yards BETWEEN 0 AND 400),
    dispersion_yards DOUBLE PRECISION NOT NULL CHECK (dispersion_yards BETWEEN 0 AND 150),
    shot_count INTEGER NOT NULL CHECK (shot_count BETWEEN 5 AND 500),
    measured_at TIMESTAMPTZ NOT NULL CHECK (measured_at <= CURRENT_TIMESTAMP),
    consent BOOLEAN NOT NULL CHECK (consent IS TRUE),
    consented_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    consent_version VARCHAR(50) NOT NULL,
    collected_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_fitting_outcomes_golfer
    ON fitting_outcomes(golfer_id);
CREATE INDEX IF NOT EXISTS idx_fitting_outcomes_measured
    ON fitting_outcomes(measured_at);
