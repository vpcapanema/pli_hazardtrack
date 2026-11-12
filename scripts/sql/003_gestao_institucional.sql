-- 003: cadastro institucional. Nao ativa nem modifica o dispatcher legado.
-- Executar em transacao; referencias SIGMA sao externas, nunca FKs locais.
CREATE SCHEMA IF NOT EXISTS dominios;

CREATE TABLE IF NOT EXISTS dominios.natureza_risco (
    id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    codigo text NOT NULL UNIQUE CHECK (btrim(codigo) <> ''),
    nome text NOT NULL CHECK (btrim(nome) <> ''),
    descricao text,
    ativo boolean NOT NULL DEFAULT true,
    criado_em timestamptz NOT NULL DEFAULT now(),
    atualizado_em timestamptz NOT NULL DEFAULT now()
);
INSERT INTO dominios.natureza_risco (codigo, nome) VALUES
    ('geo', 'Geológico'),
    ('hidro', 'Hidrológico'),
    ('fire', 'Fogo')
ON CONFLICT (codigo) DO NOTHING;

CREATE TABLE IF NOT EXISTS dominios.responsabilidade_operacional (
    id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    codigo text NOT NULL UNIQUE CHECK (btrim(codigo) <> ''),
    nome text NOT NULL CHECK (btrim(nome) <> ''),
    descricao text,
    ativo boolean NOT NULL DEFAULT true,
    criado_em timestamptz NOT NULL DEFAULT now(),
    atualizado_em timestamptz NOT NULL DEFAULT now()
);
INSERT INTO dominios.responsabilidade_operacional (codigo, nome) VALUES
    ('coordenacao_estadual', 'Coordenação estadual'),
    ('coordenacao_regional', 'Coordenação regional'),
    ('monitoramento', 'Monitoramento'),
    ('operacao_rodoviaria', 'Operação rodoviária'),
    ('inspecao', 'Inspeção de campo'),
    ('resgate', 'Resgate'),
    ('combate_incendio', 'Combate a incêndio'),
    ('apoio_tecnico', 'Apoio técnico')
ON CONFLICT (codigo) DO NOTHING;

CREATE TABLE IF NOT EXISTS dominios.tipo_unidade_operacional (
    id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    codigo text NOT NULL UNIQUE CHECK (btrim(codigo) <> ''),
    nome text NOT NULL CHECK (btrim(nome) <> ''),
    descricao text,
    ativo boolean NOT NULL DEFAULT true,
    criado_em timestamptz NOT NULL DEFAULT now(),
    atualizado_em timestamptz NOT NULL DEFAULT now()
);
INSERT INTO dominios.tipo_unidade_operacional (codigo, nome) VALUES
    ('regional', 'Regional'),
    ('residencia', 'Residência de conservação'),
    ('uba', 'Unidade Básica de Atendimento'),
    ('cco', 'Centro de Controle Operacional'),
    ('grupamento', 'Grupamento'),
    ('subgrupamento', 'Subgrupamento'),
    ('posto', 'Posto'),
    ('nucleo', 'Núcleo'),
    ('base', 'Base operacional')
ON CONFLICT (codigo) DO NOTHING;

CREATE TABLE IF NOT EXISTS dominios.tipo_abrangencia (
    id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    codigo text NOT NULL UNIQUE CHECK (btrim(codigo) <> ''),
    nome text NOT NULL CHECK (btrim(nome) <> ''),
    descricao text,
    ativo boolean NOT NULL DEFAULT true,
    criado_em timestamptz NOT NULL DEFAULT now(),
    atualizado_em timestamptz NOT NULL DEFAULT now()
);
INSERT INTO dominios.tipo_abrangencia (codigo, nome) VALUES
    ('estado', 'Estado'),
    ('regiao', 'Região institucional'),
    ('municipio', 'Município'),
    ('trecho', 'Trecho rodoviário'),
    ('uc', 'Unidade de conservação'),
    ('area', 'Área delimitada')
ON CONFLICT (codigo) DO NOTHING;

CREATE TABLE IF NOT EXISTS dominios.papel_institucional (
    id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    codigo text NOT NULL UNIQUE CHECK (btrim(codigo) <> ''),
    nome text NOT NULL CHECK (btrim(nome) <> ''),
    descricao text,
    ativo boolean NOT NULL DEFAULT true,
    criado_em timestamptz NOT NULL DEFAULT now(),
    atualizado_em timestamptz NOT NULL DEFAULT now()
);
INSERT INTO dominios.papel_institucional (codigo, nome) VALUES
    ('coordenacao', 'Coordenação'),
    ('execucao', 'Execução'),
    ('regulacao', 'Regulação'),
    ('apoio_tecnico', 'Apoio técnico'),
    ('apoio_operacional', 'Apoio operacional')
