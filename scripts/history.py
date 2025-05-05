import os
from scripts.healthreact import HealthReact

# Funkce pro zobrazení historie doporučení uživatele

def show_user_history(user_id: str, limit: int = 10):
    """
    Otevře nové okno a zobrazí historii doporučení (traces) pro daného uživatele.
    """
    # Inicializace HealthReact s API klíčem z prostředí
    hr = HealthReact(api_key=os.environ["HR_API_KEY"])
    traces = hr.get_user_traces(user_id, limit=limit)
    print(f"Historie doporučení pro uživatele {user_id} (posledních {limit}):\n")
    for idx, trace in enumerate(traces, 1):
        print(f"{idx}. Datum: {getattr(trace, 'createdAt', '-')}, Výstup: {getattr(trace, 'output', '-')}")
    print("\nPro detail zadejte číslo záznamu nebo ID trace.")


def show_trace_detail(trace):
    """
    Zobrazí detailní informace o konkrétním trace.
    """
    print(f"Trace ID: {getattr(trace, 'id', '-')}")
    print(f"Name: {getattr(trace, 'name', '-')}")
    print(f"Input: {getattr(trace, 'input', '-')}")
    print(f"Output: {getattr(trace, 'output', '-')}")
    print(f"Tags: {getattr(trace, 'tags', '-')}")
    print(f"Metadata: {getattr(trace, 'metadata', '-')}")
    print(f"Vytvořeno: {getattr(trace, 'createdAt', '-')}")
    print("===\n")

