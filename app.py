import os
import certifi
import secrets
from urllib.parse import quote_plus
from dotenv import load_dotenv
from flask import Flask, jsonify, request
from flask_cors import CORS
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
from functools import wraps  # --- SESIÓN 2 (NUEVO): para crear decoradores ---

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


# ---------- MODELOS ----------

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
    
    # --- SESIÓN 2 (NUEVO): vinculamos la reserva a un usuario ---
    usuario_id = db.Column(db.Integer, db.ForeignKey("usuarios.id"), nullable=True)

    def to_dict(self):
        return {
            "id": self.id,
            "cliente": self.cliente,
            "servicio_id": self.servicio_id,
            "fecha": self.fecha,
            "estado": self.estado,
            "usuario_id": self.usuario_id,
        }


class Usuario(db.Model):
    __tablename__ = "usuarios"

    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(256), nullable=False)
    rol = db.Column(db.String(20), nullable=False)
    token = db.Column(db.String(64), nullable=True)

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

    def generar_token(self):
        self.token = secrets.token_hex(32)
        return self.token

    def to_dict(self):
        return {
            "id": self.id,
            "email": self.email,
            "rol": self.rol,
        }


# --- SESIÓN 2 (NUEVO): Funciones auxiliares de seguridad ---

def obtener_usuario_actual():
    """Lee el token del header y devuelve el usuario o None"""
    auth_header = request.headers.get('Authorization')
    if not auth_header or not auth_header.startswith('Bearer '):
        return None
    token = auth_header.split(' ')[1]
    return Usuario.query.filter_by(token=token).first()

def requiere_login(f):
    """Decorador: exige que el usuario esté logueado"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        usuario = obtener_usuario_actual()
        if not usuario:
            return jsonify({"error": "Token no válido o sesión caducada. Haz login."}), 401
        request.usuario_actual = usuario  # Guardamos el usuario en la petición para usarlo después
        return f(*args, **kwargs)
    return decorated_function

def requiere_admin(f):
    """Decorador: exige que el usuario sea admin"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        usuario = obtener_usuario_actual()
        if not usuario:
            return jsonify({"error": "Token no válido o sesión caducada. Haz login."}), 401
        if usuario.rol != 'admin':
            return jsonify({"error": "Permiso denegado. Solo para administradores."}), 403
        request.usuario_actual = usuario
        return f(*args, **kwargs)
    return decorated_function


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

    if Usuario.query.count() == 0:
        admin = Usuario(email="admin@reservalocal.com", rol="admin")
        admin.set_password("Admin123.")

        cliente = Usuario(email="cliente@reservalocal.com", rol="cliente")
        cliente.set_password("Cliente123!")

        db.session.add(admin)
        db.session.add(cliente)

    db.session.commit()
    return jsonify({"status": "tablas creadas y datos de prueba insertados"})


# --- SESIÓN 2 (NUEVO): Ruta para resetear BD local fácilmente si hay errores de columnas ---
@app.route("/reset")
def reset():
    db.drop_all()
    db.create_all()
    return jsonify({"status": "Base de datos reiniciada. Ahora visita /setup"})


# ---------- SERVICIOS (Lectura pública, Escritura solo Admin) ----------

@app.route("/servicios")
def listar_servicios():
    return jsonify([s.to_dict() for s in Servicio.query.all()])

# --- SESIÓN 2 (NUEVO): CRUD de servicios protegido para Admin ---
@app.route("/servicios", methods=["POST"])
@requiere_admin
def crear_servicio():
    datos = request.get_json(silent=True) or {}
    nombre = datos.get("nombre")
    precio = datos.get("precio")
    if not nombre or precio is None:
        return jsonify({"error": "Faltan campos: nombre, precio"}), 400
    
    servicio = Servicio(nombre=nombre, precio=precio)
    db.session.add(servicio)
    db.session.commit()
    return jsonify(servicio.to_dict()), 201

@app.route("/servicios/<int:id>", methods=["PUT"])
@requiere_admin
def editar_servicio(id):
    servicio = Servicio.query.get_or_404(id)
    datos = request.get_json(silent=True) or {}
    if "nombre" in datos:
        servicio.nombre = datos["nombre"]
    if "precio" in datos:
        servicio.precio = datos["precio"]
    db.session.commit()
    return jsonify(servicio.to_dict())

@app.route("/servicios/<int:id>", methods=["DELETE"])
@requiere_admin
def borrar_servicio(id):
    servicio = Servicio.query.get_or_404(id)
    db.session.delete(servicio)
    db.session.commit()
    return jsonify({"status": "servicio eliminado", "id": id})


# ---------- RESERVAS: CRUD protegido y filtrado ----------

@app.route("/reservas", methods=["GET"])
@requiere_login
def listar_reservas():
    usuario = request.usuario_actual
    if usuario.rol == 'admin':
        # El admin ve todas
        reservas = Reserva.query.all()
    else:
        # El cliente solo ve las suyas
        reservas = Reserva.query.filter_by(usuario_id=usuario.id).all()
    return jsonify([r.to_dict() for r in reservas])


@app.route("/reservas", methods=["POST"])
@requiere_login
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
        
    # --- SESIÓN 2 (NUEVO): guardamos el ID del usuario que crea la reserva ---
    reserva = Reserva(
        cliente=cliente, 
        servicio_id=servicio_id,
        fecha=fecha, 
        estado="pendiente",
        usuario_id=request.usuario_actual.id
    )
    db.session.add(reserva)
    db.session.commit()
    return jsonify(reserva.to_dict()), 201


@app.route("/reservas/<int:id>", methods=["PUT"])
@requiere_login
def editar_reserva(id):
    reserva = Reserva.query.get_or_404(id)
    usuario = request.usuario_actual
    
    # --- SESIÓN 2 (NUEVO): Un cliente no puede editar reservas de otros ---
    if usuario.rol != 'admin' and reserva.usuario_id != usuario.id:
        return jsonify({"error": "No puedes modificar reservas de otros usuarios"}), 403

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
@requiere_login
def borrar_reserva(id):
    reserva = Reserva.query.get_or_404(id)
    usuario = request.usuario_actual
    
    # --- SESIÓN 2 (NUEVO): Un cliente no puede borrar reservas de otros ---
    if usuario.rol != 'admin' and reserva.usuario_id != usuario.id:
        return jsonify({"error": "No puedes eliminar reservas de otros usuarios"}), 403

    db.session.delete(reserva)
    db.session.commit()
    return jsonify({"status": "reserva eliminada", "id": id})


# ---------- AUTH (Login / Logout) ----------

@app.route("/login", methods=["POST"])
def login():
    datos = request.get_json(silent=True) or {}
    email = datos.get("email", "").strip().lower()
    password = datos.get("password", "")

    usuario = Usuario.query.filter_by(email=email).first()

    if not usuario or not usuario.check_password(password):
        return jsonify({"error": "Email o contraseña incorrectos"}), 401

    token = usuario.generar_token()
    db.session.commit()

    return jsonify({
        "mensaje": "Login correcto",
        "token": token,
        "usuario": usuario.to_dict(),
    }), 200


@app.route("/logout", methods=["POST"])
def logout():
    datos = request.get_json(silent=True) or {}
    token = datos.get("token", "")

    usuario = Usuario.query.filter_by(token=token).first()
    if usuario:
        usuario.token = None
        db.session.commit()

    return jsonify({"mensaje": "Sesión cerrada"}), 200


if __name__ == "__main__":
    app.run(debug=True)