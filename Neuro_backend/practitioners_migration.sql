-- ── Table praticiens (prescripteurs) ────────────────────────────────────────
-- Lookup RPPS by P.Code (initiales) comme "VS", "BAZ", "STA"

CREATE TABLE IF NOT EXISTS practitioners (
    id          SERIAL PRIMARY KEY,
    pcode       VARCHAR(10)  NOT NULL UNIQUE,  -- Initiales ex: "VS", "BAZ"
    full_name   VARCHAR(200) NOT NULL,          -- Nom complet ex: "STAN ANAMARIA-VERON"
    rpps        VARCHAR(20),                    -- N° RPPS 11 chiffres
    specialty   VARCHAR(100) DEFAULT 'Ophtalmologue',
    active      BOOLEAN DEFAULT TRUE,
    created_at  TIMESTAMP DEFAULT NOW()
);

-- Index sur pcode pour lookup rapide
CREATE INDEX IF NOT EXISTS idx_practitioners_pcode ON practitioners(pcode);

-- ── Données initiales (à adapter selon votre centre) ─────────────────────────
INSERT INTO practitioners (pcode, full_name, rpps, specialty) VALUES
    ('VS',  'STAN ANAMARIA-VERON',  NULL, 'Ophtalmologue'),
    ('BAZ', 'BAZ PATRICK',          NULL, 'Ophtalmologue'),
    ('CH',  'CHAVANNES SYLVIE',     NULL, 'Ophtalmologue')
ON CONFLICT (pcode) DO NOTHING;
