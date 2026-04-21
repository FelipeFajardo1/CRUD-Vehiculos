import json

from flask import Flask, jsonify, request
from pymongo import MongoClient
import redis

app = Flask(__name__)

# MongoDB: base y colección solicitadas
mongo_client = MongoClient("mongodb://localhost:27017/")
db_mongo = mongo_client["vehiculos"]
vehiculos_col = db_mongo["vehiculo"]

# Redis: base de datos 2
cache = redis.Redis(
    host="localhost",
    port=6379,
    db=2,
    decode_responses=True,
)

FIELD_VEHICULO = "Vehiculo"
FIELD_CATEGORIA = "Categoria"
FIELD_PESO_TON = "Peso/Ton"
FIELD_DESCRIPCION = "Descripcion"


def cache_key(vehiculo: str) -> str:
    return f"vehiculo:{vehiculo.lower().strip()}"


def extraer_primero(data: dict, claves: list[str], default: str = "") -> str:
    for clave in claves:
        if clave in data and data[clave] is not None:
            return str(data[clave]).strip()
    return default


def filtro_por_vehiculo(nombre: str) -> dict:
    return {"$or": [{FIELD_VEHICULO: nombre}, {"vehiculo": nombre}]}


def normalizar_payload(data: dict, vehiculo_default: str | None = None) -> dict:
    salida = dict(data)
    salida.pop("_id", None)

    vehiculo = extraer_primero(salida, [FIELD_VEHICULO, "vehiculo"], vehiculo_default or "")
    if vehiculo:
        salida[FIELD_VEHICULO] = vehiculo

    descripcion = extraer_primero(salida, [FIELD_DESCRIPCION, "descripcion"], "")
    if descripcion:
        salida[FIELD_DESCRIPCION] = descripcion

    categoria = extraer_primero(salida, [FIELD_CATEGORIA, "categoria"], "")
    if categoria:
        salida[FIELD_CATEGORIA] = categoria

    if FIELD_PESO_TON not in salida and "PesoTon" in salida:
        salida[FIELD_PESO_TON] = salida["PesoTon"]

    salida.pop("vehiculo", None)
    salida.pop("descripcion", None)
    salida.pop("categoria", None)
    salida.pop("PesoTon", None)
    return salida


def ttl_por_longitud(vehiculo: str) -> int:
    longitud = len(vehiculo)
    if longitud <= 5:
        return 15
    if longitud <= 10:
        return 20
    return 40


def serializar_documento(doc: dict) -> dict:
    salida = dict(doc)
    salida.pop("_id", None)
    return salida


def regla_cache(vehiculo: str, descripcion: str) -> dict:
    if len(descripcion) > 20:
        return {
            "cacheable": False,
            "motivo": "descripcion_mayor_a_20",
            "ttl": 0,
        }

    ttl = ttl_por_longitud(vehiculo)
    return {
        "cacheable": True,
        "motivo": "ok",
        "ttl": ttl,
    }


@app.route("/vehiculos", methods=["POST"])
def crear_vehiculo():
    data = request.get_json(silent=True)
    if not data:
        return jsonify({"error": "Debes enviar JSON válido."}), 400

    data = normalizar_payload(data)
    vehiculo = extraer_primero(data, [FIELD_VEHICULO], "")
    if not vehiculo:
        return jsonify({"error": "El campo 'Vehiculo' es obligatorio."}), 400

    if vehiculos_col.find_one(filtro_por_vehiculo(vehiculo), {"_id": 0}):
        return jsonify({"error": "Ya existe un vehículo con ese nombre."}), 409

    vehiculos_col.insert_one(data)
    cache.delete(cache_key(vehiculo))

    return jsonify({"mensaje": "Vehículo creado", "datos": serializar_documento(data)}), 201


@app.route("/vehiculos", methods=["GET"])
def listar_vehiculos():
    docs = [serializar_documento(doc) for doc in vehiculos_col.find()]
    return jsonify({"total": len(docs), "datos": docs})


