"""
Sistema de Estacionamento - Flask + SQLite
Executar:  python app.py
Depois abra no navegador:  http://SEU_IP:5000
(o terminal do Flask mostra o IP da rede ao iniciar)
"""
import math
import socket
import sqlite3
from datetime import datetime

from flask import Flask, g, jsonify, render_template, request

DB_NAME = "estacionamento.db"
FMT = "%Y-%m-%d %H:%M:%S"

app = Flask(__name__)


# ---------------------------------------------------------------- Banco
def conectar():
    con = sqlite3.connect(DB_NAME)
    con.row_factory = sqlite3.Row
    con.execute("PRAGMA foreign_keys = ON")
    return con


def get_db():
    if "db" not in g:
        g.db = conectar()
    return g.db


@app.teardown_appcontext
def close_db(exception=None):
    db = g.pop("db", None)
    if db is not None:
        db.close()


def criar_tabelas():
    con = conectar()
    con.executescript("""
    CREATE TABLE IF NOT EXISTS Clientes (
        ID   INTEGER PRIMARY KEY AUTOINCREMENT,
        Nome TEXT NOT NULL,
        Fone TEXT,
        CPF  TEXT NOT NULL UNIQUE
    );
    CREATE TABLE IF NOT EXISTS Precos (
        ID           INTEGER PRIMARY KEY AUTOINCREMENT,
        Tipo_Veiculo TEXT NOT NULL UNIQUE,
        Valor_Hora   REAL NOT NULL,
        Valor_Diaria REAL NOT NULL
    );
    CREATE TABLE IF NOT EXISTS Veiculos (
        ID        INTEGER PRIMARY KEY AUTOINCREMENT,
        Placa     TEXT NOT NULL UNIQUE,
        Modelo    TEXT,
        Marca     TEXT,
        Cor       TEXT,
        ClienteID INTEGER NOT NULL REFERENCES Clientes(ID),
        Preco_ID  INTEGER NOT NULL REFERENCES Precos(ID)
    );
    CREATE TABLE IF NOT EXISTS Estadias (
        ID              INTEGER PRIMARY KEY AUTOINCREMENT,
        Veiculo_ID      INTEGER NOT NULL REFERENCES Veiculos(ID),
        Horario_Entrada TEXT NOT NULL,
        Horario_Saida   TEXT,
        Valor_Total     REAL,
        Status          TEXT NOT NULL DEFAULT 'Aberta'
    );
    CREATE TABLE IF NOT EXISTS Pagamentos (
        ID              INTEGER PRIMARY KEY AUTOINCREMENT,
        Estadia_ID      INTEGER NOT NULL REFERENCES Estadias(ID),
        Forma_Pagamento TEXT NOT NULL,
        Valor_Pago      REAL NOT NULL,
        Data_Pago       TEXT NOT NULL
    );
    """)
    if con.execute("SELECT COUNT(*) FROM Precos").fetchone()[0] == 0:
        con.executemany(
            "INSERT INTO Precos (Tipo_Veiculo, Valor_Hora, Valor_Diaria) VALUES (?,?,?)",
            [("Carro", 8.0, 40.0), ("Moto", 4.0, 20.0), ("Caminhonete", 12.0, 60.0)],
        )
    con.commit()
    con.close()


# ---------------------------------------------------------------- Utilidades
def agora():
    return datetime.now().strftime(FMT)


def calcular_valor(entrada, saida, valor_hora, valor_diaria):
    """Horas são cobradas por hora cheia (mín. 1h). Nunca passa da diária por dia."""
    minutos = max((saida - entrada).total_seconds() / 60, 0)
    horas = max(math.ceil(minutos / 60), 1)
    dias, resto = divmod(horas, 24)
    return dias * valor_diaria + min(resto * valor_hora, valor_diaria)


def row_to_dict(row):
    return dict(row) if row is not None else None


def rows_to_list(rows):
    return [dict(r) for r in rows]


def erro(msg, status=400):
    return jsonify({"erro": msg}), status


# ---------------------------------------------------------------- Página
@app.route("/")
def index():
    return render_template("index.html")


# ---------------------------------------------------------------- Clientes
@app.route("/api/clientes", methods=["GET"])
def listar_clientes():
    db = get_db()
    return jsonify(rows_to_list(db.execute("SELECT * FROM Clientes ORDER BY Nome").fetchall()))


