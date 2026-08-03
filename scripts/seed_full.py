#!/usr/bin/env python3
"""Carga un catálogo demostrativo en Multi-Hub. Requiere API_KEY/HMAC_SECRET si el API los usa."""
import hashlib
import hmac
import json
import os
import time
from datetime import date, timedelta

import httpx

API_URL = os.getenv("API_URL", "http://localhost:8080/api/v1").rstrip("/")
DELAY = 2
API_KEY = os.getenv("API_KEY", "")
HMAC_SECRET = os.getenv("HMAC_SECRET", "")

CATEGORIES = [("Hoteles", "hoteles", "🏨"), ("Restaurantes", "restaurantes", "🍽️"),
              ("Tours y Aventura", "tours-y-aventura", "🥾"), ("Spa y Bienestar", "spa-y-bienestar", "🧘"),
              ("Transporte", "transporte", "🚐"), ("Eventos", "eventos", "🎟️")]

def product(name, slug, category, price, kind, description, **metadata):
    return {"name": name, "slug": slug, "category": category, "base_price": price,
            "currency": "USD", "product_type": kind, "description": description,
            "description_short": description[:115], "status": "active",
            "images": [f"https://images.unsplash.com/photo-{metadata.pop('image')}?auto=format&fit=crop&w=1200"],
            "metadata": metadata}