@app.route("/vehiculos/<vehiculo>", methods=["GET"])
def obtener_vehiculo(vehiculo):
    key = cache_key(vehiculo)
    cache_valor = cache.get(key)

    if cache_valor:
        ttl_restante = cache.ttl(key)
        return jsonify(
            {
                "origen": "redis",
                "datos": json.loads(cache_valor),
                "cache_info": {
                    "cache_aplicado": True,
                    "ttl_restante": ttl_restante,
                },
            }
        )

    doc = vehiculos_col.find_one(filtro_por_vehiculo(vehiculo))
    if not doc:
        return jsonify({"error": "Vehículo no encontrado"}), 404

    datos = serializar_documento(doc)
    nombre_guardado = extraer_primero(datos, [FIELD_VEHICULO, "vehiculo"], vehiculo)
    descripcion = extraer_primero(datos, [FIELD_DESCRIPCION, "descripcion"], "")
    evaluacion = regla_cache(nombre_guardado, descripcion)

    if evaluacion["cacheable"]:
        cache.set(key, json.dumps(datos), ex=evaluacion["ttl"])

    return jsonify(
        {
            "origen": "mongo",
            "datos": datos,
            "cache_info": {
                "cache_aplicado": evaluacion["cacheable"],
                "motivo": evaluacion["motivo"],
                "ttl_configurado": evaluacion["ttl"],
                "longitud_vehiculo": len(nombre_guardado),
                "longitud_descripcion": len(descripcion),
            },
        }
    )


@app.route("/vehiculos/<vehiculo>", methods=["PUT"])
def actualizar_vehiculo(vehiculo):
    data = request.get_json(silent=True)
    if not data:
        return jsonify({"error": "Debes enviar JSON válido."}), 400

    data = normalizar_payload(data, vehiculo_default=vehiculo)

    actual = vehiculos_col.find_one(filtro_por_vehiculo(vehiculo))
    if not actual:
        return jsonify({"error": "Vehículo no encontrado"}), 404

    nombre_actual = extraer_primero(actual, [FIELD_VEHICULO, "vehiculo"], vehiculo)
    nuevo_nombre = extraer_primero(data, [FIELD_VEHICULO], nombre_actual)
    if not nuevo_nombre:
        return jsonify({"error": "El campo 'Vehiculo' no puede estar vacío."}), 400

    if nuevo_nombre != nombre_actual and vehiculos_col.find_one(filtro_por_vehiculo(nuevo_nombre)):
        return jsonify({"error": "Ya existe otro vehículo con ese nombre."}), 409

    data[FIELD_VEHICULO] = nuevo_nombre
    vehiculos_col.update_one({"_id": actual["_id"]}, {"$set": data})

    cache.delete(cache_key(vehiculo))
    cache.delete(cache_key(nombre_actual))
    if nuevo_nombre != nombre_actual:
        cache.delete(cache_key(nuevo_nombre))

    actualizado = vehiculos_col.find_one({"_id": actual["_id"]}, {"_id": 0})
    return jsonify({"mensaje": "Vehículo actualizado", "datos": actualizado})


@app.route("/vehiculos/<vehiculo>", methods=["DELETE"])
def eliminar_vehiculo(vehiculo):
    eliminado = vehiculos_col.find_one_and_delete(filtro_por_vehiculo(vehiculo), {"_id": 0})
    if not eliminado:
        return jsonify({"error": "Vehículo no encontrado"}), 404

    nombre_eliminado = extraer_primero(eliminado, [FIELD_VEHICULO, "vehiculo"], vehiculo)
    cache.delete(cache_key(vehiculo))
    cache.delete(cache_key(nombre_eliminado))
    return jsonify({"mensaje": "Vehículo eliminado", "datos": eliminado})


@app.route("/vehiculos/cargar", methods=["POST"])
def cargar_vehiculos_masivo():
    data = request.get_json(silent=True)
    if not isinstance(data, list):
        return jsonify({"error": "Debes enviar una lista JSON de vehículos."}), 400

    insertables = []
    existentes = []
    for item in data:
        if not isinstance(item, dict):
            continue

        item = normalizar_payload(item)
        vehiculo = extraer_primero(item, [FIELD_VEHICULO], "")
        if not vehiculo:
            continue

        if vehiculos_col.find_one(filtro_por_vehiculo(vehiculo), {"_id": 1}):
            existentes.append(vehiculo)
            continue

        insertables.append(item)

    if insertables:
        vehiculos_col.insert_many(insertables)

    return jsonify(
        {
            "insertados": len(insertables),
            "omitidos_existentes": existentes,
        }
    )


if __name__ == "__main__":
    app.run(debug=True)
