import os
import certifi
from urllib.parse import quote_plus
from dotenv import load_dotenv
from flask import Flask, jsonify
from flask_cors import CORS
from flask_sqlalchemy import SQLAlchemy

load_dotenv()  # lee el archivo .env

DB_URI = (
    f"mysql+pymysql://{quote_plus(os.getenv('DB_USER'))}:"
    f"{quote_plus(os.getenv('DB_PASSWORD'))}@"
    f"{os.getenv('DB_HOST')}:{os.getenv('DB_PORT')}/{os.getenv('DB_NAME')}"
)

app = Flask(__name__)
CORS(app)

app.config["SQLALCHEMY_DATABASE_URI"] = DB_URI
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
app.config["SQLALCHEMY_ENGINE_OPTIONS"] = {
    "connect_args": {
        "ssl_ca": certifi.where(),
        "ssl_verify_cert": True,
        "ssl_verify_identity": True,
    }
}
db = SQLAlchemy(app)


class Servicio(db.Model):
    __tablename__ = "servicios"
    id = db.Column(db.Integer, primary_key=True)
    nombre = db.Column(db.String(100), nullable=False)
    precio = db.Column(db.Float, nullable=False)


@app.route("/")
def status():
    return jsonify({
        "status": "ok",
        "proyecto": "ReservaLocal API",
        "mensaje": "Backend operativo con MySQL (TiDB Cloud)"
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


@app.route("/servicios")
def servicios():
    lista = Servicio.query.all()
    return jsonify([
        {"id": s.id, "nombre": s.nombre, "precio": s.precio}
        for s in lista
    ])


if __name__ == "__main__":
    app.run(debug=True)