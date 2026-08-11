"""Tests de la pasada semántica del diff engine. Usan un resolutor falso
(no llaman a ningún LLM real, no requieren API key) para poder probar la
lógica de armado de candidatos y de reconciliación del ResultadoDiff."""
from src.matching.engine import _candidatos_probables, resolver_semanticamente
from src.matching.resultado import NivelMatch, ResultadoDiff
from src.models.schema import AntecedenteItem, InstanciaSigeva, RubroTipo


def _item(titulo, anio, instancia=InstanciaSigeva.UNS, rubro=RubroTipo.ARTICULO):
    return AntecedenteItem(instancia_origen=instancia, rubro=rubro, rubro_original="Rubro", titulo=titulo, anio=anio)


class _ResolutorFalso:
    """Simula la interfaz ResolutorSemanticoLLM: siempre elige el primer
    candidato (o ninguno, según se configure), sin llamar a ningún LLM."""

    def __init__(self, elegir_indice: int | None = 0):
        self.elegir_indice = elegir_indice
        self.llamadas: list[tuple[AntecedenteItem, list[AntecedenteItem]]] = []

    def resolver(self, item, candidatos):
        self.llamadas.append((item, candidatos))
        if self.elegir_indice is None or not candidatos:
            return None
        return candidatos[self.elegir_indice]


def test_candidatos_probables_filtra_por_cercania_de_anio():
    item = _item("Un antecedente", anio=2020)
    pendientes = [
        _item("Otro cualquiera", anio=2018, instancia=InstanciaSigeva.CONICET),
        _item("Candidato cercano", anio=2021, instancia=InstanciaSigeva.CONICET),
        _item("Candidato exacto", anio=2020, instancia=InstanciaSigeva.CONICET),
    ]
    candidatos = _candidatos_probables(item, pendientes, umbral_anio=1, max_candidatos=5)
    assert {c.titulo for c in candidatos} == {"Candidato cercano", "Candidato exacto"}


def test_candidatos_probables_prioriza_similitud_de_titulo():
    item = _item("Evaluación de algoritmos de aprendizaje automático", anio=2020)
    pendientes = [
        _item("Un tema completamente distinto", anio=2020, instancia=InstanciaSigeva.CONICET),
        _item("Evaluación de algoritmos de machine learning", anio=2020, instancia=InstanciaSigeva.CONICET),
    ]
    candidatos = _candidatos_probables(item, pendientes, umbral_anio=1, max_candidatos=5)
    assert candidatos[0].titulo == "Evaluación de algoritmos de machine learning"


def test_candidatos_probables_respeta_el_maximo():
    item = _item("Un antecedente", anio=2020)
    pendientes = [_item(f"Candidato {i}", anio=2020, instancia=InstanciaSigeva.CONICET) for i in range(10)]
    candidatos = _candidatos_probables(item, pendientes, umbral_anio=1, max_candidatos=3)
    assert len(candidatos) == 3


def test_candidatos_probables_sin_anio_no_da_candidatos():
    item = _item("Un antecedente", anio=None)
    pendientes = [_item("Candidato", anio=2020, instancia=InstanciaSigeva.CONICET)]
    assert _candidatos_probables(item, pendientes, umbral_anio=1, max_candidatos=5) == []


def test_resolver_semanticamente_empareja_y_saca_de_solo_en_b():
    item_a = _item("Un modelo matemático para Facebook", anio=2012)
    item_b = _item("Un modelo matemático para Facebook (versión no publicada)", anio=2012, instancia=InstanciaSigeva.CONICET)
    resultado = ResultadoDiff(pares=[], solo_en_a=[item_a], solo_en_b=[item_b])

    nuevo = resolver_semanticamente(resultado, _ResolutorFalso(elegir_indice=0))

    assert nuevo.solo_en_a == []
    assert nuevo.solo_en_b == []
    assert len(nuevo.pares) == 1
    assert nuevo.pares[0].nivel == NivelMatch.SEMANTICO_LLM
    assert nuevo.pares[0].item_a is item_a
    assert nuevo.pares[0].item_b is item_b


def test_resolver_semanticamente_sin_eleccion_deja_todo_sin_matchear():
    item_a = _item("Antecedente sin equivalente real", anio=2020)
    item_b = _item("Otro antecedente distinto", anio=2020, instancia=InstanciaSigeva.CONICET)
    resultado = ResultadoDiff(pares=[], solo_en_a=[item_a], solo_en_b=[item_b])

    nuevo = resolver_semanticamente(resultado, _ResolutorFalso(elegir_indice=None))

    assert nuevo.pares == []
    assert nuevo.solo_en_a == [item_a]
    assert nuevo.solo_en_b == [item_b]


def test_resolver_semanticamente_no_llama_al_resolutor_sin_candidatos_cercanos():
    item_a = _item("Antecedente de 2020", anio=2020)
    item_b = _item("Antecedente de 1990", anio=1990, instancia=InstanciaSigeva.CONICET)
    resultado = ResultadoDiff(pares=[], solo_en_a=[item_a], solo_en_b=[item_b])
    resolutor = _ResolutorFalso(elegir_indice=0)

    nuevo = resolver_semanticamente(resultado, resolutor)

    assert resolutor.llamadas == []
    assert nuevo.solo_en_a == [item_a]
    assert nuevo.solo_en_b == [item_b]


def test_resolver_semanticamente_preserva_pares_previos():
    from src.matching.resultado import ParEmparejado

    par_previo = ParEmparejado(
        item_a=_item("Ya emparejado", anio=2019),
        item_b=_item("Ya emparejado", anio=2019, instancia=InstanciaSigeva.CONICET),
        nivel=NivelMatch.ESTRUCTURADO,
    )
    resultado = ResultadoDiff(pares=[par_previo], solo_en_a=[], solo_en_b=[])

    nuevo = resolver_semanticamente(resultado, _ResolutorFalso())

    assert nuevo.pares == [par_previo]