ON CONFLICT (codigo) DO NOTHING;

CREATE TABLE IF NOT EXISTS dominios.fase_operacional (
    id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    codigo text NOT NULL UNIQUE CHECK (btrim(codigo) <> ''),
    nome text NOT NULL CHECK (btrim(nome) <> ''),
    descricao text,
    ativo boolean NOT NULL DEFAULT true,
    criado_em timestamptz NOT NULL DEFAULT now(),
    atualizado_em timestamptz NOT NULL DEFAULT now()
);
INSERT INTO dominios.fase_operacional (codigo, nome) VALUES
    ('verde', 'Verde'),
    ('amarela', 'Amarela'),
    ('vermelha', 'Vermelha')
ON CONFLICT (codigo) DO NOTHING;

CREATE TABLE IF NOT EXISTS dominios.canal_envio (
    id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    codigo text NOT NULL UNIQUE CHECK (btrim(codigo) <> ''),
    nome text NOT NULL CHECK (btrim(nome) <> ''),
    descricao text,
    ativo boolean NOT NULL DEFAULT true,
    criado_em timestamptz NOT NULL DEFAULT now(),
    atualizado_em timestamptz NOT NULL DEFAULT now()
);
INSERT INTO dominios.canal_envio (codigo, nome) VALUES
    ('email', 'E-mail'),
    ('sms', 'SMS'),
    ('whatsapp', 'WhatsApp'),
    ('webhook', 'Webhook')
ON CONFLICT (codigo) DO NOTHING;

CREATE TABLE IF NOT EXISTS hazardtrack.instituicao_operadora (
    id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    sigma_instituicao_id uuid NOT NULL UNIQUE,
    sigma_validado_em timestamptz,
    ativa boolean NOT NULL DEFAULT true
);
CREATE TABLE IF NOT EXISTS hazardtrack.unidade_operacional (
    id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    instituicao_id bigint NOT NULL
        REFERENCES hazardtrack.instituicao_operadora(id),
    unidade_superior_id bigint,
    tipo_unidade_id bigint NOT NULL
        REFERENCES dominios.tipo_unidade_operacional(id),
    codigo text NOT NULL CHECK (btrim(codigo) <> ''),
    nome text NOT NULL CHECK (btrim(nome) <> ''),
    ativa boolean NOT NULL DEFAULT true,
    UNIQUE (instituicao_id, codigo),
    UNIQUE (id, instituicao_id),
    FOREIGN KEY (unidade_superior_id, instituicao_id)
        REFERENCES hazardtrack.unidade_operacional(id, instituicao_id),
    CHECK (unidade_superior_id IS DISTINCT FROM id)
);
CREATE TABLE IF NOT EXISTS hazardtrack.programa_operacional (
    id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    codigo text NOT NULL UNIQUE CHECK (btrim(codigo) <> ''),
    nome text NOT NULL CHECK (btrim(nome) <> ''),
    coordenacao_estadual_id bigint NOT NULL
        REFERENCES hazardtrack.instituicao_operadora(id),
    vigente_desde date NOT NULL,
    vigente_ate date,
    ativo boolean NOT NULL DEFAULT true,
    CHECK (vigente_ate IS NULL OR vigente_ate >= vigente_desde)
);
CREATE TABLE IF NOT EXISTS hazardtrack.programa_fase (
    programa_id bigint NOT NULL
        REFERENCES hazardtrack.programa_operacional(id),
    fase_id bigint NOT NULL REFERENCES dominios.fase_operacional(id),
    ativa boolean NOT NULL DEFAULT true,
    PRIMARY KEY (programa_id, fase_id)
);
CREATE TABLE IF NOT EXISTS hazardtrack.abrangencia_operacional (
    id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    codigo text NOT NULL CHECK (btrim(codigo) <> ''),
    versao integer NOT NULL DEFAULT 1 CHECK (versao > 0),
    nome text NOT NULL CHECK (btrim(nome) <> ''),
    tipo_abrangencia_id bigint NOT NULL
        REFERENCES dominios.tipo_abrangencia(id),
    vigente_desde date NOT NULL,
    vigente_ate date,
    ativa boolean NOT NULL DEFAULT true,
    UNIQUE (codigo, versao),
    CHECK (vigente_ate IS NULL OR vigente_ate >= vigente_desde)
);
CREATE TABLE IF NOT EXISTS hazardtrack.abrangencia_componente (
    id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    abrangencia_id bigint NOT NULL
        REFERENCES hazardtrack.abrangencia_operacional(id),
    codigo_ibge text CHECK (codigo_ibge ~ '^[0-9]{7}$'),
    sigla_rodovia text,
    km_inicial numeric(12,3),
    km_final numeric(12,3),
    referencia_territorial text,
    geometria_geojson jsonb,
    CHECK (num_nonnulls(codigo_ibge, sigla_rodovia,
                       referencia_territorial, geometria_geojson) = 1),
    CHECK (
        (sigla_rodovia IS NULL AND km_inicial IS NULL
         AND km_final IS NULL)
        OR (sigla_rodovia IS NOT NULL AND btrim(sigla_rodovia) <> ''
            AND km_inicial IS NOT NULL AND km_final IS NOT NULL
            AND km_inicial >= 0 AND km_final > km_inicial)
    ),
    CHECK (referencia_territorial IS NULL
           OR btrim(referencia_territorial) <> ''),
    CHECK (geometria_geojson IS NULL
           OR jsonb_typeof(geometria_geojson) = 'object')
);
CREATE INDEX IF NOT EXISTS abrangencia_componentes
    ON hazardtrack.abrangencia_componente (abrangencia_id);
