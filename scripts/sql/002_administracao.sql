CREATE TABLE IF NOT EXISTS hazardtrack.telemetria_ciclo (
    iniciado_em timestamptz PRIMARY KEY,
    dados jsonb NOT NULL
);

CREATE TABLE IF NOT EXISTS hazardtrack.produto_monitoramento (
    id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    sistema text NOT NULL CHECK (sistema IN ('geo', 'fire')),
    referencia_em timestamptz NOT NULL,
    assinatura text NOT NULL,
    dados jsonb NOT NULL,
    UNIQUE (sistema, assinatura)
);
CREATE INDEX IF NOT EXISTS produto_referencia
    ON hazardtrack.produto_monitoramento
    (sistema, referencia_em DESC, id DESC);

CREATE TABLE IF NOT EXISTS hazardtrack.controle_monitoramento (
    singleton boolean PRIMARY KEY DEFAULT true CHECK (singleton),
    dados jsonb NOT NULL
);

CREATE TABLE IF NOT EXISTS hazardtrack.auditoria_administrativa (
    id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    ocorrido_em timestamptz NOT NULL DEFAULT now(),
    ator text NOT NULL,
    acao text NOT NULL,
    dados jsonb NOT NULL
);

INSERT INTO hazardtrack.versao_esquema (versao) VALUES (2)
ON CONFLICT DO NOTHING;
