"""Costo mensile stimato dell'architettura target su Azure: ipotesi esplicite, prezzi letti a mano.

Nessun prezzo è scritto nel codice: arrivano da docs/cost_inputs.json, con fonte e data.
"""
PRICE_KEYS = [
    "container_apps_vcpu_second", "container_apps_gib_second",
    "cosmos_serverless_per_million_ru", "cosmos_storage_gb_month", "blob_hot_lrs_gb_month",
    "key_vault_per_10k_operations", "registry_month", "log_analytics_per_gb",
    "gemini_input_per_million", "gemini_output_per_million", "gemini_embed_per_million",
]
GRANT_KEYS = ["container_apps_vcpu_seconds", "container_apps_gib_seconds", "log_analytics_free_gb"]
COMPONENTS = ["Container Apps", "Cosmos DB", "Blob Storage", "Key Vault", "Registry", "Log Analytics",
              "Gemini API"]


def check_inputs(inputs: dict) -> None:
    """Errore se manca un prezzo o una soglia gratuita: meglio fermarsi che stimare con un buco."""
    missing = [k for k in PRICE_KEYS if inputs["prices"].get(k) is None]
    missing += [k for k in GRANT_KEYS if inputs["free_grants"].get(k) is None]
    if missing:
        raise ValueError("Valori mancanti in cost_inputs.json: " + ", ".join(missing))


def monthly_costs(inputs: dict, learners: int, ru_factor: float = 1.0) -> dict:
    """Costo al mese per componente, totale e per studente. ru_factor serve per la sensibilità."""
    check_inputs(inputs)
    p, g, u = inputs["prices"], inputs["free_grants"], inputs["usage"]
    sessions = learners * u["sessions_per_learner_month"]
    questions = sessions * u["questions_per_session"]
    notes_queries = questions * u["notes_share"]

    # Scala a zero: la replica è attiva solo durante le sessioni. sessions_per_replica = 1 è la CLI di oggi
    # (un container per conversazione); con un'API HTTP una replica servirebbe più sessioni insieme.
    active_seconds = sessions * u["minutes_per_session"] * 60 / u["sessions_per_replica"]
    vcpu_s = active_seconds * u["replica_vcpu"]
    gib_s = active_seconds * u["replica_gib"]
    container = (max(0.0, vcpu_s - g["container_apps_vcpu_seconds"]) * p["container_apps_vcpu_second"]
                 + max(0.0, gib_s - g["container_apps_gib_seconds"]) * p["container_apps_gib_second"])

    ru = ru_factor * (notes_queries * u["ru_per_vector_query"]
                      + sessions * u["progress_writes_per_session"] * u["ru_per_progress_write"])
    cosmos = ru / 1e6 * p["cosmos_serverless_per_million_ru"] + u["storage_gb"] * p["cosmos_storage_gb_month"]
    blob = u["storage_gb"] * p["blob_hot_lrs_gb_month"]
    key_vault = sessions * u["key_vault_ops_per_session"] / 10_000 * p["key_vault_per_10k_operations"]
    logs = max(0.0, learners * u["log_gb_per_learner_month"] - g["log_analytics_free_gb"]) * p["log_analytics_per_gb"]
    llm = (questions * (u["tokens_in_per_question"] * p["gemini_input_per_million"]
                        + u["tokens_out_per_question"] * p["gemini_output_per_million"])
           + notes_queries * u["embed_tokens_per_query"] * p["gemini_embed_per_million"]) / 1e6

    parts = dict(zip(COMPONENTS, [container, cosmos, blob, key_vault, p["registry_month"], logs, llm]))
    total = sum(parts.values())
    return {"parts": parts, "total": total, "per_learner": total / learners,
            "questions": questions, "vcpu_seconds": vcpu_s}