CREATE TABLE IF NOT EXISTS hazardtrack.documento_referencia (
    id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    titulo text NOT NULL CHECK (btrim(titulo) <> ''),
    orgao_emissor text NOT NULL,
    numero text,
    publicado_em date,
    url text NOT NULL,
    arquivo_repositorio text,
    sha256 text CHECK (sha256 ~ '^[0-9a-f]{64}$'),
    consultado_em timestamptz NOT NULL,
    vigente_desde date,
    vigente_ate date,
    revisado_em timestamptz,
    revisado_por_sigma_usuario_id uuid,
    observacoes text,
    CHECK (vigente_ate IS NULL OR vigente_desde IS NULL
           OR vigente_ate >= vigente_desde)
);
CREATE TABLE IF NOT EXISTS hazardtrack.competencia_operacional (
    id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    programa_id bigint NOT NULL
        REFERENCES hazardtrack.programa_operacional(id),
    fase_id bigint,
    unidade_id bigint NOT NULL,
    instituicao_id bigint NOT NULL,
    natureza_risco_id bigint NOT NULL
        REFERENCES dominios.natureza_risco(id),
    responsabilidade_id bigint NOT NULL
        REFERENCES dominios.responsabilidade_operacional(id),
    papel_id bigint NOT NULL REFERENCES dominios.papel_institucional(id),
    abrangencia_id bigint NOT NULL
        REFERENCES hazardtrack.abrangencia_operacional(id),
    vigente_desde date NOT NULL,
    vigente_ate date,
    ativa boolean NOT NULL DEFAULT true,
    UNIQUE (id, instituicao_id),
    FOREIGN KEY (unidade_id, instituicao_id)
        REFERENCES hazardtrack.unidade_operacional(id, instituicao_id),
    FOREIGN KEY (programa_id, fase_id)
        REFERENCES hazardtrack.programa_fase(programa_id, fase_id),
    CHECK (vigente_ate IS NULL OR vigente_ate >= vigente_desde)
);
CREATE INDEX IF NOT EXISTS competencia_roteamento
    ON hazardtrack.competencia_operacional
    (natureza_risco_id, abrangencia_id) WHERE ativa;
