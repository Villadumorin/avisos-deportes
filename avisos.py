"""Avisos push de F1, MotoGP e Celta vía ntfy.

Cada execución le os horarios, calcula os avisos das próximas horas e
prográmaos en ntfy (que os entrega á hora exacta). Os avisos xa
programados non se repiten.

Uso:
  python avisos.py            # programa os avisos (precisa NTFY_TOPIC)
  python avisos.py --dry-run  # só amosa o que programaría
  python avisos.py --proba    # manda unha notificación de proba agora
"""

import json
import os
import re
import sys
import urllib.request
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

# --- Configuración -------------------------------------------------------

TZ = ZoneInfo("Europe/Madrid")
NTFY_SERVER = os.environ.get("NTFY_SERVER", "https://ntfy.sh").rstrip("/")
NTFY_TOPIC = os.environ.get("NTFY_TOPIC", "")

AVISO_ANTES = timedelta(hours=1)
HORIZONTE = timedelta(hours=36)  # canto adiante se programa en cada execución
TOLERANCIA = timedelta(minutes=15)  # avisos atrasados que aínda se mandan
RESUMO_DIA, RESUMO_HORA = 0, 9  # luns ás 09:00

# Sesións que avisan. Quita as que non queiras.
F1_SESIONS = {"FP1", "FP2", "FP3", "Sprint Qualifying", "Sprint", "Qualifying", "Grand Prix"}
MOTOGP_SESIONS = {"FP1", "PR", "FP2", "Q", "SPR", "RAC"}  # sen Warm Up

CELTA_ESPN_ID = 85
F1_ICS = "https://files-f1.motorsportcalendars.com/f1-calendar_p1_p2_p3_qualifying_sprint_gp.ics"
MOTOGP_API = "https://api.pulselive.motogp.com/motogp/v1/events?seasonYear={}"
CELTA_API = f"https://site.api.espn.com/apis/site/v2/sports/soccer/all/teams/{CELTA_ESPN_ID}/schedule?fixture=true"

DIAS = ["luns", "martes", "mércores", "xoves", "venres", "sábado", "domingo"]
F1_NOMES = {
    "FP1": "Libres 1", "FP2": "Libres 2", "FP3": "Libres 3",
    "Sprint Qualifying": "Clasificación sprint", "Sprint": "Sprint",
    "Qualifying": "Clasificación", "Grand Prix": "Carreira",
}
MOTOGP_NOMES = {
    "FP1": "Libres 1", "PR": "Práctica", "FP2": "Libres 2",
    "Q": "Clasificación", "SPR": "Sprint", "RAC": "Carreira",
}


# --- Lectura de horarios -------------------------------------------------

def descargar(url):
    req = urllib.request.Request(url, headers={"User-Agent": "avisos-deportes/1.0"})
    with urllib.request.urlopen(req, timeout=30) as r:
        return r.read().decode("utf-8")


def eventos_f1():
    texto = descargar(F1_ICS).replace("\r\n ", "").replace("\n ", "")
    eventos = []
    for bloque in texto.split("BEGIN:VEVENT")[1:]:
        resumo = re.search(r"^SUMMARY:(.*)$", bloque, re.M).group(1).strip()
        inicio = re.search(r"^DTSTART:(\d{8}T\d{6})Z", bloque, re.M).group(1)
        m = re.match(r"F1: (.+?) \((.+)\)", resumo)
        if not m or m.group(1) not in F1_SESIONS:
            continue
        gp = "GP " + m.group(2).replace(" Grand Prix", "")
        eventos.append({
            "deporte": "F1",
            "cando": datetime.strptime(inicio, "%Y%m%dT%H%M%S").replace(tzinfo=timezone.utc),
            "titulo": f"F1 · {F1_NOMES[m.group(1)]}",
            "detalle": gp,
            "grupo": gp,
            "hora_confirmada": True,
        })
    return eventos