@app.route("/api/clientes", methods=["POST"])
def criar_cliente():
    dados = request.get_json(force=True)
    nome = (dados.get("nome") or "").strip()
    fone = (dados.get("fone") or "").strip()
    cpf = "".join(c for c in (dados.get("cpf") or "") if c.isdigit())
    if not nome or len(cpf) != 11:
        return erro("Nome obrigatório e CPF deve ter 11 dígitos.")
    db = get_db()
    try:
        cur = db.execute("INSERT INTO Clientes (Nome, Fone, CPF) VALUES (?,?,?)", (nome, fone, cpf))
        db.commit()
        return jsonify({"ID": cur.lastrowid}), 201
    except sqlite3.IntegrityError:
        return erro("Já existe um cliente com esse CPF.")


# ---------------------------------------------------------------- Preços
@app.route("/api/precos", methods=["GET"])
def listar_precos():
    db = get_db()
    return jsonify(rows_to_list(db.execute("SELECT * FROM Precos ORDER BY ID").fetchall()))


@app.route("/api/precos", methods=["POST"])
def criar_preco():
    dados = request.get_json(force=True)
    tipo = (dados.get("tipo") or "").strip()
    try:
        hora = float(dados.get("hora"))
        diaria = float(dados.get("diaria"))
    except (TypeError, ValueError):
        return erro("Valores de hora/diária inválidos.")
    if not tipo:
        return erro("Tipo de veículo obrigatório.")
    db = get_db()
    try:
        cur = db.execute(
            "INSERT INTO Precos (Tipo_Veiculo, Valor_Hora, Valor_Diaria) VALUES (?,?,?)",
            (tipo, hora, diaria))
        db.commit()
        return jsonify({"ID": cur.lastrowid}), 201
    except sqlite3.IntegrityError:
        return erro("Esse tipo de veículo já existe.")


# ---------------------------------------------------------------- Veículos
@app.route("/api/veiculos", methods=["GET"])
def listar_veiculos():
    db = get_db()
    rows = db.execute("""
        SELECT v.*, c.Nome AS Cliente_Nome, p.Tipo_Veiculo FROM Veiculos v
        JOIN Clientes c ON c.ID = v.ClienteID
        JOIN Precos p ON p.ID = v.Preco_ID ORDER BY v.Placa""").fetchall()
    return jsonify(rows_to_list(rows))


@app.route("/api/veiculos", methods=["POST"])
def criar_veiculo():
    dados = request.get_json(force=True)
    placa = (dados.get("placa") or "").strip().upper()
    modelo = (dados.get("modelo") or "").strip()
    marca = (dados.get("marca") or "").strip()
    cor = (dados.get("cor") or "").strip()
    cliente_id = dados.get("cliente_id")
    preco_id = dados.get("preco_id")
    if not placa or not cliente_id or not preco_id:
        return erro("Placa, cliente e tipo de preço são obrigatórios.")
    db = get_db()
    if not db.execute("SELECT 1 FROM Clientes WHERE ID=?", (cliente_id,)).fetchone():
        return erro("Cliente não encontrado.")
    if not db.execute("SELECT 1 FROM Precos WHERE ID=?", (preco_id,)).fetchone():
        return erro("Tipo de preço não encontrado.")
    try:
        cur = db.execute(
            "INSERT INTO Veiculos (Placa, Modelo, Marca, Cor, ClienteID, Preco_ID) VALUES (?,?,?,?,?,?)",
            (placa, modelo, marca, cor, cliente_id, preco_id))
        db.commit()
        return jsonify({"ID": cur.lastrowid}), 201
    except sqlite3.IntegrityError:
        return erro("Já existe um veículo com essa placa.")


# ---------------------------------------------------------------- Estadias
@app.route("/api/estadias/abertas", methods=["GET"])
def listar_estadias_abertas():
    db = get_db()
    rows = db.execute("""
        SELECT e.ID, e.Horario_Entrada, v.Placa, v.Modelo, c.Nome FROM Estadias e
        JOIN Veiculos v ON v.ID = e.Veiculo_ID
        JOIN Clientes c ON c.ID = v.ClienteID
        WHERE e.Status='Aberta' ORDER BY e.Horario_Entrada""").fetchall()
    return jsonify(rows_to_list(rows))


@app.route("/api/entrada", methods=["POST"])
def registrar_entrada():
    dados = request.get_json(force=True)
    placa = (dados.get("placa") or "").strip().upper()
    db = get_db()
    v = db.execute("SELECT * FROM Veiculos WHERE Placa=?", (placa,)).fetchone()
    if not v:
        return erro("Veículo não cadastrado. Cadastre-o primeiro.")
    if db.execute("SELECT 1 FROM Estadias WHERE Veiculo_ID=? AND Status='Aberta'", (v["ID"],)).fetchone():
        return erro("Esse veículo já está no estacionamento.")
    cur = db.execute("INSERT INTO Estadias (Veiculo_ID, Horario_Entrada, Status) VALUES (?,?, 'Aberta')",
                      (v["ID"], agora()))
    db.commit()
    return jsonify({"ID": cur.lastrowid}), 201