PRODUCTS = [
 product("Hotel Brisa Marina", "hotel-brisa-marina", "hoteles", 165, "hotel", "Hotel frente al mar con desayuno incluido, piscina infinita y acceso directo a la playa.", image="1507525428034-b723cf961d3e", amenities=["piscina", "desayuno", "wifi"], check_in="15:00"),
 product("Cabaña Bosque Nublado", "cabana-bosque-nublado", "hoteles", 110, "hotel", "Cabaña privada entre senderos y niebla, ideal para descansar lejos de la ciudad.", image="1449157291145-7efd050a4d0e", amenities=["chimenea", "terraza", "parking"], capacity=4),
 product("Boutique Centro Histórico", "boutique-centro-historico", "hoteles", 128, "hotel", "Habitación boutique a pasos de museos, cafés y la vida cultural del centro.", image="1566073771259-6a8506099945", amenities=["wifi", "aire acondicionado", "recepción 24h"], capacity=2),
 product("Eco Lodge Río Claro", "eco-lodge-rio-claro", "hoteles", 145, "hotel", "Alojamiento sostenible junto al río con observación de aves y cocina local.", image="1500534623283-312aade485b7", amenities=["desayuno", "senderos", "kayak"], capacity=3),
 product("Casa del Valle", "casa-del-valle", "hoteles", 95, "hotel", "Posada familiar rodeada de viñedos, con habitaciones tranquilas y jardín.", image="1542314831-068cd1dbfeeb", amenities=["jardín", "desayuno", "bicicletas"], capacity=2),
 product("Cena Sabores del Pacífico", "cena-sabores-pacifico", "restaurantes", 58, "restaurant", "Menú de cinco tiempos inspirado en pescados frescos, cacao y frutas tropicales.", image="1414235077428-338989a2e8c0", cuisine="fusión costera", schedule="19:00-22:30"),
 product("Parrilla La Estancia", "parrilla-la-estancia", "restaurantes", 42, "restaurant", "Cortes a la brasa, verduras de estación y selección de vinos regionales.", image="1515003197210-e0cd71810b5f", cuisine="parrilla", schedule="12:00-23:00"),
 product("Brunch Jardín Urbano", "brunch-jardin-urbano", "restaurantes", 28, "restaurant", "Brunch de masa madre, café de especialidad y opciones vegetarianas en un jardín luminoso.", image="1495474472287-4d71bcdd2085", cuisine="cafetería", schedule="08:00-16:00"),
 product("Mesa del Chef Andino", "mesa-del-chef-andino", "restaurantes", 76, "restaurant", "Experiencia íntima de cocina andina contemporánea con maridaje opcional.", image="1517248135467-4c7edcad34c4", cuisine="andina", schedule="20:00"),
 product("Taller de Pasta Artesanal", "taller-pasta-artesanal", "restaurantes", 48, "restaurant", "Aprende a preparar pasta fresca y comparte la cena con el grupo al final del taller.", image="1473093295043-cdd812d0e601", cuisine="italiana", duration="3 horas"),
 product("Caminata al Volcán", "caminata-al-volcan", "tours-y-aventura", 89, "tour", "Ascenso guiado de día completo con vistas panorámicas, refrigerio y equipo básico.", image="1464822759023-fed622ff2c3b", duration="8 horas", difficulty="media"),
 product("Rafting Río Esmeralda", "rafting-rio-esmeralda", "tours-y-aventura", 72, "tour", "Descenso en rápidos para principiantes con guías certificados y transporte incluido.", image="1521336575822-6da63fb45455", duration="4 horas", difficulty="media"),
 product("Tour de Café y Cacao", "tour-cafe-y-cacao", "tours-y-aventura", 45, "tour", "Visita una finca local, conoce el proceso y prueba café y chocolate recién hechos.", image="1447933601403-0c6688de566e", duration="3 horas", difficulty="baja"),
 product("Snorkel Bahía Cristal", "snorkel-bahia-cristal", "tours-y-aventura", 65, "tour", "Navegación corta y snorkel guiado en arrecifes de aguas transparentes.", image="1544551763-46a013bb70d5", duration="4 horas", difficulty="baja"),
 product("Canopy del Bosque", "canopy-del-bosque", "tours-y-aventura", 55, "tour", "Recorre siete cables entre árboles centenarios acompañado por especialistas.", image="1530789253388-582c481c54b0", duration="2 horas", difficulty="media"),
 product("Masaje de Piedras Calientes", "masaje-piedras-calientes", "spa-y-bienestar", 68, "service", "Masaje corporal relajante de 75 minutos con aceites botánicos y piedras volcánicas.", image="1544161515-4ab6ce6db874", duration="75 min", treatment="relajación"),
 product("Ritual de Hidroterapia", "ritual-de-hidroterapia", "spa-y-bienestar", 54, "service", "Circuito de sauna, vapor, jacuzzi y piscina de contraste para renovar cuerpo y mente.", image="1531058020387-3be344556be6", duration="90 min", treatment="hidroterapia"),
 product("Clase de Yoga al Amanecer", "yoga-al-amanecer", "spa-y-bienestar", 22, "service", "Práctica suave frente al paisaje natural, apta para todos los niveles.", image="1506126613408-eca07ce68773", duration="60 min", level="todos"),
 product("Facial Botánico", "facial-botanico", "spa-y-bienestar", 60, "service", "Limpieza profunda e hidratación con ingredientes botánicos seleccionados para tu piel.", image="1515377905703-c4788e51af15", duration="60 min", treatment="facial"),
 product("Traslado Aeropuerto Privado", "traslado-aeropuerto-privado", "transporte", 38, "service", "Traslado puerta a puerta en vehículo climatizado con seguimiento de vuelo.", image="1549317661-bd32c8ce0db2", vehicle="sedán", capacity=3),
 product("Shuttle a la Playa", "shuttle-a-la-playa", "transporte", 15, "service", "Servicio compartido de ida y vuelta entre el centro y las playas principales.", image="1544620347-c4fd4a3d5957", vehicle="minibús", capacity=12),
 product("Alquiler de Bicicleta Día Completo", "alquiler-bicicleta-dia-completo", "transporte", 18, "service", "Bicicleta urbana con casco, candado y mapa de rutas para explorar a tu ritmo.", image="1485965120184-e220f721d03e", vehicle="bicicleta", duration="día completo"),
 product("Excursión en Catamarán", "excursion-en-catamaran", "transporte", 70, "tour", "Navegación al atardecer con bebidas sin alcohol y paradas para nadar.", image="1540946485063-a40da27545f8", vehicle="catamarán", duration="3 horas"),
 product("Festival de Jazz del Puerto", "festival-jazz-del-puerto", "eventos", 35, "event", "Entrada para una noche de jazz en vivo con artistas locales e internacionales.", image="1514525253161-7a46d19cd819", venue="Anfiteatro del Puerto", starts_at="20:00"),
 product("Noche de Cine Bajo las Estrellas", "cine-bajo-las-estrellas", "eventos", 12, "event", "Proyección al aire libre con manta, palomitas y una selección de cine independiente.", image="1489599849927-2ee91cede3ba", venue="Parque Central", starts_at="19:30"),
 product("Mercado de Diseño Local", "mercado-de-diseno-local", "eventos", 8, "event", "Feria de diseñadores, ilustradores y productores locales con música en directo.", image="1488459716781-31db52582fe9", venue="Nave Cultural", starts_at="11:00"),
 product("Concierto Acústico en la Viña", "concierto-acustico-en-la-vina", "eventos", 45, "event", "Música acústica al atardecer entre viñedos, con copa de bienvenida incluida.", image="1501386761578-eac5c94b800a", venue="Bodega del Valle", starts_at="18:30"),
 product("Cena Teatro Misterio", "cena-teatro-misterio", "eventos", 64, "event", "Cena participativa con actores y una trama para resolver durante la velada.", image="1505236858219-8359eb29e329", venue="Teatro Colonial", starts_at="20:30"),
]