def eventos_motogp(agora):
    eventos = []
    for ano in sorted({agora.year, (agora + HORIZONTE + timedelta(days=7)).year}):
        for gp in json.loads(descargar(MOTOGP_API.format(ano))):
            if gp.get("kind") != "GP" or gp.get("status") == "CANCELLED":
                continue
            nome = "GP " + (gp.get("additional_name") or gp["name"]).title()
            q_visto = False
            for b in gp.get("broadcasts", []):
                if b.get("type") != "SESSION" or (b.get("category") or {}).get("acronym") != "MGP":
                    continue
                codigo = b["shortname"]
                if codigo in ("Q1", "Q2"):
                    # Q1 e Q2 van seguidas: un só aviso de clasificación
                    if q_visto:
                        continue
                    q_visto, codigo = True, "Q"
                if codigo not in MOTOGP_SESIONS:
                    continue
                eventos.append({
                    "deporte": "MotoGP",
                    "cando": datetime.strptime(b["date_start"], "%Y-%m-%dT%H:%M:%S%z"),
                    "titulo": f"MotoGP · {MOTOGP_NOMES[codigo]}",
                    "detalle": nome,
                    "grupo": nome,
                    "hora_confirmada": True,
                })
    return eventos


def eventos_celta():
    eventos = []
    for ev in json.loads(descargar(CELTA_API)).get("events", []):
        comp = ev["competitions"][0]
        casa = next(c for c in comp["competitors"] if c["homeAway"] == "home")["team"]["displayName"]
        fora = next(c for c in comp["competitors"] if c["homeAway"] == "away")["team"]["displayName"]
        competicion = (ev.get("league") or {}).get("name", "").replace("Spanish ", "")
        eventos.append({
            "deporte": "Celta",
            "cando": datetime.fromisoformat(ev["date"].replace("Z", "+00:00")),
            "titulo": f"⚽ {casa} - {fora}",
            "detalle": competicion,
            "grupo": None,
            "hora_confirmada": bool(comp.get("timeValid", True)),
        })
    return eventos


# --- Avisos --------------------------------------------------------------

def hora_local(dt):
    return dt.astimezone(TZ).strftime("%H:%M")


def dia_local(dt):
    d = dt.astimezone(TZ)
    return f"{DIAS[d.weekday()]} {d.day}/{d.month}"


ETIQUETAS = {"F1": "racing_car", "MotoGP": "motorcycle", "Celta": "soccer"}


def avisos_de_sesion(ev):
    if not ev["hora_confirmada"]:
        return []
    titulo = ev["titulo"].replace("⚽ ", "")
    base = f"{ev['detalle']} · {dia_local(ev['cando'])} ás {hora_local(ev['cando'])}"
    tag = ETIQUETAS[ev["deporte"]]
    return [
        {"cando": ev["cando"] - AVISO_ANTES, "titulo": f"En 1 hora: {titulo}",
         "mensaxe": base, "tags": [tag], "prioridade": 3},
        {"cando": ev["cando"], "titulo": f"Comeza agora: {titulo}",
         "mensaxe": base, "tags": [tag], "prioridade": 4},
    ]


def resumo_semanal(eventos, luns):
    """Aviso do luns co que hai na semana que empeza ese día (hora local)."""
    fin = luns + timedelta(days=7)
    semana = sorted((e for e in eventos if luns <= e["cando"] < fin), key=lambda e: e["cando"])

    def hora(e):
        return hora_local(e["cando"]) if e["hora_confirmada"] else "hora por confirmar"

    linas = []
    partidos = [e for e in semana if e["deporte"] == "Celta"]
    if partidos:
        for e in partidos:
            linas.append(f"⚽ {e['titulo'][2:]} ({e['detalle']}) · {dia_local(e['cando'])}, {hora(e)}")
    else:
        linas.append("⚽ Sen partido do Celta")

    for deporte, emoji in (("F1", "🏎️"), ("MotoGP", "🏍️")):
        sesions = [e for e in semana if e["deporte"] == deporte]
        if not sesions:
            linas.append(f"{emoji} Sen {deporte}")
            continue
        for grupo in dict.fromkeys(e["grupo"] for e in sesions):
            linas.append(f"{emoji} {deporte} · {grupo}")
            carreira = [e for e in sesions if e["grupo"] == grupo and e["titulo"].endswith("Carreira")]
            if carreira:
                c = carreira[0]
                linas.append(f"   Carreira: {dia_local(c['cando'])}, {hora(c)}")

    return {
        "cando": luns.replace(hour=RESUMO_HORA),
        "titulo": f"A semana do {luns.day}/{luns.month}",
        "mensaxe": "\n".join(linas),
        "tags": ["calendar"],
        "prioridade": 3,
    }