@app.route("/api/saida/consultar", methods=["GET"])
def consultar_saida():
    placa = (request.args.get("placa") or "").strip().upper()
    db = get_db()
    e = db.execute("""
        SELECT e.*, v.Placa, p.Valor_Hora, p.Valor_Diaria FROM Estadias e
        JOIN Veiculos v ON v.ID = e.Veiculo_ID
        JOIN Precos p ON p.ID = v.Preco_ID
        WHERE v.Placa=? AND e.Status='Aberta'""", (placa,)).fetchone()
    if not e:
        return erro("Nenhuma estadia aberta para essa placa.", 404)
    entrada = datetime.strptime(e["Horario_Entrada"], FMT)
    saida = datetime.now()
    total = calcular_valor(entrada, saida, e["Valor_Hora"], e["Valor_Diaria"])
    return jsonify({
        "estadia_id": e["ID"],
        "placa": e["Placa"],
        "entrada": e["Horario_Entrada"],
        "saida": saida.strftime(FMT),
        "total": total,
    })


@app.route("/api/saida/confirmar", methods=["POST"])
def confirmar_saida():
    dados = request.get_json(force=True)
    estadia_id = dados.get("estadia_id")
    forma = (dados.get("forma") or "").strip()
    formas_validas = {"Dinheiro", "Pix", "Cartão de débito", "Cartão de crédito"}
    if forma not in formas_validas:
        return erro("Forma de pagamento inválida.")
    db = get_db()
    e = db.execute("""
        SELECT e.*, p.Valor_Hora, p.Valor_Diaria FROM Estadias e
        JOIN Veiculos v ON v.ID = e.Veiculo_ID
        JOIN Precos p ON p.ID = v.Preco_ID
        WHERE e.ID=? AND e.Status='Aberta'""", (estadia_id,)).fetchone()
    if not e:
        return erro("Estadia não encontrada ou já finalizada.", 404)
    entrada = datetime.strptime(e["Horario_Entrada"], FMT)
    saida = datetime.now()
    total = calcular_valor(entrada, saida, e["Valor_Hora"], e["Valor_Diaria"])
    db.execute("UPDATE Estadias SET Horario_Saida=?, Valor_Total=?, Status='Finalizada' WHERE ID=?",
               (saida.strftime(FMT), total, e["ID"]))
    db.execute("INSERT INTO Pagamentos (Estadia_ID, Forma_Pagamento, Valor_Pago, Data_Pago) VALUES (?,?,?,?)",
               (e["ID"], forma, total, agora()))
    db.commit()
    return jsonify({"total": total})


# ---------------------------------------------------------------- Pagamentos
@app.route("/api/pagamentos", methods=["GET"])
def listar_pagamentos():
    db = get_db()
    rows = db.execute("""
        SELECT pg.*, v.Placa FROM Pagamentos pg
        JOIN Estadias e ON e.ID = pg.Estadia_ID
        JOIN Veiculos v ON v.ID = e.Veiculo_ID ORDER BY pg.Data_Pago""").fetchall()
    return jsonify(rows_to_list(rows))


# ---------------------------------------------------------------- Painel
@app.route("/api/painel", methods=["GET"])
def painel():
    db = get_db()
    dentro = db.execute("SELECT COUNT(*) AS n FROM Estadias WHERE Status='Aberta'").fetchone()["n"]
    hoje = datetime.now().strftime("%Y-%m-%d")
    recebido = db.execute(
        "SELECT COALESCE(SUM(Valor_Pago),0) AS total FROM Pagamentos WHERE substr(Data_Pago,1,10)=?",
        (hoje,)).fetchone()["total"]
    return jsonify({"dentro": dentro, "recebido_hoje": recebido})


def ip_local():
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return "127.0.0.1"


if __name__ == "__main__":
    criar_tabelas()
    ip = ip_local()
    print("\n===========================================")
    print("  Sistema de Estacionamento rodando!")
    print(f"  Neste PC:        http://127.0.0.1:5000")
    print(f"  Pela rede/IP:    http://{ip}:5000")
    print("===========================================\n")
    app.run(host="0.0.0.0", port=5000, debug=True)