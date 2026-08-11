from src.models.normalization import normalizar_titulo


def test_minusculas_y_tildes():
    assert normalizar_titulo("Análisis de Sistemas") == "analisis de sistemas"


def test_puntuacion_y_espacios():
    assert normalizar_titulo("  Título: con,  puntuación!!  ") == "titulo con puntuacion"


def test_string_vacio():
    assert normalizar_titulo("") == ""
