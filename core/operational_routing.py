"""Resolucao explicavel de destinatarios; nenhuma entrega externa."""
from shapely.geometry import Point, LineString, shape

from . import alert_store, zones


def in_scope(component, ua):
    reference = component.get("referencia_territorial")
    if reference:
        return reference in {
            "estado:SP", "ua:" + str(ua["ua_id"]),
            "regiao:" + str(ua.get("regiao_id")),
        }
    if component.get("sigla_rodovia"):
        return (
            ua.get("sigla_rodovia") == component["sigla_rodovia"]
            and float(ua.get("km_inicial") or 0)
            <= float(component["km_final"])
            and float(ua.get("km_final") or 0)
            >= float(component["km_inicial"])
        )
    if component.get("geometria_geojson"):
        geometry = component["geometria_geojson"]
        if geometry.get("type") == "Feature":
            geometry = geometry["geometry"]
        coordinates = ua.get("geometry")
        target = (LineString([(p[1], p[0]) for p in coordinates])
                  if coordinates else Point(ua["lon"], ua["lat"]))
        return shape(geometry).intersects(target)
    if component.get("codigo_ibge"):
        return str(ua.get("codigo_ibge", "")) == component["codigo_ibge"]
    return False


def simulate_routing(ua_id, nature, level, phase, today):
    if nature not in ("geo", "hidro", "fire") or level not in range(5):
        raise ValueError("Selecione natureza e nível válidos.")
    ua = next((u for u in zones.get_zones_geo()
               if str(u["ua_id"]) == ua_id), None)
    if not ua:
        raise ValueError("Unidade de análise não encontrada.")
    ua = dict(ua)
    if not ua.get("codigo_ibge"):
        import geopandas as gpd
        from .managed_geodata import gpkg_path
        municipalities = gpd.read_file(
            gpkg_path(), layer="municipios_area_estudo",
        )
        matches = municipalities[
            municipalities["nome_ibge"] == ua.get("municipio")
        ]
        if len(matches) == 1:
            ua["codigo_ibge"] = str(matches.iloc[0]["geocodigo"])
    with alert_store.connection() as conn:
        rules = conn.execute(
            "SELECT r.*, c.abrangencia_id, c.fase_id, u.nome AS unidade "
            "FROM hazardtrack.regra_envio_alerta r "
            "JOIN hazardtrack.competencia_operacional c "
            "ON c.id=r.competencia_id "
            "JOIN dominios.natureza_risco n ON n.id=c.natureza_risco_id "
            "JOIN hazardtrack.unidade_operacional u ON u.id=c.unidade_id "
            "JOIN hazardtrack.instituicao_operadora i "
            "ON i.id=c.instituicao_id "
            "JOIN hazardtrack.programa_operacional p ON p.id=c.programa_id "
            "JOIN hazardtrack.abrangencia_operacional a "
            "ON a.id=c.abrangencia_id "
            "WHERE c.ativa AND u.ativa AND i.ativa AND n.ativo "
            "AND p.ativo AND a.ativa AND n.codigo=%s "
            "AND c.vigente_desde<=%s "
            "AND (c.vigente_ate IS NULL OR c.vigente_ate>=%s) "
            "AND p.vigente_desde<=%s "
            "AND (p.vigente_ate IS NULL OR p.vigente_ate>=%s) "
            "AND a.vigente_desde<=%s "
            "AND (a.vigente_ate IS NULL OR a.vigente_ate>=%s) "
            "AND (c.fase_id IS NULL OR EXISTS (SELECT 1 "
            "FROM hazardtrack.programa_fase pf "
            "JOIN dominios.fase_operacional f ON f.id=pf.fase_id "
            "WHERE pf.programa_id=c.programa_id AND pf.fase_id=c.fase_id "
            "AND pf.ativa AND f.ativo))",
            (nature, today, today, today, today, today, today),
        ).fetchall()
        result = []
        warnings = set()
        for rule in rules:
            if rule["fase_id"] is not None:
                if str(rule["fase_id"]) != str(phase):
                    warnings.add("Há regras de outra fase operacional.")
                    continue
            criteria = rule["criterios"]
            if set(criteria) - {"nivel_minimo", "nivel_maximo"}:
                warnings.add("Regra com critérios não reconhecidos excluída.")
                continue
            minimum = criteria.get("nivel_minimo", 0)
            maximum = criteria.get("nivel_maximo", 4)
            if not isinstance(minimum, int) or not isinstance(maximum, int):
                warnings.add("Regra com limites inválidos excluída.")
                continue
            if not minimum <= level <= maximum:
                continue
            components = conn.execute(
                "SELECT * FROM hazardtrack.abrangencia_componente "
                "WHERE abrangencia_id=%s", (rule["abrangencia_id"],),
            ).fetchall()
            match = False
            for component in components:
                try:
                    match = match or in_scope(component, ua)
                except (ValueError, TypeError, KeyError):
                    warnings.add("Geometria inválida não foi considerada.")
                if (component.get("codigo_ibge")
                        and not ua.get("codigo_ibge")):
                    warnings.add("UA sem código IBGE: área não inferida.")
            if not match:
                continue
            contacts = conn.execute(
                "SELECT c.rotulo, c.destino, c.ativo, "
                "d.ativo AS vinculo_ativo,"
                " n.nome AS canal FROM hazardtrack.regra_envio_destino d "
                "JOIN hazardtrack.contato_operacional c ON c.id=d.contato_id "
                "JOIN dominios.canal_envio n ON n.id=c.canal_id "
                "WHERE d.regra_id=%s AND n.ativo", (rule["id"],),
            ).fetchall()
            result.append({
                "regra": rule["nome"], "unidade": rule["unidade"],
                "instituicao_id": rule["instituicao_id"],
                "ativa": rule["ativa"], "contatos": contacts,
                "incluir_json": rule["incluir_json"],
                "incluir_instrucoes_api": rule["incluir_instrucoes_api"],
            })
    return {"simulacao": True, "envios_realizados": 0,
            "ua_id": ua_id, "natureza": nature, "nivel": level,
            "destinatarios": result, "avisos": sorted(warnings)}
