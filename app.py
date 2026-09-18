from flask import Flask, jsonify
from flask_cors import CORS

app = Flask(__name__)
CORS(app)


@app.route("/")
def status():
    return jsonify({
        "status": "ok",
        "proyecto": "ReservaLocal API",
        "mensaje": "Backend operativo"
    })


@app.route("/servicios")
def servicios():
    return jsonify([
        {"id": 1, "nombre": "Corte de pelo", "precio": 15},
        {"id": 2, "nombre": "Arreglo de barba", "precio": 10}
    ])


if __name__ == "__main__":
    app.run(debug=True)