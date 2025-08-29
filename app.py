from flask import Flask, render_template, request, redirect, session, url_for
from flask_socketio import SocketIO, send
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import func
from datetime import datetime, timedelta, date
import os

app = Flask(__name__)
app.secret_key = "segredo123"
socketio = SocketIO(app, async_mode="threading")

# -------------------
# Configuração do Banco SQLite
# -------------------
app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///sistema.db"
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
db = SQLAlchemy(app)

# -------------------
# MODELOS
# -------------------
class Estoque(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    quantidade = db.Column(db.Integer, nullable=False, default=100)

class Mensagem(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    usuario = db.Column(db.String(50), nullable=False)
    texto = db.Column(db.String(500), nullable=False)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)

class Venda(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    data = db.Column(db.Date, default=date.today)

# -------------------
# Inicialização
# -------------------
with app.app_context():
    if not os.path.exists("sistema.db"):
        db.create_all()
        estoque_inicial = Estoque(quantidade=100)
        db.session.add(estoque_inicial)
        db.session.commit()

# -------------------
# Usuários
# -------------------
USERS = {
    "admin": "admin123",
    "user1": "senha1",
    "user2": "senha2",
    "user3": "senha3",
    "user4": "senha4"
}

# -------------------
# ROTAS
# -------------------
@app.route("/", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form["username"]
        password = request.form["password"]
        if username in USERS and USERS[username] == password:
            session["user"] = username
            return redirect(url_for("chat"))
        return "Usuário ou senha inválidos!"
    return render_template("login.html")

@app.route("/chat")
def chat():
    if "user" not in session:
        return redirect(url_for("login"))

    # Limpar mensagens com mais de 24h
    limite = datetime.utcnow() - timedelta(hours=24)
    Mensagem.query.filter(Mensagem.timestamp < limite).delete()
    db.session.commit()

    mensagens = Mensagem.query.order_by(Mensagem.timestamp.asc()).all()
    return render_template("chat.html", user=session["user"], mensagens=mensagens)

@app.route("/estoque", methods=["GET", "POST"])
def estoque_page():
    if "user" not in session:
        return redirect(url_for("login"))

    estoque = Estoque.query.first()

    if request.method == "POST":
        if estoque.quantidade > 0:
            estoque.quantidade -= 1
            db.session.commit()

            # Registrar venda
            venda = Venda()
            db.session.add(venda)
            db.session.commit()

    hoje = date.today()
    vendas_hoje = Venda.query.filter_by(data=hoje).count()
    return render_template("estoque.html", qtd=estoque.quantidade, vendas=vendas_hoje)

@app.route("/admin", methods=["GET", "POST"])
def admin_panel():
    if "user" not in session or session["user"] != "admin":
        return "Acesso negado!"

    estoque = Estoque.query.first()

    if request.method == "POST":
        if "reset_estoque" in request.form:
            valor = request.form.get("valor_inicial", 100)
            estoque.quantidade = int(valor)
            db.session.commit()
        elif "apagar_mensagens" in request.form:
            Mensagem.query.delete()
            db.session.commit()

    # Relatório de vendas por dia
    vendas = db.session.query(
        Venda.data,
        func.count(Venda.id)
    ).group_by(Venda.data).order_by(Venda.data.asc()).all()

    mensagens_count = Mensagem.query.count()
    return render_template("admin.html", qtd=estoque.quantidade,
                           mensagens=mensagens_count, vendas=vendas)

@app.route("/relatorio")
def relatorio():
    if "user" not in session:
        return redirect(url_for("login"))

    vendas_por_dia = (
        db.session.query(Venda.data, func.count(Venda.id))
        .group_by(Venda.data)
        .order_by(Venda.data.asc())
        .all()
    )

    datas = [str(v[0]) for v in vendas_por_dia]
    totais = [v[1] for v in vendas_por_dia]

    return render_template("relatorio.html", vendas=vendas_por_dia, datas=datas, totais=totais)

# -------------------
# CHAT EM TEMPO REAL
# -------------------
@socketio.on("message")
def handleMessage(msg):
    user = session.get("user", "Anônimo")
    nova_msg = Mensagem(usuario=user, texto=msg)
    db.session.add(nova_msg)
    db.session.commit()
    send(f"{user}: {msg}", broadcast=True)

if __name__ == "__main__":
    socketio.run(
        app,
        host="0.0.0.0",
        port=int(os.environ.get("PORT", 5000)),
        allow_unsafe_werkzeug=True
    )