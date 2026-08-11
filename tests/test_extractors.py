from pathlib import Path

from src.extractors.conicet import CONICETJSONExtractor
from src.extractors.uns import UNSJSONExtractor

DATA_DIR = Path(__file__).resolve().parents[1] / "data"


def test_uns_extractor_lee_datos_de_ejemplo():
    items = UNSJSONExtractor().extraer(DATA_DIR / "ejemplo_uns.json")
    assert len(items) == 7
    assert items[0].id_origen == "UNS-001"
    assert items[0].clave_exacta == "doi:10.1234/rev.2020.001"


def test_conicet_extractor_lee_datos_de_ejemplo():
    items = CONICETJSONExtractor().extraer(DATA_DIR / "ejemplo_conicet.json")
    assert len(items) == 7
    assert items[0].id_origen == "CON-100234"
    # mismo DOI que UNS-001, normalizado a minúsculas
    assert items[0].clave_exacta == "doi:10.1234/rev.2020.001"