def calcular_avisos(eventos, agora):
    avisos = [a for ev in eventos for a in avisos_de_sesion(ev)]
    hoxe = agora.astimezone(TZ).replace(hour=0, minute=0, second=0, microsecond=0)
    for dias in range(0, HORIZONTE.days + 2):
        dia = hoxe + timedelta(days=dias)
        if dia.weekday() == RESUMO_DIA:
            avisos.append(resumo_semanal(eventos, dia))
    return sorted(
        (a for a in avisos if agora - TOLERANCIA <= a["cando"] < agora + HORIZONTE),
        key=lambda a: a["cando"],
    )


# --- ntfy ----------------------------------------------------------------

def ntfy_xa_programados():
    """Chaves (título, mensaxe) dos avisos xa enviados ou programados."""
    url = f"{NTFY_SERVER}/{NTFY_TOPIC}/json?poll=1&since=all&sched=1"
    chaves = set()
    for lina in descargar(url).splitlines():
        m = json.loads(lina)
        if m.get("event") == "message":
            chaves.add((m.get("title", ""), m.get("message", "")))
    return chaves


def ntfy_enviar(aviso, agora):
    corpo = {
        "topic": NTFY_TOPIC,
        "title": aviso["titulo"],
        "message": aviso["mensaxe"],
        "tags": aviso["tags"],
        "priority": aviso["prioridade"],
    }
    # ntfy só acepta programar con polo menos 10 s de antelación
    if aviso["cando"] - agora > timedelta(seconds=30):
        corpo["delay"] = str(int(aviso["cando"].timestamp()))
    req = urllib.request.Request(
        NTFY_SERVER, data=json.dumps(corpo).encode("utf-8"),
        headers={"Content-Type": "application/json"}, method="POST",
    )
    urllib.request.urlopen(req, timeout=30).read()


def main():
    args = set(sys.argv[1:])
    dry_run = "--dry-run" in args or "--semana" in args
    if not NTFY_TOPIC and not dry_run:
        sys.exit("Falta a variable NTFY_TOPIC")

    agora = datetime.now(timezone.utc)

    if "--proba" in args:
        ntfy_enviar({"cando": agora, "titulo": "Proba de avisos",
                     "mensaxe": "Se ves isto, os avisos funcionan 👍",
                     "tags": ["white_check_mark"], "prioridade": 3}, agora)
        print("Proba enviada")
        return

    eventos, erros = [], []
    for nome, fonte in (("F1", eventos_f1), ("MotoGP", lambda: eventos_motogp(agora)), ("Celta", eventos_celta)):
        try:
            eventos += fonte()
        except Exception as e:  # unha fonte caída non debe parar as outras
            erros.append(f"{nome}: {e}")
            print(f"Erro lendo {nome}: {e}", file=sys.stderr)

    if "--semana" in args:
        # Amosa o resumo desta semana (útil para probar)
        hoxe = agora.astimezone(TZ).replace(hour=0, minute=0, second=0, microsecond=0)
        r = resumo_semanal(eventos, hoxe - timedelta(days=hoxe.weekday()))
        print(r["titulo"]); print(r["mensaxe"])
        return

    avisos = calcular_avisos(eventos, agora)
    xa = set() if dry_run else ntfy_xa_programados()
    novos = 0
    for a in avisos:
        if (a["titulo"], a["mensaxe"]) in xa:
            continue
        cando = a["cando"].astimezone(TZ).strftime("%a %d/%m %H:%M")
        print(f"{cando}  {a['titulo']}  |  {a['mensaxe'].splitlines()[0]}")
        if not dry_run:
            ntfy_enviar(a, agora)
        novos += 1
    print(f"{novos} avisos novos ({len(avisos)} na xanela de {HORIZONTE})")
    if erros:
        sys.exit(1)


if __name__ == "__main__":
    main()