CREATE TABLE IF NOT EXISTS hazardtrack.competencia_referencia (
    competencia_id bigint NOT NULL
        REFERENCES hazardtrack.competencia_operacional(id),
    documento_id bigint NOT NULL
        REFERENCES hazardtrack.documento_referencia(id),
    localizador text NOT NULL DEFAULT '',
    PRIMARY KEY (competencia_id, documento_id, localizador)
);
CREATE TABLE IF NOT EXISTS hazardtrack.abrangencia_referencia (
    abrangencia_id bigint NOT NULL
        REFERENCES hazardtrack.abrangencia_operacional(id),
    documento_id bigint NOT NULL
        REFERENCES hazardtrack.documento_referencia(id),
    localizador text NOT NULL DEFAULT '',
    PRIMARY KEY (abrangencia_id, documento_id, localizador)
);
-- Interlocutor institucional opcional; nao cadastra agentes/plantao internos.
CREATE TABLE IF NOT EXISTS hazardtrack.interlocutor_institucional (
    id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    unidade_id bigint NOT NULL
        REFERENCES hazardtrack.unidade_operacional(id),
    sigma_pessoa_id uuid NOT NULL,
    sigma_validado_em timestamptz,
    ativo boolean NOT NULL DEFAULT true,
    UNIQUE (unidade_id, sigma_pessoa_id)
);
CREATE TABLE IF NOT EXISTS hazardtrack.contato_operacional (
    id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    unidade_id bigint NOT NULL,
    instituicao_id bigint NOT NULL,
    canal_id bigint NOT NULL REFERENCES dominios.canal_envio(id),
    rotulo text NOT NULL CHECK (btrim(rotulo) <> ''),
    destino text NOT NULL CHECK (btrim(destino) <> ''),
    verificado_em timestamptz,
    ativo boolean NOT NULL DEFAULT false,
    UNIQUE (id, instituicao_id),
    UNIQUE (unidade_id, canal_id, destino),
    FOREIGN KEY (unidade_id, instituicao_id)
        REFERENCES hazardtrack.unidade_operacional(id, instituicao_id)
);
CREATE TABLE IF NOT EXISTS hazardtrack.regra_envio_alerta (
    id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    competencia_id bigint NOT NULL,
    instituicao_id bigint NOT NULL,
    nome text NOT NULL CHECK (btrim(nome) <> ''),
    criterios jsonb NOT NULL DEFAULT '{}'
        CHECK (jsonb_typeof(criterios) = 'object'),
    intervalo_reenvio_min integer NOT NULL DEFAULT 360
        CHECK (intervalo_reenvio_min >= 0),
    incluir_json boolean NOT NULL DEFAULT true,
    incluir_instrucoes_api boolean NOT NULL DEFAULT true,
    ativa boolean NOT NULL DEFAULT false,
    UNIQUE (id, instituicao_id),
    FOREIGN KEY (competencia_id, instituicao_id)
        REFERENCES hazardtrack.competencia_operacional(id, instituicao_id)
);
CREATE TABLE IF NOT EXISTS hazardtrack.regra_envio_destino (
    regra_id bigint NOT NULL,
    contato_id bigint NOT NULL,
    instituicao_id bigint NOT NULL,
    ativo boolean NOT NULL DEFAULT true,
    PRIMARY KEY (regra_id, contato_id),
    FOREIGN KEY (regra_id, instituicao_id)
        REFERENCES hazardtrack.regra_envio_alerta(id, instituicao_id),
    FOREIGN KEY (contato_id, instituicao_id)
        REFERENCES hazardtrack.contato_operacional(id, instituicao_id)
);
-- A URL fica no contato webhook. Segredos permanecem fora destas tabelas.
CREATE TABLE IF NOT EXISTS hazardtrack.integracao_institucional (
    id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    contato_id bigint NOT NULL UNIQUE
        REFERENCES hazardtrack.contato_operacional(id),
    versao_contrato text NOT NULL DEFAULT '1',
    referencia_segredo text,
    verificada_em timestamptz,
    ativa boolean NOT NULL DEFAULT false
);
CREATE TABLE IF NOT EXISTS hazardtrack.configuracao_envio (
    singleton boolean PRIMARY KEY DEFAULT true CHECK (singleton),
    envio_externo_ativo boolean NOT NULL DEFAULT false
);
INSERT INTO hazardtrack.configuracao_envio (singleton)
VALUES (true) ON CONFLICT DO NOTHING;

-- Trilha automatica: ator informado pelo futuro endpoint autenticado.
-- Fora da API, registra o usuario SQL; jamais inventa usuario SIGMA.
CREATE OR REPLACE FUNCTION hazardtrack.auditar_cadastro_operacional()
RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE
    anterior jsonb;
    posterior jsonb;
    ator text;
