"""Configuración del canal: nombre, colores, voz y pronunciaciones."""
import re

CHANNEL_NAME = "SEIS ESTRELLAS"
CHANNEL_HANDLE = "@SeisEstrellasGTA"   # cámbialo por el handle real del canal

W, H, FPS = 1920, 1080, 30
SR = 24000  # frecuencia de la voz (Kokoro) y de la mezcla

VOICE = "em_alex"   # voz masculina en español (alternativas: em_santa, ef_dora)
VOICE_SPEED = 1.07

FONT_DIR = "/usr/share/fonts/opentype/inter/"
F_BLACK_IT = FONT_DIR + "InterDisplay-BlackItalic.otf"
F_BLACK = FONT_DIR + "InterDisplay-Black.otf"
F_XBOLD = FONT_DIR + "InterDisplay-ExtraBold.otf"
F_BOLD = FONT_DIR + "Inter-Bold.otf"
F_SEMI = FONT_DIR + "Inter-SemiBold.otf"

# Paleta "neón de Florida"
PINK = (255, 46, 136)
ORANGE = (255, 140, 40)
YELLOW = (255, 214, 64)
CYAN = (40, 230, 255)
PURPLE = (126, 60, 255)
NAVY = (10, 8, 30)
WHITE = (255, 255, 255)
SOFT = (210, 205, 235)
GREEN = (60, 240, 150)
RED = (255, 70, 80)

# Correcciones de pronunciación SOLO para la voz (los subtítulos usan el texto original)
PRONUNCIATION = [
    (r"\bGTA VI\b", "ge te a seis"),
    (r"\bGTA Online\b", "ge te a onláin"),
    (r"\bGTA\+", "ge te a plus"),
    (r"\bGTA\b", "ge te a"),
    (r"\bXbox\b", "équis box"),
    (r"\bSeries X\b", "Series équis"),
    (r"\bSeries S\b", "Series ese"),
    (r"\bX\|S\b", "équis y ese"),
    (r"\bPS5 Pro\b", "pe ese cinco pro"),
    (r"\bPS5\b", "pe ese cinco"),
    (r"\bPS4\b", "pe ese cuatro"),
    (r"\bPS3\b", "pe ese tres"),
    (r"\bPC\b", "pe ce"),
    (r"\bVice City\b", "Vais Síti"),
    (r"\bSan Andreas\b", "San Andreas"),
    (r"\bLiberty City\b", "Líberti Síti"),
    (r"\bLos Santos\b", "Los Santos"),
    (r"\bJason\b", "Yéison"),
    (r"\bDuval\b", "Duval"),
    (r"\bUltimate\b", "Áltimeit"),
    (r"\bVintage\b", "Víntach"),
    (r"\bStanier\b", "Stánier"),
    (r"\bStandard\b", "Estándar"),
    (r"\bRockstar Games\b", "Rocstar Geims"),
    (r"\bRockstar\b", "Rocstar"),
    (r"\bTake-Two\b", "Teik Tu"),
    (r"\bTrailer\b", "tráiler"),
    (r"\bHDR\b", "hache de erre"),
    (r"\bVRR\b", "uve erre erre"),
    (r"\bHDMI\b", "hache de eme i"),
    (r"\bSSD\b", "ese ese de"),
    (r"\bTB\b", "teras"),
    (r"\bGB\b", "gigas"),
    (r"\bfps\b", "fotogramas por segundo"),
    (r"\bYouTube\b", "Yutub"),
    (r"\bKeys\b", "Kis"),
    (r"\bGrassrivers\b", "Grasrívers"),
    (r"\bPort Gellhorn\b", "Port Guélhorn"),
    (r"\bAmbrosia\b", "Ambrosia"),
    (r"\bMount Kalaga\b", "Maunt Kalaga"),
    (r"\bLeonida\b", "Leónida"),
    (r"\bonline\b", "onláin"),
    (r"\bstreaming\b", "estrímin"),
    (r"\bspoilers?\b", "espóilers"),
    (r"\bleaks?\b", "liks"),
    (r"\bshooter\b", "chúter"),
    (r"\bgameplay\b", "guéimplei"),
    (r"\bupdate\b", "ápdeit"),
    (r"\bpatch\b", "pach"),
    (r"\bstore\b", "estor"),
    (r"\bStore\b", "Estor"),
    (r"\bMicrosoft\b", "Máicrosoft"),
    (r"\bPlayStation\b", "Pléisteishon"),
    (r"\bNetwork\b", "Nétwork"),
    (r"\bTwitter\b", "Tuíter"),
    (r"\bGame Pass\b", "Guéim Pas"),
    (r"\bQ1\b", "primer trimestre"),
    (r"%", " por ciento"),
    (r"€", " euros"),
    (r"\bvs\.?\b", "contra"),
    (r"\bMXN\b", "pesos mexicanos"),
    (r"\bUSD\b", "dólares"),
]


def tts_text(text: str) -> str:
    out = text
    for pat, rep in PRONUNCIATION:
        out = re.sub(pat, rep, out)
    out = out.replace("—", ", ").replace("«", "").replace("»", "").replace("\"", "")
    return out
