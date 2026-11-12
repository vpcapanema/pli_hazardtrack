CREATE SCHEMA IF NOT EXISTS hazardtrack;

CREATE TABLE IF NOT EXISTS hazardtrack.versao_esquema (
    versao integer PRIMARY KEY,
    aplicado_em timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS hazardtrack.ciclo (
    id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    iniciado_em timestamptz NOT NULL UNIQUE,
    dados jsonb NOT NULL
);

CREATE TABLE IF NOT EXISTS hazardtrack.alerta (
    id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    ua_id text NOT NULL,
    canal text NOT NULL CHECK (canal IN ('geo', 'hidro')),
    aberto_em timestamptz NOT NULL,
    atualizado_em timestamptz NOT NULL,
    encerrado_em timestamptz,
    rd_atual smallint NOT NULL CHECK (rd_atual BETWEEN 0 AND 4),
    rd_maximo smallint NOT NULL CHECK (rd_maximo BETWEEN 0 AND 4),
    observavel boolean NOT NULL DEFAULT true,
    evidencia jsonb NOT NULL
);
CREATE UNIQUE INDEX IF NOT EXISTS alerta_ativo_ua
    ON hazardtrack.alerta (ua_id, canal)
    WHERE encerrado_em IS NULL;
CREATE INDEX IF NOT EXISTS alerta_data
    ON hazardtrack.alerta (aberto_em DESC, id DESC);

CREATE TABLE IF NOT EXISTS hazardtrack.evento_alerta (
    id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    alerta_id bigint NOT NULL REFERENCES hazardtrack.alerta(id),
    ciclo_id bigint NOT NULL REFERENCES hazardtrack.ciclo(id),
    ocorrido_em timestamptz NOT NULL,
    tipo text NOT NULL CHECK (tipo IN (
        'abertura', 'escalada', 'reducao', 'encerramento',
        'sem_dados', 'retomada'
    )),
    rd_anterior smallint,
    rd smallint,
    evidencia jsonb NOT NULL
);
CREATE INDEX IF NOT EXISTS evento_por_alerta
    ON hazardtrack.evento_alerta (alerta_id, id);

CREATE TABLE IF NOT EXISTS hazardtrack.notificacao (
    id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    alerta_id bigint NOT NULL REFERENCES hazardtrack.alerta(id),
    transporte text NOT NULL CHECK (transporte IN ('email', 'webhook')),
    rd smallint NOT NULL CHECK (rd BETWEEN 0 AND 4),
    criada_em timestamptz NOT NULL,
    proxima_tentativa timestamptz NOT NULL,
    enviada_em timestamptz,
    estado text NOT NULL DEFAULT 'pendente' CHECK (
        estado IN ('pendente', 'processando', 'enviada', 'cancelada')
    ),
    lease_token uuid,
    lease_ate timestamptz,
    conteudo jsonb NOT NULL
);
CREATE UNIQUE INDEX IF NOT EXISTS notificacao_pendente
    ON hazardtrack.notificacao (alerta_id, transporte)
    WHERE estado IN ('pendente', 'processando');
CREATE INDEX IF NOT EXISTS notificacao_envio
    ON hazardtrack.notificacao (alerta_id, transporte, enviada_em DESC)
    WHERE estado = 'enviada';

CREATE TABLE IF NOT EXISTS hazardtrack.tentativa_entrega (
    id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    notificacao_id bigint NOT NULL REFERENCES hazardtrack.notificacao(id),
    ocorrido_em timestamptz NOT NULL,
    sucesso boolean NOT NULL,
    erro text
);
CREATE INDEX IF NOT EXISTS tentativa_por_notificacao
    ON hazardtrack.tentativa_entrega (notificacao_id, id);

INSERT INTO hazardtrack.versao_esquema (versao) VALUES (1)
ON CONFLICT DO NOTHING;
