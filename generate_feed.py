import xml.etree.ElementTree as ET

from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup
from feedgen.feed import FeedGenerator


SOURCE_URL = "https://www.immedica.com/en/press-releases"
BASE_URL = "https://www.immedica.com"
OUTPUT_FILE = Path("docs/feed.xml")
MAX_ITEMS = 100

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 Chrome/130.0 Safari/537.36"
    )
}


def limpiar(texto):
    return " ".join((texto or "").split())


def leer_anteriores():
    anteriores = {}

    if not OUTPUT_FILE.exists():
        return anteriores

    try:
        root = ET.parse(OUTPUT_FILE).getroot()

        for item in root.findall("./channel/item"):
            enlace = limpiar(item.findtext("link"))

            if enlace:
                anteriores[enlace] = {
                    "title": limpiar(item.findtext("title")),
                    "description": limpiar(
                        item.findtext("description")
                    ),
                    "pubDate": limpiar(item.findtext("pubDate")),
                }

    except Exception as error:
        print(f"No se pudo leer la RSS anterior: {error}")

    return anteriores


def convertir_fecha(texto):
    try:
        fecha = datetime.fromisoformat(
            texto.replace("Z", "+00:00")
        )

        if fecha.tzinfo is None:
            fecha = fecha.replace(tzinfo=timezone.utc)

        return fecha

    except Exception:
        return datetime.now(timezone.utc)


def obtener_comunicados():
    respuesta = requests.get(
        SOURCE_URL,
        headers=HEADERS,
        timeout=60
    )
    respuesta.raise_for_status()

    soup = BeautifulSoup(respuesta.text, "html.parser")
    comunicados = {}

    for bloque in soup.select(".views-row"):
        enlace_elemento = bloque.select_one(
            '.headline a[href*="/en/press/"]'
        )
        fecha_elemento = bloque.select_one("time[datetime]")

        if not enlace_elemento:
            continue

        href = enlace_elemento.get("href", "")
        titulo = limpiar(
            enlace_elemento.get_text(" ", strip=True)
        )

        if not href or not titulo:
            continue

        enlace = urljoin(BASE_URL, href)
        enlace = enlace.split("?")[0].split("#")[0]

        fecha_texto = (
            fecha_elemento.get("datetime", "")
            if fecha_elemento else ""
        )

        comunicados[enlace] = {
            "title": titulo,
            "link": enlace,
            "description": (
                "Comunicado de prensa publicado por Immedica."
            ),
            "date": convertir_fecha(fecha_texto),
        }

    if not comunicados:
        raise RuntimeError(
            "No se encontraron comunicados de Immedica. "
            "La RSS anterior no será eliminada."
        )

    return comunicados


def generar_rss():
    comunicados = obtener_comunicados()
    anteriores = leer_anteriores()

    for enlace, anterior in anteriores.items():
        if enlace not in comunicados:
            try:
                from email.utils import parsedate_to_datetime
                fecha = parsedate_to_datetime(
                    anterior["pubDate"]
                )
            except Exception:
                fecha = datetime(1970, 1, 1, tzinfo=timezone.utc)

            comunicados[enlace] = {
                "title": anterior["title"],
                "link": enlace,
                "description": anterior["description"],
                "date": fecha,
            }

    ordenados = sorted(
        comunicados.values(),
        key=lambda elemento: elemento["date"],
        reverse=True
    )[:MAX_ITEMS]

    feed = FeedGenerator()
    feed.title("Immedica - Press Releases")
    feed.link(href=SOURCE_URL, rel="alternate")
    feed.description(
        "Últimos comunicados de prensa de Immedica"
    )
    feed.language("en")
    feed.id(SOURCE_URL)
    feed.lastBuildDate(datetime.now(timezone.utc))

    for comunicado in reversed(ordenados):
        entrada = feed.add_entry()
        entrada.id(comunicado["link"])
        entrada.title(comunicado["title"])
        entrada.link(href=comunicado["link"])
        entrada.description(comunicado["description"])
        entrada.pubDate(comunicado["date"])

    OUTPUT_FILE.parent.mkdir(
        parents=True,
        exist_ok=True
    )

    feed.rss_file(
        str(OUTPUT_FILE),
        pretty=True
    )

    print(
        f"RSS creada correctamente con "
        f"{len(ordenados)} comunicados."
    )


if __name__ == "__main__":
    generar_rss()
