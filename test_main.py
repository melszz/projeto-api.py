"""
Testes automatizados da API.

Como rodar:
    pip install pytest httpx
    pytest -v
"""

import pytest
from fastapi.testclient import TestClient

import main

client = TestClient(main.app)

# Chave de API usada nos endpoints protegidos (deve ser igual à CHAVE_API do main.py)
HEADERS_AUTENTICADO = {"x-api-key": "12345"}


@pytest.fixture(autouse=True)
def limpar_reservas():
    """Remove todas as reservas antes de cada teste, mantendo as salas."""
    conn = main.get_conn()
    conn.execute("DELETE FROM reservas")
    conn.commit()
    conn.close()
    main._cache_salas = None  # reseta o cache de salas entre os testes
    yield


def payload_reserva(**overrides):
    dados = {
        "responsavel": "Ana Silva",
        "sala_id": 1,
        "data": "2026-08-01",
        "horario_inicial": "09:00:00",
        "horario_final": "10:00:00",
        "observacao": "Reunião de alinhamento",
    }
    dados.update(overrides)
    return dados


def test_listar_salas_retorna_as_3_salas_iniciais():
    resposta = client.get("/salas")
    assert resposta.status_code == 200
    salas = resposta.json()
    assert len(salas) == 3


def test_criar_reserva_com_sucesso():
    resposta = client.post("/reservas", json=payload_reserva(), headers=HEADERS_AUTENTICADO)
    assert resposta.status_code == 201
    dados = resposta.json()
    assert dados["responsavel"] == "Ana Silva"


def test_criar_reserva_sem_chave_de_api_e_negado():
    resposta = client.post("/reservas", json=payload_reserva())
    assert resposta.status_code == 422


def test_nao_permite_sala_inexistente():
    resposta = client.post(
        "/reservas", json=payload_reserva(sala_id=999), headers=HEADERS_AUTENTICADO
    )
    assert resposta.status_code == 404


def test_horario_final_antes_do_inicial_e_invalido():
    resposta = client.post(
        "/reservas",
        json=payload_reserva(horario_inicial="10:00:00", horario_final="09:00:00"),
        headers=HEADERS_AUTENTICADO,
    )
    assert resposta.status_code == 422


def test_nao_permite_conflito_de_horario():
    client.post("/reservas", json=payload_reserva(), headers=HEADERS_AUTENTICADO)
    resposta = client.post(
        "/reservas",
        json=payload_reserva(horario_inicial="09:30:00", horario_final="10:30:00"),
        headers=HEADERS_AUTENTICADO,
    )
    assert resposta.status_code == 409


def test_permite_reserva_em_horario_diferente():
    client.post("/reservas", json=payload_reserva(), headers=HEADERS_AUTENTICADO)
    resposta = client.post(
        "/reservas",
        json=payload_reserva(horario_inicial="10:00:00", horario_final="11:00:00"),
        headers=HEADERS_AUTENTICADO,
    )
    assert resposta.status_code == 201


def test_listar_reservas():
    client.post("/reservas", json=payload_reserva(), headers=HEADERS_AUTENTICADO)
    resposta = client.get("/reservas")
    assert resposta.status_code == 200
    assert len(resposta.json()) == 1


def test_buscar_reserva_por_id():
    criada = client.post(
        "/reservas", json=payload_reserva(), headers=HEADERS_AUTENTICADO
    ).json()
    resposta = client.get(f"/reservas/{criada['id']}")
    assert resposta.status_code == 200
    assert resposta.json()["id"] == criada["id"]


def test_buscar_reserva_inexistente_retorna_404():
    resposta = client.get("/reservas/9999")
    assert resposta.status_code == 404

def test_atualizar_reserva():
    criada = client.post(
        "/reservas", json=payload_reserva(), headers=HEADERS_AUTENTICADO
    ).json()
    resposta = client.put(
        f"/reservas/{criada['id']}",
        json=payload_reserva(responsavel="Bruno Souza"),
        headers=HEADERS_AUTENTICADO,
    )
    assert resposta.status_code == 200
    assert resposta.json()["responsavel"] == "Bruno Souza"


def test_excluir_reserva():
    criada = client.post(
        "/reservas", json=payload_reserva(), headers=HEADERS_AUTENTICADO
    ).json()
    resposta = client.delete(f"/reservas/{criada['id']}", headers=HEADERS_AUTENTICADO)
    assert resposta.status_code == 204
    assert client.get(f"/reservas/{criada['id']}").status_code == 404


def test_filtro_por_sala():
    client.post(
        "/reservas", json=payload_reserva(sala_id=1), headers=HEADERS_AUTENTICADO
    )
    client.post(
        "/reservas",
        json=payload_reserva(sala_id=2, horario_inicial="14:00:00", horario_final="15:00:00"),
        headers=HEADERS_AUTENTICADO,
    )
    resposta = client.get("/reservas", params={"sala_id": 2})
    dados = resposta.json()
    assert len(dados) == 1
    assert dados[0]["sala_id"] == 2