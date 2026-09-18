import os
import certifi
from urllib.parse import quote_plus
from dotenv import load_dotenv
from flask import Flask, jsonify, request
from flask_cors import CORS
from flask_sqlalchemy import SQLAlchemy

load_dotenv()

app = Flask(__name__)
CORS(app)

DATABASE_URL = os.getenv("DATABASE_URL")

if DATABASE_URL:
    app.config["SQLALCHEMY_DATABASE_URI"] = DATABASE_URL
else:
    DB_URI = (
        f"mysql+pymysql://{quote_plus(os.getenv('DB_USER'))}:"
        f"{quote_plus(os.getenv('DB_PASSWORD'))}@"
        f"{os.getenv('DB_HOST')}:{os.getenv('DB_PORT')}/{os.getenv('DB_NAME')}"
    )
    app.config["SQLALCHEMY_DATABASE_URI"] = DB_URI
    app.config["SQLALCHEMY_ENGINE_OPTIONS"] = {
        "connect_args": {
            "ssl_ca": certifi.where(),
            "ssl_verify_cert": True,
            "ssl_verify_identity": True,
        }
    }

app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
db = SQLAlchemy(app)


class Servicio(db.Model):
    __tablename__ = "servicios"
    id = db.Column(db.Integer, primary_key=True)
    nombre = db.Column(db.String(100), nullable=False)
    precio = db.Column(db.Float, nullable=False)

    def to_dict(self):
        return {"id": self.id, "nombre": self.nombre, "precio": self.precio}


class Reserva(db.Model):
    __tablename__ = "reservas"
    id = db.Column(db.Integer, primary_key=True)
    cliente = db.Column(db.String(100), nullable=False)
    servicio_id = db.Column(db.Integer, db.ForeignKey("servicios.id"), nullable=False)
    fecha = db.Column(db.String(40), nullable=False)
    estado = db.Column(db.String(20), default="pendiente")

    def to_dict(self):
        return {
            "id": self.id,
            "cliente": self.cliente,
            "servicio_id": self.servicio_id,
            "fecha": self.fecha,
            "estado": self.estado,
        }


# ---------- Rutas de estado y setup ----------

@app.route("/")
def status():
    return jsonify({
        "status": "ok",
        "proyecto": "ReservaLocal API",
        "mensaje": "Backend operativo con base de datos"
    })


@app.route("/setup")
def setup():
    db.create_all()
    if Servicio.query.count() == 0:
        db.session.add_all([
            Servicio(nombre="Corte de pelo", precio=15),
            Servicio(nombre="Arreglo de barba", precio=10),
        ])
        db.session.commit()
    return jsonify({"status": "tablas creadas y datos de prueba insertados"})


# ---------- SERVICIOS (lectura) ----------

@app.route("/servicios")
def listar_servicios():
    return jsonify([s.to_dict() for s in Servicio.query.all()])


# ---------- RESERVAS: CRUD completo ----------

@app.route("/reservas", methods=["GET"])
def listar_reservas():
    return jsonify([r.to_dict() for r in Reserva.query.all()])


@app.route("/reservas", methods=["POST"])
def crear_reserva():
    datos = request.get_json(silent=True) or {}
    cliente = datos.get("cliente")
    servicio_id = datos.get("servicio_id")
    fecha = datos.get("fecha")
    if not cliente or not servicio_id or not fecha:
        return jsonify({"error": "Faltan campos: cliente, servicio_id, fecha"}), 400
    servicio = Servicio.query.get(servicio_id)
    if servicio is None:
        return jsonify({"error": "El servicio indicado no existe"}), 404
    reserva = Reserva(cliente=cliente, servicio_id=servicio_id,
                      fecha=fecha, estado="pendiente")
    db.session.add(reserva)
    db.session.commit()
    return jsonify(reserva.to_dict()), 201


@app.route("/reservas/<int:id>", methods=["PUT"])
def editar_reserva(id):
    reserva = Reserva.query.get_or_404(id)
    datos = request.get_json(silent=True) or {}
    if "cliente" in datos:
        reserva.cliente = datos["cliente"]
    if "fecha" in datos:
        reserva.fecha = datos["fecha"]
    if "estado" in datos:
        if datos["estado"] not in ("pendiente", "confirmada", "cancelada"):
            return jsonify({"error": "Estado no valido. Usa: pendiente, confirmada o cancelada"}), 400
        reserva.estado = datos["estado"]
    db.session.commit()
    return jsonify(reserva.to_dict())


@app.route("/reservas/<int:id>", methods=["DELETE"])
def borrar_reserva(id):
    reserva = Reserva.query.get_or_404(id)
    db.session.delete(reserva)
    db.session.commit()
    return jsonify({"status": "reserva eliminada", "id": id})


if __name__ == "__main__":
    app.run(debug=True)