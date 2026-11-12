"""Validacao das migracoes em PostgreSQL exclusivo de teste."""
import os
from pathlib import Path
import unittest
from datetime import date
from unittest.mock import patch, MagicMock
from uuid import uuid4

import psycopg
from psycopg.conninfo import conninfo_to_dict
from psycopg.rows import dict_row


DSN = os.environ.get("HAZARDTRACK_TEST_DATABASE_URL", "")
SQL_DIR = Path(__file__).resolve().parents[1] / "scripts" / "sql"


@unittest.skipUnless(DSN, "Requer PostgreSQL exclusivo de teste")
class TestOperacaoSchema(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        name = conninfo_to_dict(DSN).get("dbname", "")
        if not isinstance(name, str) or not name.startswith(
                "pli_hazardtrack_test_"):
            raise RuntimeError("Recusando banco nao exclusivo de teste")
        with psycopg.connect(DSN) as conn:
            for filename in (
                "001_alertas.sql", "002_administracao.sql",
                "003_gestao_institucional.sql",
            ):
                conn.execute((SQL_DIR / filename).read_bytes())

    def setUp(self):
        self.conn = psycopg.connect(DSN)
        self.addCleanup(self.conn.close)
        self.addCleanup(self.conn.rollback)

    def scalar(self, query, params=None):
        row = self.conn.execute(query, params).fetchone()
        assert row is not None
        return row[0]

    def institution(self):
        return self.scalar(
            "INSERT INTO hazardtrack.instituicao_operadora"
            " (sigma_instituicao_id) VALUES (%s) RETURNING id",
            (uuid4(),),
        )

    def test_routing_matches_scope_and_level_without_delivery(self):
        from core.operational_routing import simulate_routing
        institution = self.institution()
        unit = self.unit(institution)
        program = self.scalar(
            "INSERT INTO hazardtrack.programa_operacional "
            "(codigo,nome,coordenacao_estadual_id,vigente_desde) "
            "VALUES (%s,'Teste',%s,'2020-01-01') RETURNING id",
            (str(uuid4()), institution),
        )
        scope = self.scalar(
            "INSERT INTO hazardtrack.abrangencia_operacional "
            "(codigo,nome,tipo_abrangencia_id,vigente_desde) "
            "VALUES (%s,'Teste',(SELECT id FROM dominios.tipo_abrangencia "
            "WHERE codigo='estado'),'2020-01-01') RETURNING id",
            (str(uuid4()),),
        )
        self.conn.execute(
            "INSERT INTO hazardtrack.abrangencia_componente "
            "(abrangencia_id,referencia_territorial) VALUES (%s,'estado:SP')",
            (scope,),
        )
        competence = self.scalar(
            "INSERT INTO hazardtrack.competencia_operacional "
            "(programa_id,unidade_id,instituicao_id,natureza_risco_id,"
            "responsabilidade_id,papel_id,abrangencia_id,vigente_desde) "
            "VALUES (%s,%s,%s,(SELECT id FROM dominios.natureza_risco "
            "WHERE codigo='geo'),(SELECT id FROM "
            "dominios.responsabilidade_operacional WHERE codigo='resgate'),"
            "(SELECT id FROM dominios.papel_institucional "
            "WHERE codigo='execucao'),%s,'2020-01-01') RETURNING id",
            (program, unit, institution, scope),
        )
        self.conn.execute(
            "INSERT INTO hazardtrack.regra_envio_alerta "
            "(competencia_id,instituicao_id,nome,criterios) "
            "VALUES (%s,%s,'Regra teste','{\"nivel_minimo\":3}')",
            (competence, institution),
        )
        before = self.scalar("SELECT count(*) FROM hazardtrack.notificacao")
        handle = MagicMock()
        # Use dictionary rows only for the routing queries in this transaction.
        handle.__enter__.return_value.execute.side_effect = (
            lambda query, params=None: self.conn.cursor(
                row_factory=dict_row
            ).execute(query, params)
        )
        with patch("core.operational_routing.alert_store.connection",
                   return_value=handle):
            result = simulate_routing(
                'UA-R1-BER-10K-001', 'geo', 3, None, date.today(),
            )
            self.assertEqual(len(result['destinatarios']), 1)
            self.assertEqual(result['envios_realizados'], 0)
            result = simulate_routing(
                'UA-R1-BER-10K-001', 'geo', 2, None, date.today(),
            )
            self.assertEqual(result['destinatarios'], [])
        self.assertEqual(
            self.scalar("SELECT count(*) FROM hazardtrack.notificacao"),
            before,
        )

    def unit(self, institution, parent=None):
        return self.scalar(
            "INSERT INTO hazardtrack.unidade_operacional"
            " (instituicao_id,unidade_superior_id,tipo_unidade_id,"
            " codigo,nome) VALUES (%s,%s,"
            " (SELECT id FROM dominios.tipo_unidade_operacional"
            " WHERE codigo='cco'),%s,'CCO teste') RETURNING id",
            (institution, parent, str(uuid4())),
        )

    def test_defaults_do_not_authorize_delivery(self):
        self.assertFalse(self.scalar(
            "SELECT envio_externo_ativo"
            " FROM hazardtrack.configuracao_envio",
        ))
        inst = self.institution()
        unit = self.unit(inst)
        active = self.scalar(
            "INSERT INTO hazardtrack.contato_operacional"
            " (unidade_id,instituicao_id,canal_id,rotulo,destino)"
            " VALUES (%s,%s,(SELECT id FROM dominios.canal_envio"
            " WHERE codigo='email'),'Plantao','plantao@example.invalid')"
            " RETURNING ativo", (unit, inst),
        )
        self.assertFalse(active)

    def test_domain_is_extensible_and_audited(self):
        self.conn.execute(
            "SELECT set_config('hazardtrack.sigma_usuario_id',%s,true)",
            (str(uuid4()),),
        )
        self.conn.execute(
            "INSERT INTO dominios.responsabilidade_operacional"
            " (codigo,nome) VALUES ('teste_novo','Nova responsabilidade')",
        )
        self.assertEqual(self.scalar(
            "SELECT count(*) FROM hazardtrack.auditoria_administrativa"
            " WHERE dados->'posterior'->>'codigo'='teste_novo'",
        ), 1)

    def test_referenced_domain_cannot_be_deleted(self):
        self.unit(self.institution())
        with self.assertRaises(psycopg.errors.ForeignKeyViolation):
            self.conn.execute(
                "DELETE FROM dominios.tipo_unidade_operacional"
                " WHERE codigo='cco'",
            )

    def test_cannot_mix_institutions_in_hierarchy(self):
        parent = self.unit(self.institution())
        with self.assertRaises(psycopg.errors.ForeignKeyViolation):
            self.unit(self.institution(), parent)

    def test_cannot_create_hierarchy_cycle(self):
        inst = self.institution()
        root = self.unit(inst)
        child = self.unit(inst, root)
        with self.assertRaises(psycopg.errors.CheckViolation):
            self.conn.execute(
                "UPDATE hazardtrack.unidade_operacional"
                " SET unidade_superior_id=%s WHERE id=%s", (child, root),
            )

    def test_contact_must_belong_to_its_institution(self):
        unit = self.unit(self.institution())
        other = self.institution()
        with self.assertRaises(psycopg.errors.ForeignKeyViolation):
            self.conn.execute(
                "INSERT INTO hazardtrack.contato_operacional"
                " (unidade_id,instituicao_id,canal_id,rotulo,destino)"
                " VALUES (%s,%s,(SELECT id FROM dominios.canal_envio"
                " WHERE codigo='email'),'Teste','teste@example.invalid')",
                (unit, other),
            )

    def test_reapply_preserves_domain_edits_and_switch(self):
        self.conn.execute(
            "UPDATE dominios.canal_envio SET nome='Email operacional',"
            " ativo=false WHERE codigo='email'",
        )
        self.conn.execute(
            "UPDATE hazardtrack.configuracao_envio"
            " SET envio_externo_ativo=true",
        )
        self.conn.execute(
            (SQL_DIR / "003_gestao_institucional.sql").read_bytes(),
        )
        self.assertEqual(self.scalar(
            "SELECT nome FROM dominios.canal_envio WHERE codigo='email'",
        ), 'Email operacional')
        self.assertFalse(self.scalar(
            "SELECT ativo FROM dominios.canal_envio WHERE codigo='email'",
        ))
        self.assertTrue(self.scalar(
            "SELECT envio_externo_ativo"
            " FROM hazardtrack.configuracao_envio",
        ))
        self.assertEqual(self.scalar(
            "SELECT count(*) FROM hazardtrack.versao_esquema"
            " WHERE versao=3",
        ), 1)


if __name__ == "__main__":
    unittest.main()
