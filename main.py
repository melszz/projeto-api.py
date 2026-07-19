import sqlite3
from datetime import date, time
from typing import Optional

from fastapi import FastAPI, HTTPException, Query
from pydantic import BaseModel, field_validator

DB_FILE = "reserva_salas.db"

app = FastAPI(title="Sistema de Reserva de Salas")


# ---------- Banco de dados ----------

def get_conn():
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row
    return conn


def iniciar_banco():
    conn = get_conn()
    conn.execute("""
        CREATE TABLE IF NOT EXISTS salas (
            id INTEGER PRIMARY KEY,
            nome TEXT NOT NULL,
            capacidade INTEGER NOT NULL
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS reservas (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            responsavel TEXT NOT NULL,
            sala_id INTEGER NOT NULL REFERENCES salas(id),
            data TEXT NOT NULL,
            horario_inicial TEXT NOT NULL,
            horario_final TEXT NOT NULL,
            observacao TEXT
        )
    """)
    # Cadastro (seed) das 3 salas iniciais, só se a tabela estiver vazia
    if conn.execute("SELECT COUNT(*) FROM salas").fetchone()[0] == 0:
        conn.executemany(
            "INSERT INTO salas (id, nome, capacidade) VALUES (?, ?, ?)",
            [(1, "Sala A", 6), (2, "Sala B", 10), (3, "Sala C", 20)],
        )
    conn.commit()
    conn.close()


iniciar_banco()


# ---------- Schema de entrada da reserva (com validações) ----------

class ReservaEntrada(BaseModel):
    responsavel: str
    sala_id: int
    data: date
    horario_inicial: time
    horario_final: time
    observacao: Optional[str] = None

    @field_validator("horario_final")
    @classmethod
    def valida_horario(cls, v, info):
        inicio = info.data.get("horario_inicial")
        if inicio is not None and v <= inicio:
            raise ValueError("horario_final deve ser posterior ao horario_inicial")
        return v


# ---------- Funções auxiliares ----------

def sala_existe(conn, sala_id: int) -> bool:
    return conn.execute("SELECT 1 FROM salas WHERE id = ?", (sala_id,)).fetchone() is not None


def existe_conflito(conn, sala_id, data_, inicio, fim, ignorar_id=None) -> bool:
    query = """
        SELECT 1 FROM reservas
        WHERE sala_id = ? AND data = ?
          AND horario_inicial < ? AND horario_final > ?
    """
    params = [sala_id, str(data_), str(fim), str(inicio)]
    if ignorar_id is not None:
        query += " AND id != ?"
        params.append(ignorar_id)
    return conn.execute(query, params).fetchone() is not None


def reserva_para_dict(row) -> dict:
    return {
        "id": row["id"],
        "responsavel": row["responsavel"],
        "sala_id": row["sala_id"],
        "data": row["data"],
        "horario_inicial": row["horario_inicial"],
        "horario_final": row["horario_final"],
        "observacao": row["observacao"],
    }


# ---------- Endpoints ----------

@app.get("/")
def raiz():
    return {"mensagem": "API Funcionando!"}


# ----- SALAS -----

@app.get("/salas")
def listar_salas():
    conn = get_conn()
    salas = conn.execute("SELECT * FROM salas").fetchall()
    conn.close()
    return [dict(s) for s in salas]


# ----- RESERVAS -----

@app.post("/reservas", status_code=201)
def criar_reserva(reserva: ReservaEntrada):
    conn = get_conn()
    if not sala_existe(conn, reserva.sala_id):
        conn.close()
        raise HTTPException(404, f"Sala {reserva.sala_id} não existe")

    if existe_conflito(conn, reserva.sala_id, reserva.data, reserva.horario_inicial, reserva.horario_final):
        conn.close()
        raise HTTPException(409, "Já existe uma reserva para esta sala neste horário")

    cursor = conn.execute(
        """INSERT INTO reservas (responsavel, sala_id, data, horario_inicial, horario_final, observacao)
           VALUES (?, ?, ?, ?, ?, ?)""",
        (reserva.responsavel, reserva.sala_id, str(reserva.data),
         str(reserva.horario_inicial), str(reserva.horario_final), reserva.observacao),
    )
    conn.commit()
    nova = conn.execute("SELECT * FROM reservas WHERE id = ?", (cursor.lastrowid,)).fetchone()
    conn.close()
    return reserva_para_dict(nova)


@app.get("/reservas")
def listar_reservas(
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    data: Optional[date] = None,
    sala_id: Optional[int] = None,
    ordernar_por: str = Query("data", description="Campos: data, horario_inicial, id, responsavel"),
    ordem: str = Query("asc", description="asc ou desc"),
):
    conn = get_conn()
    query = "SELECT * FROM reservas WHERE 1=1"
    params = []
    if data is not None:
        query += " AND data = ?"
        params.append(str(data))
    if sala_id is not None:
        query += " AND sala_id = ?"
        params.append(sala_id)
        
    colunas_validas = {"data", "horario_inicial", "id", "responsavel"}
    coluna = ordenar_por if ordenar_por in colunas_validas else "data"
    direcao = "DESC" if ordem.lower() == "desc" else "ASC"
    query += f" ORDER BY {coluna} {direcao} LIMIT ? OFFSET ?"
    params += [limit, skip]

    rows = conn.execute(query, params).fetchall()
    conn.close()
    return [reserva_para_dict(r) for r in rows]


@app.get("/reservas/{reserva_id}")
def buscar_reserva(reserva_id: int):
    conn = get_conn()
    row = conn.execute("SELECT * FROM reservas WHERE id = ?", (reserva_id,)).fetchone()
    conn.close()
    if row is None:
        raise HTTPException(404, "Reserva não encontrada")
    return reserva_para_dict(row)


@app.put("/reservas/{reserva_id}")
def atualizar_reserva(reserva_id: int, dados: ReservaEntrada):
    conn = get_conn()
    existente = conn.execute("SELECT * FROM reservas WHERE id = ?", (reserva_id,)).fetchone()
    if existente is None:
        conn.close()
        raise HTTPException(404, "Reserva não encontrada")

    if not sala_existe(conn, dados.sala_id):
        conn.close()
        raise HTTPException(404, f"Sala {dados.sala_id} não existe")

    if existe_conflito(conn, dados.sala_id, dados.data, dados.horario_inicial, dados.horario_final, ignorar_id=reserva_id):
        conn.close()
        raise HTTPException(409, "Já existe uma reserva para esta sala neste horário")

    conn.execute(
        """UPDATE reservas SET responsavel=?, sala_id=?, data=?, horario_inicial=?, horario_final=?, observacao=?
           WHERE id=?""",
        (dados.responsavel, dados.sala_id, str(dados.data),
         str(dados.horario_inicial), str(dados.horario_final), dados.observacao, reserva_id),
    )
    conn.commit()
    atualizada = conn.execute("SELECT * FROM reservas WHERE id = ?", (reserva_id,)).fetchone()
    conn.close()
    return reserva_para_dict(atualizada)


@app.delete("/reservas/{reserva_id}", status_code=204)
def excluir_reserva(reserva_id: int):
    conn = get_conn()
    existente = conn.execute("SELECT * FROM reservas WHERE id = ?", (reserva_id,)).fetchone()
    if existente is None:
        conn.close()
        raise HTTPException(404, "Reserva não encontrada")
    conn.execute("DELETE FROM reservas WHERE id = ?", (reserva_id,))
    conn.commit()
    conn.close()