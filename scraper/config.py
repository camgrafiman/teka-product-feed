import os

CATEGORIES = [
    {"name": "Hornos",                       "url": "https://www.teka.com/es-es/cocina/hornos/"},
    {"name": "Microondas",                   "url": "https://www.teka.com/es-es/cocina/microondas/"},
    {"name": "Cafeteras Integrables",        "url": "https://www.teka.com/es-es/cocina/cafeteras-integrables/"},
    {"name": "Placas",                       "url": "https://www.teka.com/es-es/cocina/placas/"},
    {"name": "Cocinas de Libre Instalación", "url": "https://www.teka.com/es-es/cocina/cocinas-de-libre-instalacion/"},
    {"name": "Campanas",                     "url": "https://www.teka.com/es-es/cocina/campanas/"},
    {"name": "Frigoríficos y Congeladores",  "url": "https://www.teka.com/es-es/cocina/frigorificos-y-congeladores/"},
    {"name": "Vinotecas",                    "url": "https://www.teka.com/es-es/cocina/vinotecas/"},
    {"name": "Fregaderos",                   "url": "https://www.teka.com/es-es/cocina/fregaderos/"},
    {"name": "Grifería de Cocina",           "url": "https://www.teka.com/es-es/cocina/griferia-de-cocina/"},
    {"name": "Lavavajillas",                 "url": "https://www.teka.com/es-es/cocina/lavavajillas/"},
    {"name": "Pequeño Electrodoméstico",     "url": "https://www.teka.com/es-es/cocina/pequeno-electrodomestico/"},
    {"name": "Complementos",                 "url": "https://www.teka.com/es-es/cocina/complementos/"},
    {"name": "Repuestos y Otros Accesorios", "url": "https://www.teka.com/es-es/cocina/repuestos-y-otros-accesorios/"},
    {"name": "Lavadoras",                    "url": "https://www.teka.com/es-es/lavado/lavadoras/"},
    {"name": "Secadoras",                    "url": "https://www.teka.com/es-es/lavado/secadoras/"},
    {"name": "Lavadoras-Secadoras",          "url": "https://www.teka.com/es-es/lavado/lavadoras-secadoras/"},
    {"name": "Termos Estándar",              "url": "https://www.teka.com/es-es/termos/termos-estandar/"},
    {"name": "Filtros de Agua de Cocina",    "url": "https://www.teka.com/es-es/tratamiento-del-agua/filtros-de-agua-de-cocina/"},
]

BROWSER = {
    "headless": True,
    "viewport": {"width": 1920, "height": 1080},
    "user_agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "locale": "es-ES",
    "timeout": 30_000,
}

SCROLL = {
    "step_px": 800,
    "pause_ms": 1_500,
    "max_rounds": 30,
    "idle_rounds_to_stop": 3,
}

SHEETS = {
    "spreadsheet_id": os.getenv("GOOGLE_SHEET_ID", ""),
    "products_tab": "Productos",
    "log_tab": "Log",
}

BASE_URL = "https://www.teka.com"

# Selectors (ordered by confidence). The scraper tries each and uses the first match.
PRODUCT_CARD_SELECTORS = [
    ".products-list .product-card",
    ".product-list__item",
    ".product-item",
    "article.product",
    "[data-entity-type='product']",
    ".views-row",
    "li.product",
]

PRODUCT_LINK_SELECTORS = ["a.product-card__link", "a.product-link", "h2 a", "h3 a", ".product-name a", "a"]
PRODUCT_NAME_SELECTORS = [".product-card__title", ".product-name", "h2", "h3", ".title"]
PRODUCT_DESC_SELECTORS = [".product-card__description", ".product-description", ".description", "p"]
PRODUCT_IMAGE_SELECTORS = ["img[data-src]", "img[data-lazy-src]", "img[src]", "img"]
PRODUCT_BADGE_SELECTORS = [".product-card__badge", ".badge", ".tag", ".label"]
PRODUCT_COLOR_SELECTORS = [".product-card__colors .color-swatch", ".color-option", ".swatch", "[class*='color']"]

# Consent / cookie banner dismiss selectors
CONSENT_SELECTORS = [
    "#onetrust-accept-btn-handler",
    ".cookie-accept",
    "button[id*='accept']",
    "button[class*='accept']",
    "#accept-cookies",
    ".js-accept-cookies",
]
