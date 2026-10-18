import os
import certifi
import secrets
import calendar                      # --- NUEVO: para calcular el último día del mes ---
from datetime import datetime
from urllib.parse import quote_plus
from dotenv import load_dotenv
from flask import Flask, jsonify, request, send_from_directory
from flask_cors import CORS
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
from functools import wraps

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
app.config["MAX_CONTENT_LENGTH"] = 5 * 1024 * 1024
db = SQLAlchemy(app)

CODIGO_MAESTRO = "1234"

UPLOAD_FOLDER = os.path.join(os.path.dirname(os.path.abspath(__file__)), "uploads")
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
EXTENSIONES_PERMITIDAS = {"png", "jpg", "jpeg", "gif", "webp"}

DIAS_SEMANA = ["lunes", "martes", "miercoles", "jueves", "viernes", "sabado", "domingo"]

PLAN_HORARIO_JON = {
    0: (True, "09:00", "20:00", 30),
    1: (True, "09:00", "20:00", 30),
    2: (True, "09:00", "20:00", 30),
    3: (True, "09:00", "20:00", 30),
    4: (True, "09:00", "21:00", 30),
    5: (True, "10:00", "14:00", 30),
    6: (False, "09:00", "20:00", 30),
}

PLAN_HORARIO_CENTRAL = {
    0: (False, "10:00", "14:00", 60),
    1: (True, "10:00", "14:00", 60),
    2: (True, "10:00", "14:00", 60),
    3: (True, "10:00", "14:00", 60),
    4: (True, "10:00", "14:00", 60),
    5: (True, "11:00", "15:00", 60),
    6: (False, "10:00", "14:00", 60),
}


# ---------- MODELOS ----------

class Usuario(db.Model):
    __tablename__ = "usuarios"

    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(120), unique=True, nullable=False)
    nombre = db.Column(db.String(60), nullable=False, default="")
    apellidos = db.Column(db.String(120), nullable=False, default="")
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

    def nombre_completo(self):
        completo = f"{self.nombre or ''} {self.apellidos or ''}".strip()
        return completo or self.email

    def to_dict(self):
        return {
            "id": self.id,
            "email": self.email,
            "nombre": self.nombre,
            "apellidos": self.apellidos,
            "rol": self.rol,
        }


class Negocio(db.Model):
    __tablename__ = "negocios"

    id = db.Column(db.Integer, primary_key=True)
    nombre = db.Column(db.String(120), nullable=False)
    usuario_id = db.Column(db.Integer, db.ForeignKey("usuarios.id"), nullable=False)
    icono_url = db.Column(db.String(300), nullable=True)

    def to_dict(self):
        return {
            "id": self.id,
            "nombre": self.nombre,
            "usuario_id": self.usuario_id,
            "icono_url": self.icono_url,
        }


class Servicio(db.Model):
    __tablename__ = "servicios"
    id = db.Column(db.Integer, primary_key=True)
    nombre = db.Column(db.String(100), nullable=False)
    precio = db.Column(db.Float, nullable=False)
    negocio_id = db.Column(db.Integer, db.ForeignKey("negocios.id"), nullable=False)

    def to_dict(self):
        return {"id": self.id, "nombre": self.nombre, "precio": self.precio, "negocio_id": self.negocio_id}


class Reserva(db.Model):
    __tablename__ = "reservas"
    id = db.Column(db.Integer, primary_key=True)
    cliente = db.Column(db.String(100), nullable=False)
    servicio_id = db.Column(db.Integer, db.ForeignKey("servicios.id"), nullable=False)
    fecha = db.Column(db.String(40), nullable=False)
    estado = db.Column(db.String(20), default="pendiente")
    usuario_id = db.Column(db.Integer, db.ForeignKey("usuarios.id"), nullable=True)
    negocio_id = db.Column(db.Integer, db.ForeignKey("negocios.id"), nullable=False)

    def to_dict(self):
        return {
            "id": self.id,
            "cliente": self.cliente,
            "servicio_id": self.servicio_id,
            "fecha": self.fecha,
            "estado": self.estado,
            "usuario_id": self.usuario_id,
            "negocio_id": self.negocio_id,
        }