def assert_catalog():
    assert len(CATEGORIES) == 6 and len(PRODUCTS) >= 25
    assert {p["category"] for p in PRODUCTS} == {category[1] for category in CATEGORIES}

class API:
    def __init__(self): self.client = httpx.Client(timeout=30)
    def request(self, method, path, payload=None):
        content = json.dumps(payload, separators=(",", ":")).encode() if payload is not None else b""
        headers = {"Content-Type": "application/json"} if payload is not None else {}
        if API_KEY: headers["X-API-Key"] = API_KEY
        if HMAC_SECRET: headers["X-Hub-Signature"] = hmac.new(HMAC_SECRET.encode(), content, hashlib.sha256).hexdigest()
        try: return self.client.request(method, f"{API_URL}{path}", content=content, headers=headers)
        finally: time.sleep(DELAY)
    def json(self, method, path, payload=None):
        response = self.request(method, path, payload)
        if response.is_error: raise RuntimeError(f"{method} {path}: {response.status_code} {response.text}")
        return response.json()

def create_or_find(api, path, payload, current):
    try: return api.json("POST", path, payload)
    except RuntimeError as error:
        if " 409 " not in str(error): raise
        return current[payload["slug"]]

def main():
    assert_catalog()
    api = API()
    categories = {item["slug"]: item for item in api.json("GET", "/categories")}
    for index, (name, slug, icon) in enumerate(CATEGORIES):
        categories[slug] = create_or_find(api, "/categories", {"name": name, "slug": slug, "icon": icon, "sort_order": index}, categories)
    existing = {item["slug"]: item for item in api.json("GET", "/products")}
    products = {}
    for item in PRODUCTS:
        payload = {key: value for key, value in item.items() if key != "category"}
        payload["category_id"] = categories[item["category"]]["id"]
        products[item["slug"]] = create_or_find(api, "/products", payload, existing)
    start = date.today()
    for item in PRODUCTS:
        slots = 20 if item["product_type"] == "hotel" else 12
        available_dates = {entry["date"] for entry in api.json("GET", f"/products/{products[item['slug']]['id']}/availability")}
        for offset in range(30):
            day = str(start + timedelta(days=offset))
            if day not in available_dates:
                api.json("POST", f"/products/{products[item['slug']]['id']}/availability", {"date": day, "slots_total": slots, "slots_available": slots, "metadata": {"seed": "full-v1"}})
    orders = api.json("GET", "/orders")
    known = {order.get("metadata", {}).get("seed_key") for order in orders}
    states = [("confirmed", "paid"), ("pending", "unpaid"), ("completed", "paid"), ("cancelled", "refunded")]
    for index in range(16):
        key = f"full-v1-{index}"
        if key in known: continue
        item = PRODUCTS[index]
        payload = {"product_id": products[item["slug"]]["id"], "customer_name": f"Cliente Demo {index + 1}", "customer_email": f"cliente{index + 1}@example.test", "customer_phone": "+506 7000-0000", "date_from": str(start + timedelta(days=index + 1)), "date_to": str(start + timedelta(days=index + 2)), "quantity": 1, "total_amount": item["base_price"], "currency": "USD", "metadata": {"seed_key": key, "source": "seed_full"}}
        order = api.json("POST", "/orders", payload)
        status, payment_status = states[index % len(states)]
        api.json("PATCH", f"/orders/{order['id']}", {"status": status, "payment_status": payment_status})
    print(f"Seed completed: {len(CATEGORIES)} categories, {len(PRODUCTS)} products, 30 days availability, 16 orders.")

if __name__ == "__main__": main()
