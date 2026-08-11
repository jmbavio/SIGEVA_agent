from src.matching.engine import emparejar
from src.matching.resultado import NivelMatch
from src.models.schema import AntecedenteItem, InstanciaSigeva, RubroTipo


def _item(titulo, anio=2020, doi=None, isbn=None, instancia=InstanciaSigeva.UNS, rubro_original="Artículos en Revistas"):
    return AntecedenteItem(
        instancia_origen=instancia,
        rubro=RubroTipo.ARTICULO,
        rubro_original=rubro_original,
        titulo=titulo,
        anio=anio,
        doi=doi,
        isbn=isbn,
    )


def test_exact_match_por_doi():
    a = _item("Un título cualquiera", doi="10.1/ABC")
    b = _item("Un título completamente distinto", doi="10.1/abc", instancia=InstanciaSigeva.CONICET)

    resultado = emparejar([a], [b])

    assert len(resultado.pares) == 1
    assert resultado.pares[0].nivel == NivelMatch.EXACTO
    assert not resultado.solo_en_a and not resultado.solo_en_b


def test_structured_match_por_titulo_y_anio():
    a = _item("Modelos Estocásticos: Una Introducción", anio=2021)
    b = _item("modelos estocasticos una introduccion", anio=2021, instancia=InstanciaSigeva.CONICET)

    resultado = emparejar([a], [b])

    assert len(resultado.pares) == 1
    assert resultado.pares[0].nivel == NivelMatch.ESTRUCTURADO


def test_fuzzy_match_bajo_umbral():
    a = _item("Evaluación de algoritmos de aprendizaje automático", anio=2022)
    b = _item("Evaluación de algoritmos de machine learning", anio=2022, instancia=InstanciaSigeva.CONICET)

    resultado = emparejar([a], [b], umbral_fuzzy=60)

    assert len(resultado.pares) == 1
    assert resultado.pares[0].nivel == NivelMatch.FUZZY
    assert resultado.pares[0].score is not None


def test_sin_match_queda_en_las_listas_restantes():
    a = _item("Un antecedente único de UNS", anio=2023)
    b = _item("Un antecedente completamente distinto de CONICET", anio=2019, instancia=InstanciaSigeva.CONICET)

    resultado = emparejar([a], [b], umbral_fuzzy=85)

    assert resultado.pares == []
    assert resultado.solo_en_a == [a]
    assert resultado.solo_en_b == [b]
