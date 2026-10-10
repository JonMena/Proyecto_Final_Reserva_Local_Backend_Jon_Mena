# ReservaLocal API

API RESTful para ReservaLocal, un sistema de reservas genérico y adaptable a
cualquier negocio local (peluquerías, clínicas, talleres, restaurantes...).
Cada negocio define sus propios servicios y los clientes los reservan.
La instancia desplegada incluye los servicios de una peluquería como
configuración de ejemplo.

## Tecnologías

- Python 3.10
- Flask + Flask-Cors
- Flask-SQLAlchemy (ORM)
- PyMySQL (driver compatible con MySQL)
- SQLite (producción) y TiDB Cloud compatible con MySQL (desarrollo)
- python-dotenv y certifi

## Endpoints de la API

| Método | Ruta             | Descripción                                                |
|--------|------------------|----------------------------------------------------------  |
| GET    | /                | Estado de la API                                           |
| GET    | /setup           | Crea las tablas y carga servicios de ejemplo               |
| GET    | /servicios       | Lista todos los servicios                                  |
| GET    | /reservas        | Lista todas las reservas                                   |
| POST   | /reservas        | Crea una reserva (cliente, servicio_id, fecha)       |
| PUT    | /reservas/<id>   | Actualiza una reserva (cliente, fecha, estado)             |
| DELETE | /reservas/<id>   | Elimina una reserva                                        |

## Cómo ejecutarlo en local

1. Clona este repositorio.
2. Crea y activa un entorno virtual: `python -m venv venv`.
3. Instala las dependencias: `pip install -r requirements.txt`.
4. Crea un archivo `.env` (nunca se sube a GitHub) con tus credenciales:

   DB_USER=tu_usuario
   DB_PASSWORD=tu_password
   DB_HOST=tu_host
   DB_PORT=4000
   DB_NAME=tu_base_de_datos

   Como alternativa, define `DATABASE_URL=sqlite:///reservalocal.db`
   para usar un archivo SQLite local.

5. Arranca el servidor: `python app.py`.
6. Abre `http://localhost:5000/setup` una vez para crear las tablas
   y los datos de prueba; después usa `/servicios` y `/reservas`.

## Despliegue

Alojado en PythonAnywhere (plan gratuito) con configuración WSGI manual.
En producción se usa SQLite porque el plan gratuito bloquea los puertos
MySQL salientes; en desarrollo se usa un clúster de TiDB Cloud compatible
con MySQL. El mismo esquema y el mismo código funcionan en ambos entornos.