class HorarioDia(db.Model):
    __tablename__ = "horarios_dia"

    id = db.Column(db.Integer, primary_key=True)
    negocio_id = db.Column(db.Integer, db.ForeignKey("negocios.id"), nullable=False)
    dia = db.Column(db.Integer, nullable=False)
    abierto = db.Column(db.Boolean, nullable=False, default=False)
    hora_apertura = db.Column(db.String(5), nullable=False, default="09:00")
    hora_cierre = db.Column(db.String(5), nullable=False, default="20:00")
    intervalo_minutos = db.Column(db.Integer, nullable=False, default=30)

    def to_dict(self):
        return {
            "id": self.id,
            "negocio_id": self.negocio_id,
            "dia": self.dia,
            "nombre_dia": DIAS_SEMANA[self.dia],
            "abierto": self.abierto,
            "hora_apertura": self.hora_apertura,
            "hora_cierre": self.hora_cierre,
            "intervalo_minutos": self.intervalo_minutos,
        }


class CodigoInvitacion(db.Model):
    __tablename__ = "codigos_invitacion"
    id = db.Column(db.Integer, primary_key=True)
    codigo = db.Column(db.String(64), unique=True, nullable=False)
    usado = db.Column(db.Boolean, default=False)

    def to_dict(self):
        return {"id": self.id, "codigo": self.codigo, "usado": self.usado}


# ---------- HELPERS DE SEGURIDAD ----------

def obtener_usuario_actual():
    auth_header = request.headers.get('Authorization')
    if not auth_header or not auth_header.startswith('Bearer '):
        return None
    token = auth_header.split(' ')[1]
    return Usuario.query.filter_by(token=token).first()