BEGIN
    IF TG_OP <> 'INSERT' THEN anterior := to_jsonb(OLD); END IF;
    IF TG_OP <> 'DELETE' THEN posterior := to_jsonb(NEW); END IF;
    IF TG_OP = 'UPDATE' AND anterior = posterior THEN RETURN NEW; END IF;
    ator := COALESCE(
        NULLIF(current_setting('hazardtrack.sigma_usuario_id', true), ''),
        'sql:' || session_user
    );
    INSERT INTO hazardtrack.auditoria_administrativa (ator, acao, dados)
    VALUES (ator, 'cadastro_operacional', jsonb_build_object(
        'tabela', TG_TABLE_SCHEMA || '.' || TG_TABLE_NAME,
        'operacao', TG_OP, 'anterior', anterior, 'posterior', posterior
    ));
    IF TG_OP = 'DELETE' THEN RETURN OLD; END IF;
    RETURN NEW;
END;
$$;
CREATE OR REPLACE FUNCTION hazardtrack.validar_arvore_operacional()
RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
    -- Serializa alteracoes da hierarquia, evitando ciclos concorrentes.
    PERFORM pg_advisory_xact_lock(572043003);
    IF NEW.unidade_superior_id IS NOT NULL AND EXISTS (
        WITH RECURSIVE ancestrais AS (
            SELECT id, unidade_superior_id
            FROM hazardtrack.unidade_operacional
            WHERE id = NEW.unidade_superior_id
            UNION
            SELECT u.id, u.unidade_superior_id
            FROM hazardtrack.unidade_operacional u
            JOIN ancestrais a ON u.id = a.unidade_superior_id
        ) SELECT 1 FROM ancestrais WHERE id = NEW.id
    ) THEN
        RAISE EXCEPTION 'Ciclo na hierarquia operacional'
            USING ERRCODE = '23514';
    END IF;
    RETURN NEW;
END;
$$;
DROP TRIGGER IF EXISTS validar_arvore ON hazardtrack.unidade_operacional;
CREATE TRIGGER validar_arvore BEFORE INSERT OR UPDATE
ON hazardtrack.unidade_operacional FOR EACH ROW
EXECUTE FUNCTION hazardtrack.validar_arvore_operacional();

CREATE OR REPLACE FUNCTION hazardtrack.atualizar_data_dominio()
RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
    NEW.atualizado_em := now();
    RETURN NEW;
END;
$$;

DO $$
DECLARE t text;
BEGIN
    FOREACH t IN ARRAY ARRAY[
        'dominios.natureza_risco',
        'dominios.responsabilidade_operacional',
        'dominios.tipo_unidade_operacional',
        'dominios.tipo_abrangencia',
        'dominios.papel_institucional',
        'dominios.fase_operacional',
        'dominios.canal_envio',
        'hazardtrack.instituicao_operadora',
        'hazardtrack.unidade_operacional',
        'hazardtrack.programa_operacional',
        'hazardtrack.programa_fase',
        'hazardtrack.abrangencia_operacional',
        'hazardtrack.abrangencia_componente',
        'hazardtrack.documento_referencia',
        'hazardtrack.competencia_operacional',
        'hazardtrack.competencia_referencia',
        'hazardtrack.abrangencia_referencia',
        'hazardtrack.interlocutor_institucional',
        'hazardtrack.contato_operacional',
        'hazardtrack.regra_envio_alerta',
        'hazardtrack.regra_envio_destino',
        'hazardtrack.integracao_institucional',
        'hazardtrack.configuracao_envio'
    ] LOOP
        EXECUTE format('DROP TRIGGER IF EXISTS auditar_cadastro ON %s', t);
        EXECUTE format(
            'CREATE TRIGGER auditar_cadastro AFTER INSERT OR UPDATE'
            ' OR DELETE ON %s FOR EACH ROW EXECUTE FUNCTION'
            ' hazardtrack.auditar_cadastro_operacional()', t);
        IF t LIKE 'dominios.%' THEN
            EXECUTE format(
                'DROP TRIGGER IF EXISTS atualizar_data ON %s', t);
            EXECUTE format(
                'CREATE TRIGGER atualizar_data BEFORE UPDATE ON %s'
                ' FOR EACH ROW EXECUTE FUNCTION'
                ' hazardtrack.atualizar_data_dominio()', t);
        END IF;
    END LOOP;
END;
$$;
WITH aplicada AS (
    INSERT INTO hazardtrack.versao_esquema (versao) VALUES (3)
    ON CONFLICT DO NOTHING RETURNING versao
)
INSERT INTO hazardtrack.auditoria_administrativa (ator, acao, dados)
SELECT 'sql:' || session_user, 'migracao_esquema',
       jsonb_build_object('versao', versao,
                          'arquivo', '003_gestao_institucional.sql')
FROM aplicada;
