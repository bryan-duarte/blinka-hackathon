import random
from typing import Literal

ToolPhase = Literal["start", "finish"]

TOOL_PHRASES: dict[str, dict[ToolPhase, tuple[str, ...]]] = {
    "classify_document": {
        "start": (
            "Leyendo el documento para entender si es una factura…",
            "Clasificando el documento: ¿cobro, cotización o nota de crédito?",
            "Revisando qué tipo de documento llegó…",
            "Mirando el documento para saber si hay algo que pagar…",
        ),
        "finish": (
            "Listo, ya sé qué tipo de documento es.",
            "Documento clasificado.",
            "Ya identifiqué el tipo de documento.",
        ),
    },
    "extract_invoice": {
        "start": (
            "Sacando monto, moneda y beneficiario del documento…",
            "Extrayendo los datos clave de la factura…",
            "Leyendo número de factura y fecha de vencimiento…",
            "Anotando a quién, cuánto y para cuándo hay que pagar…",
        ),
        "finish": (
            "Datos de la factura extraídos.",
            "Ya tengo monto, moneda y beneficiario.",
            "Listo, los datos clave quedaron anotados.",
        ),
    },
    "register_bill": {
        "start": (
            "Buscando al beneficiario en la lista permitida…",
            "Revisando si esta factura ya había llegado antes…",
            "Registrando la factura y comparándola con las anteriores…",
        ),
        "finish": (
            "Factura registrada.",
            "Beneficiario revisado y factura registrada.",
            "Listo, ya sé si esta factura es nueva.",
        ),
    },
    "evaluate_rules": {
        "start": (
            "Comparando contra las reglas de pago de la empresa…",
            "Revisando límites, presupuesto y beneficiarios…",
            "Pasando la factura por las 18 reglas de pago…",
            "Verificando montos máximos y presupuesto del periodo…",
        ),
        "finish": (
            "Reglas de pago revisadas.",
            "Listo, ya revisé todas las reglas.",
            "Terminé de comparar contra las reglas de la empresa.",
        ),
    },
    "run_checker": {
        "start": (
            "Haciendo una segunda revisión antes de pagar…",
            "Verificando que todo cuadre con lo acordado…",
            "Pidiendo una segunda opinión antes de mover dinero…",
        ),
        "finish": (
            "Segunda revisión terminada.",
            "El verificador ya dio su opinión.",
            "Listo, la segunda revisión quedó hecha.",
        ),
    },
    "settle_decision": {
        "start": (
            "Registrando la decisión y su explicación…",
            "Dejando constancia de por qué se decidió así…",
            "Guardando la decisión en el registro…",
        ),
        "finish": (
            "Decisión registrada.",
            "Listo, la decisión quedó guardada con su explicación.",
            "Decisión tomada y anotada.",
        ),
    },
}
TOOL_ERROR_PHRASES: tuple[str, ...] = (
    "Este paso no se pudo completar.",
    "Algo falló en este paso.",
    "Este paso no salió como esperaba.",
)
STEP_PHRASES: dict[str, tuple[str, ...]] = {
    "started": (
        "El agente empezó a trabajar en esta factura.",
        "El agente tomó el documento y empezó a revisarlo.",
    ),
    "classified": ("Documento clasificado.",),
    "not_a_bill": (
        "Esto no parece una factura por pagar.",
        "No encontré nada que pagar en este documento.",
    ),
    "extracted": ("Datos de la factura extraídos.",),
    "extraction_failed": (
        "No se pudieron leer los datos de la factura.",
        "El documento no trae datos suficientes para pagar.",
    ),
    "claimed": ("Factura registrada.",),
    "decided": ("Decisión tomada.",),
    "decision_failed": (
        "Algo falló al decidir; la factura queda en revisión.",
        "No pude terminar los controles; una persona debe revisarla.",
    ),
    "completed": ("El agente terminó.", "Revisión terminada."),
    "cancelled": ("La revisión se interrumpió.",),
    "failed": ("La revisión falló.", "El agente no pudo terminar la revisión."),
}


def pick_tool_phrase(tool: str, phase: ToolPhase) -> str:
    return random.choice(TOOL_PHRASES[tool][phase])


def pick_tool_error_phrase() -> str:
    return random.choice(TOOL_ERROR_PHRASES)


def pick_step_phrase(step: str) -> str | None:
    step_phrases = STEP_PHRASES.get(step)
    if step_phrases is None:
        return None
    return random.choice(step_phrases)