def requiere_login(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        usuario = obtener_usuario_actual()
        if not usuario:
            return jsonify({"error": "Token no válido o sesión caducada. Haz login."}), 401
        request.usuario_actual = usuario
        return f(*args, **kwargs)
    return decorated_function

def requiere_admin(f):
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

def negocios_del_admin(usuario):
    return Negocio.query.filter_by(usuario_id=usuario.id).all()

def admin_es_dueno(usuario, negocio_id):
    return Negocio.query.filter_by(id=negocio_id, usuario_id=usuario.id).first() is not None


# ---------- HELPERS DE HORARIOS SEMANALES Y PASADO ----------

def _hhmm_a_minutos(hhmm):
    partes = hhmm.split(":")
    return int(partes[0]) * 60 + int(partes[1])

def _minutos_a_hhmm(minutos):
    return f"{minutos // 60:02d}:{minutos % 60:02d}"

def generar_slots(config):
    inicio = _hhmm_a_minutos(config.hora_apertura)
    fin = _hhmm_a_minutos(config.hora_cierre)
    slots = []
    t = inicio
    while t < fin:
        slots.append(_minutos_a_hhmm(t))
        t += config.intervalo_minutos
    return slots

def hoy_str():
    return datetime.now().strftime("%Y-%m-%d")

def hora_actual_hhmm():
    return datetime.now().strftime("%H:%M")

def es_pasado(fecha_dia, hora):
    try:
        momento = datetime.strptime(fecha_dia + " " + hora, "%Y-%m-%d %H:%M")
    except ValueError:
        return True
    return momento < datetime.now()

def config_dia(negocio_id, fecha_dia):
    try:
        fecha = datetime.strptime(fecha_dia, "%Y-%m-%d")
    except ValueError:
        return None
    return HorarioDia.query.filter_by(negocio_id=negocio_id, dia=fecha.weekday()).first()

def asegurar_horario_semanal(negocio_id):
    for d in range(7):
        existe = HorarioDia.query.filter_by(negocio_id=negocio_id, dia=d).first()
        if not existe:
            db.session.add(HorarioDia(
                negocio_id=negocio_id,
                dia=d,
                abierto=d < 5,
                hora_apertura="09:00",
                hora_cierre="20:00",
                intervalo_minutos=30,
            ))
    db.session.commit()

def fijar_horario_semanal(negocio_id, plan):
    HorarioDia.query.filter_by(negocio_id=negocio_id).delete()
    for d in range(7):
        abierto, apertura, cierre, intervalo = plan[d]
        db.session.add(HorarioDia(
            negocio_id=negocio_id,
            dia=d,
            abierto=abierto,
            hora_apertura=apertura,
            hora_cierre=cierre,
            intervalo_minutos=intervalo,
        ))
    db.session.commit()

def slots_ocupados(fecha_dia, negocio_id, excluir_id=None):
    ocupados = set()
    reservas = Reserva.query.filter(
        Reserva.fecha.startswith(fecha_dia),
        Reserva.negocio_id == negocio_id
    ).all()
    for r in reservas:
        if r.id == excluir_id:
            continue
        if r.estado in ("pendiente", "confirmada"):
            partes = r.fecha.split(" ")
            if len(partes) == 2:
                ocupados.add(partes[1])
    return ocupados


def asegurar_servicio(negocio_id, nombre, precio):
    existe = Servicio.query.filter_by(nombre=nombre, negocio_id=negocio_id).first()
    if not existe:
        db.session.add(Servicio(nombre=nombre, precio=precio, negocio_id=negocio_id))


# ---------- ESTADO, SETUP Y RESET DEFINITIVO (MySQL Y SQLite) ----------

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

    if Usuario.query.count() == 0:
        admin = Usuario(email="admin@reservalocal.com", nombre="Jon", apellidos="Mena", rol="admin")
        admin.set_password("Admin123.")
        admin2 = Usuario(email="admin2@reservalocal.com", nombre="Ana", apellidos="Central", rol="admin")
        admin2.set_password("Admin123.")
        cliente = Usuario(email="cliente@reservalocal.com", nombre="Cliente", apellidos="Demo", rol="cliente")
        cliente.set_password("Cliente123!")
        db.session.add_all([admin, admin2, cliente])
        db.session.commit()

    if Negocio.query.count() == 0:
        admin = Usuario.query.filter_by(email="admin@reservalocal.com").first()
        admin2 = Usuario.query.filter_by(email="admin2@reservalocal.com").first()
        db.session.add_all([
            Negocio(nombre="Peluquería Jon", usuario_id=admin.id),
            Negocio(nombre="Barbería Central", usuario_id=admin2.id),
        ])
        db.session.commit()

    n1 = Negocio.query.filter_by(nombre="Peluquería Jon").first()
    n2 = Negocio.query.filter_by(nombre="Barbería Central").first()

    if n1:
        asegurar_servicio(n1.id, "Corte de pelo", 15)
        asegurar_servicio(n1.id, "Arreglo de barba", 10)
    if n2:
        asegurar_servicio(n2.id, "Corte clásico", 12)
        asegurar_servicio(n2.id, "Afeitado tradicional", 8)

    if n1:
        fijar_horario_semanal(n1.id, PLAN_HORARIO_JON)
    if n2:
        fijar_horario_semanal(n2.id, PLAN_HORARIO_CENTRAL)

    db.session.commit()
    return jsonify({"status": "tablas creadas y datos de prueba insertados"})


@app.route("/reset")
def reset():
    db.drop_all()
    db.create_all()
    return jsonify({"status": "Base de datos reiniciada. Ahora visita /setup"})


@app.route("/reset-forzado")
def reset_forzado():
    """
    Borra las tablas en orden hijas -> madres. Funciona en MySQL Y en SQLite
    (sin necesidad de SET FOREIGN_KEY_CHECKS, que SQLite no entiende).
    """
    tablas_en_orden = [
        "fotos",
        "horarios_dia",
        "reservas",
        "servicios",
        "horarios",
        "codigos_invitacion",
        "negocios",
        "usuarios",
    ]
    for tabla in tablas_en_orden:
        try:
            db.session.execute(db.text(f"DROP TABLE IF EXISTS {tabla}"))
            db.session.commit()
        except Exception:
            db.session.rollback()

    db.create_all()
    return jsonify({"status": "Base de datos reiniciada (forzado). Ahora visita /setup"})


# ---------- ICONO SUBIDO (servir archivo) ----------

@app.route("/uploads/<path:filename>")
def servir_upload(filename):
    return send_from_directory(UPLOAD_FOLDER, filename)


# ---------- NEGOCIOS ----------

@app.route("/negocios", methods=["GET"])
def listar_negocios():
    return jsonify([n.to_dict() for n in Negocio.query.all()])


@app.route("/negocios/mios", methods=["GET"])
@requiere_admin
def mis_negocios():
    return jsonify([n.to_dict() for n in negocios_del_admin(request.usuario_actual)])


@app.route("/negocios/<int:id>", methods=["PUT"])
@requiere_admin
def editar_negocio(id):
    if not admin_es_dueno(request.usuario_actual, id):
        return jsonify({"error": "No eres el dueno de este negocio"}), 403
    negocio = Negocio.query.get_or_404(id)
    datos = request.get_json(silent=True) or {}
    if "nombre" in datos and datos["nombre"].strip():
        negocio.nombre = datos["nombre"].strip()
    db.session.commit()
    return jsonify(negocio.to_dict())


# ---------- ICONO ÚNICO DEL NEGOCIO ----------

@app.route("/negocios/<int:id>/foto", methods=["POST"])
@requiere_admin
def subir_icono(id):
    if not admin_es_dueno(request.usuario_actual, id):
        return jsonify({"error": "No eres el dueno de este negocio"}), 403

    archivo = request.files.get("foto")
    if not archivo or not archivo.filename:
        return jsonify({"error": "No se ha enviado ninguna imagen"}), 400

    extension = archivo.filename.rsplit(".", 1)[-1].lower() if "." in archivo.filename else ""
    if extension not in EXTENSIONES_PERMITIDAS:
        return jsonify({"error": "Formato no permitido. Usa: png, jpg, jpeg, gif o webp"}), 400

    negocio = Negocio.query.get_or_404(id)

    if negocio.icono_url:
        viejo = negocio.icono_url.split("/")[-1]
        ruta_vieja = os.path.join(UPLOAD_FOLDER, viejo)
        if os.path.exists(ruta_vieja):
            os.remove(ruta_vieja)

    nombre_guardado = secrets.token_hex(10) + "." + extension
    archivo.save(os.path.join(UPLOAD_FOLDER, nombre_guardado))
    negocio.icono_url = "/uploads/" + nombre_guardado

    db.session.commit()
    return jsonify(negocio.to_dict())


@app.route("/negocios/<int:id>/foto", methods=["DELETE"])
@requiere_admin
def quitar_icono(id):
    if not admin_es_dueno(request.usuario_actual, id):
        return jsonify({"error": "No eres el dueno de este negocio"}), 403

    negocio = Negocio.query.get_or_404(id)
    if negocio.icono_url:
        viejo = negocio.icono_url.split("/")[-1]
        ruta_vieja = os.path.join(UPLOAD_FOLDER, viejo)
        if os.path.exists(ruta_vieja):
            os.remove(ruta_vieja)
    negocio.icono_url = None

    db.session.commit()
    return jsonify(negocio.to_dict())


# ---------- HORARIOS SEMANALES ----------

@app.route("/horario", methods=["GET"])
def ver_horario():
    negocio_id = request.args.get("negocio_id", type=int)
    if not negocio_id:
        return jsonify({"error": "Falta el parametro negocio_id"}), 400
    asegurar_horario_semanal(negocio_id)
    filas = HorarioDia.query.filter_by(negocio_id=negocio_id).order_by(HorarioDia.dia).all()
    return jsonify([f.to_dict() for f in filas])


@app.route("/horario", methods=["PUT"])
@requiere_admin
def editar_horario():
    datos = request.get_json(silent=True) or {}
    negocio_id = datos.get("negocio_id")
    dias = datos.get("dias")

    if not negocio_id:
        mios = negocios_del_admin(request.usuario_actual)
        if not mios:
            return jsonify({"error": "No tienes negocios"}), 404
        negocio_id = mios[0].id
    elif not admin_es_dueno(request.usuario_actual, negocio_id):
        return jsonify({"error": "No eres el dueno de este negocio"}), 403

    if not dias or not isinstance(dias, list):
        return jsonify({"error": "Falta la lista de dias"}), 400

    asegurar_horario_semanal(negocio_id)

    for item in dias:
        d = item.get("dia")
        if d is None or d < 0 or d > 6:
            continue
        fila = HorarioDia.query.filter_by(negocio_id=negocio_id, dia=d).first()
        if not fila:
            fila = HorarioDia(negocio_id=negocio_id, dia=d)
            db.session.add(fila)
        if "abierto" in item:
            fila.abierto = bool(item["abierto"])
        if "hora_apertura" in item:
            fila.hora_apertura = item["hora_apertura"]
        if "hora_cierre" in item:
            fila.hora_cierre = item["hora_cierre"]
        if "intervalo_minutos" in item:
            intervalo = int(item["intervalo_minutos"])
            if intervalo < 5 or intervalo > 240:
                return jsonify({"error": "El intervalo debe estar entre 5 y 240 minutos"}), 400
            fila.intervalo_minutos = intervalo

    db.session.commit()
    filas = HorarioDia.query.filter_by(negocio_id=negocio_id).order_by(HorarioDia.dia).all()
    return jsonify([f.to_dict() for f in filas])


@app.route("/horarios/disponibles", methods=["GET"])
@requiere_login
def horarios_disponibles():
    fecha_dia = request.args.get("fecha", "")
    negocio_id = request.args.get("negocio_id", type=int)
    if not fecha_dia or not negocio_id:
        return jsonify({"error": "Faltan los parametros fecha y negocio_id"}), 400

    if fecha_dia < hoy_str():
        return jsonify({"fecha": fecha_dia, "slots": [], "ocupados": [], "cerrado": False, "pasado": True})

    config = config_dia(negocio_id, fecha_dia)
    if not config or not config.abierto:
        return jsonify({"fecha": fecha_dia, "slots": [], "ocupados": [], "cerrado": True, "pasado": False})

    todos = generar_slots(config)
    ocupados = slots_ocupados(fecha_dia, negocio_id)
    libres = [s for s in todos if s not in ocupados]

    if fecha_dia == hoy_str():
        ahora = hora_actual_hhmm()
        libres = [s for s in libres if s > ahora]

    return jsonify({"fecha": fecha_dia, "slots": libres, "ocupados": sorted(ocupados), "cerrado": False, "pasado": False})


# ---------- SERVICIOS ----------

@app.route("/servicios", methods=["GET"])
def listar_servicios():
    negocio_id = request.args.get("negocio_id", type=int)
    if not negocio_id:
        return jsonify({"error": "Falta el parametro negocio_id"}), 400
    return jsonify([s.to_dict() for s in Servicio.query.filter_by(negocio_id=negocio_id).all()])

@app.route("/servicios", methods=["POST"])
@requiere_admin
def crear_servicio():
    datos = request.get_json(silent=True) or {}
    nombre = datos.get("nombre")
    precio = datos.get("precio")
    if not nombre or precio is None:
        return jsonify({"error": "Faltan campos: nombre, precio"}), 400

    negocio_id = datos.get("negocio_id")
    if not negocio_id:
        mios = negocios_del_admin(request.usuario_actual)
        if not mios:
            return jsonify({"error": "No tienes negocios"}), 404
        negocio_id = mios[0].id
    elif not admin_es_dueno(request.usuario_actual, negocio_id):
        return jsonify({"error": "No eres el dueno de este negocio"}), 403

    servicio = Servicio(nombre=nombre, precio=precio, negocio_id=negocio_id)
    db.session.add(servicio)
    db.session.commit()
    return jsonify(servicio.to_dict()), 201

@app.route("/servicios/<int:id>", methods=["PUT"])
@requiere_admin
def editar_servicio(id):
    servicio = Servicio.query.get_or_404(id)
    if not admin_es_dueno(request.usuario_actual, servicio.negocio_id):
        return jsonify({"error": "No eres el dueno de este negocio"}), 403
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
    if not admin_es_dueno(request.usuario_actual, servicio.negocio_id):
        return jsonify({"error": "No eres el dueno de este negocio"}), 403
    db.session.delete(servicio)
    db.session.commit()
    return jsonify({"status": "servicio eliminado", "id": id})


# ---------- RESERVAS ----------

@app.route("/reservas", methods=["GET"])
@requiere_login
def listar_reservas():
    usuario = request.usuario_actual
    negocio_id = request.args.get("negocio_id", type=int)

    if usuario.rol == 'admin':
        mios = [n.id for n in negocios_del_admin(usuario)]
        consulta = Reserva.query.filter(Reserva.negocio_id.in_(mios))
    else:
        consulta = Reserva.query.filter_by(usuario_id=usuario.id)

    if negocio_id:
        consulta = consulta.filter_by(negocio_id=negocio_id)

    return jsonify([r.to_dict() for r in consulta.all()])


def validar_fecha_de_reserva(fecha, negocio_id, excluir_id=None):
    partes = fecha.split(" ")
    if len(partes) != 2:
        return "Formato de fecha invalido. Usa: YYYY-MM-DD HH:MM", 400
    dia, hora = partes

    if es_pasado(dia, hora):
        return "No se pueden hacer reservas en el pasado. Elige una fecha y hora futuras.", 400

    # --- Tope de 1 mes natural de antelación ---
    try:
        dia_dt = datetime.strptime(dia, "%Y-%m-%d")
    except ValueError:
        return "Formato de fecha invalido. Usa: YYYY-MM-DD HH:MM", 400

    hoy = datetime.now()
    mes_sig = hoy.month + 1
    anio_sig = hoy.year + (1 if mes_sig > 12 else 0)
    mes_sig_norm = mes_sig if mes_sig <= 12 else 1
    ultimo_dia_mes_sig = calendar.monthrange(anio_sig, mes_sig_norm)[1]
    dia_limite = min(hoy.day, ultimo_dia_mes_sig)
    limite = datetime(anio_sig, mes_sig_norm, dia_limite, 23, 59, 59)

    if dia_dt > limite:
        return "No se pueden reservar citas con mas de un mes de antelacion.", 400

    config = config_dia(negocio_id, dia)
    if not config or not config.abierto:
        return "El negocio esta cerrado ese dia. Elige otro dia.", 400

    if hora not in generar_slots(config):
        return f"Hora fuera del horario del dia ({config.hora_apertura}-{config.hora_cierre}, cada {config.intervalo_minutos} min)", 400

    if hora in slots_ocupados(dia, negocio_id, excluir_id=excluir_id):
        return "Esa hora ya esta reservada. Elige otra.", 409

    return None, None


@app.route("/reservas", methods=["POST"])
@requiere_login
def crear_reserva():
    datos = request.get_json(silent=True) or {}
    servicio_id = datos.get("servicio_id")
    fecha = datos.get("fecha")
    negocio_id = datos.get("negocio_id")

    if not servicio_id or not fecha or not negocio_id:
        return jsonify({"error": "Faltan campos: servicio_id, fecha, negocio_id"}), 400

    negocio = Negocio.query.get(negocio_id)
    if negocio is None:
        return jsonify({"error": "El negocio indicado no existe"}), 404

    servicio = Servicio.query.get(servicio_id)
    if servicio is None or servicio.negocio_id != negocio_id:
        return jsonify({"error": "El servicio no pertenece a este negocio"}), 404

    # --- NUEVO: un cliente no puede tener dos reservas ACTIVAS del mismo servicio en el mismo negocio ---
    duplicada = (
        Reserva.query.filter_by(
            usuario_id=request.usuario_actual.id,
            servicio_id=servicio_id,
            negocio_id=negocio_id,
        )
        .filter(Reserva.estado.in_(["pendiente", "confirmada"]))
        .first()
    )
    if duplicada:
        return jsonify({
            "error": "Ya tienes una reserva activa de este servicio en este negocio. Cancelala antes de pedir otra."
        }), 409

    error, codigo = validar_fecha_de_reserva(fecha, negocio_id)
    if error:
        return jsonify({"error": error}), codigo

    reserva = Reserva(
        cliente=request.usuario_actual.nombre_completo(),
        servicio_id=servicio_id,
        fecha=fecha,
        estado="pendiente",
        usuario_id=request.usuario_actual.id,
        negocio_id=negocio_id,
    )
    db.session.add(reserva)
    db.session.commit()
    return jsonify(reserva.to_dict()), 201


@app.route("/reservas/<int:id>", methods=["PUT"])
@requiere_login
def editar_reserva(id):
    reserva = Reserva.query.get_or_404(id)
    usuario = request.usuario_actual

    if usuario.rol == 'admin':
        if not admin_es_dueno(usuario, reserva.negocio_id):
            return jsonify({"error": "No puedes modificar reservas de otros negocios"}), 403
    elif reserva.usuario_id != usuario.id:
        return jsonify({"error": "No puedes modificar reservas de otros usuarios"}), 403

    datos = request.get_json(silent=True) or {}

    # El admin SOLO gestiona el estado, NUNCA la fecha
    if usuario.rol == 'admin' and "fecha" in datos:
        return jsonify({"error": "Los administradores no pueden modificar la fecha de una reserva. Solo confirmar o cancelar."}), 403

    if "fecha" in datos:
        error, codigo = validar_fecha_de_reserva(datos["fecha"], reserva.negocio_id, excluir_id=reserva.id)
        if error:
            return jsonify({"error": error}), codigo
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

    if usuario.rol == 'admin':
        if not admin_es_dueno(usuario, reserva.negocio_id):
            return jsonify({"error": "No puedes eliminar reservas de otros negocios"}), 403
    elif reserva.usuario_id != usuario.id:
        return jsonify({"error": "No puedes eliminar reservas de otros usuarios"}), 403

    db.session.delete(reserva)
    db.session.commit()
    return jsonify({"status": "reserva eliminada", "id": id})


# ---------- AUTH: LOGIN / LOGOUT ----------

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


# ---------- REGISTRO Y CÓDIGOS DE INVITACIÓN ----------

@app.route("/registro", methods=["POST"])
def registro():
    datos = request.get_json(silent=True) or {}
    email = datos.get("email", "").strip().lower()
    password = datos.get("password", "")
    nombre = datos.get("nombre", "").strip()
    apellidos = datos.get("apellidos", "").strip()
    codigo = datos.get("codigo_invitacion", "").strip()
    nombre_negocio = datos.get("nombre_negocio", "").strip()

    if not email or "@" not in email:
        return jsonify({"error": "Introduce un email valido"}), 400
    if len(password) < 6:
        return jsonify({"error": "La contrasena debe tener al menos 6 caracteres"}), 400
    if not nombre or not apellidos:
        return jsonify({"error": "El nombre y los apellidos son obligatorios"}), 400
    if Usuario.query.filter_by(email=email).first():
        return jsonify({"error": "Ese email ya esta registrado"}), 409

    es_admin = False
    if codigo:
        if codigo == CODIGO_MAESTRO:
            es_admin = True
        else:
            invitacion = CodigoInvitacion.query.filter_by(codigo=codigo, usado=False).first()
            if not invitacion:
                return jsonify({"error": "Codigo de invitacion invalido o ya usado"}), 400
            invitacion.usado = True
            es_admin = True

    if es_admin and not nombre_negocio:
        return jsonify({"error": "Los administradores deben indicar el nombre de su negocio"}), 400

    usuario = Usuario(
        email=email,
        nombre=nombre,
        apellidos=apellidos,
        rol="admin" if es_admin else "cliente",
    )
    usuario.set_password(password)
    token = usuario.generar_token()
    db.session.add(usuario)
    db.session.commit()

    negocio = None
    if es_admin:
        negocio = Negocio(nombre=nombre_negocio, usuario_id=usuario.id)
        db.session.add(negocio)
        db.session.commit()
        asegurar_horario_semanal(negocio.id)

    return jsonify({
        "mensaje": "Cuenta creada correctamente",
        "token": token,
        "usuario": usuario.to_dict(),
        "negocio": negocio.to_dict() if negocio else None,
    }), 201


@app.route("/codigos", methods=["POST"])
@requiere_admin
def crear_codigo():
    codigo = CodigoInvitacion(codigo=secrets.token_hex(6).upper())
    db.session.add(codigo)
    db.session.commit()
    return jsonify(codigo.to_dict()), 201


@app.route("/codigos", methods=["GET"])
@requiere_admin
def listar_codigos():
    return jsonify([c.to_dict() for c in CodigoInvitacion.query.all()])


if __name__ == "__main__":
    app.run(debug=True)