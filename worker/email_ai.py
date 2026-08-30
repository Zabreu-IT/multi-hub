import os
import smtplib
from email.message import EmailMessage

import requests


FALLBACK_SUBJECT = "Bienvenido a Multi-Hub"


def fallback_email(lead: dict) -> tuple[str, str]:
    name = lead.get("business_name") or lead.get("name") or "Hola"
    return FALLBACK_SUBJECT, f"""Hola {name},

Gracias por registrar tu interés en Multi-Hub. Nos alegra poder acompañarte en este paso.

Un asesor te ayudará personalmente a configurar tu hub: catálogo, disponibilidad y reservas, para que puedas empezar con claridad y sin complicaciones.

En la llamada podremos conocer las necesidades de tu negocio, resolver tus dudas y definir los primeros pasos para que tus clientes encuentren y reserven tus experiencias de forma sencilla. No necesitas preparar nada especial: revisaremos juntos la información que ya tienes y te orientaremos en cada decisión.

Queremos que esta primera conversación sea útil, cercana y enfocada en las oportunidades reales de tu negocio.

Puedes conocer más sobre nosotros y nuestros servicios en https://zabreuit.com.

Saludos,
Equipo Zabreuit"""


def valid_body(body: str) -> bool:
    return 100 <= len(body.split()) <= 220 and all(item in body for item in ("https://zabreuit.com", "Zabreuit"))


def generate_welcome_email(lead: dict) -> tuple[str, str]:
    if not (api_key := os.getenv("OPENROUTER_API_KEY")):
        return fallback_email(lead)
    prompt = f'''Redacta un correo breve, amigable y no técnico en español para {lead.get("business_name") or lead.get("name") or "un nuevo cliente"}. Agradece su interés en Multi-Hub y explica que un asesor le ayudará personalmente a configurar su hub (catálogo, disponibilidad y reservas). Incluye https://zabreuit.com y la firma "Equipo Zabreuit". Debe tener 100-220 palabras. Devuelve únicamente el correo, con "Asunto: ..." como primera línea.'''
    try:
        response = requests.post(
            "https://openrouter.ai/api/v1/chat/completions",
            headers={"Authorization": f"Bearer {api_key}"},
            json={"model": os.getenv("OPENROUTER_MODEL", "nvidia/nemotron-3-super-120b-a12b:free"), "messages": [{"role": "user", "content": prompt}]},
            timeout=30,
        )
        response.raise_for_status()
        content = response.json()["choices"][0]["message"]["content"].strip()
        subject, separator, body = content.partition("\n")
        if not subject.lower().startswith("asunto:") or not subject.split(":", 1)[1].strip() or not separator or not valid_body(body):
            raise ValueError("OpenRouter response did not include subject and body")
        return subject.split(":", 1)[1].strip(), body.strip()
    except (requests.RequestException, KeyError, IndexError, TypeError, ValueError):
        return fallback_email(lead)


def send_email(to_email, subject, body):
    try:
        host = os.getenv("SMTP_HOST", "smtp.zoho.com")
        port = int(os.getenv("SMTP_PORT", "465"))
        user = os.getenv("SMTP_USER", "hola@zabreuit.com")
        password = os.getenv("SMTP_PASS")
        if not password:
            return {"success": False, "error": "SMTP_PASS is not configured"}
        message = EmailMessage()
        message["From"] = f"Zabreuit <{user}>"
        message["To"] = to_email
        message["Subject"] = subject
        message.set_content(body)
        smtp = smtplib.SMTP_SSL(host, port) if port == 465 else smtplib.SMTP(host, port)
        with smtp:
            if port == 587:
                smtp.starttls()
            smtp.login(user, password)
            smtp.send_message(message)
        return {"success": True, "error": ""}
    except (OSError, ValueError, smtplib.SMTPException) as error:
        return {"success": False, "error": str(error)}
