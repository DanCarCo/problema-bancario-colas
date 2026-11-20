"""
Simulación del problema bancario (Teoría de Colas, Actividad didáctica 2-M3).

Modelo
------
* Cada cajero es una cola M/M/1 independiente (FIFO, un servidor, velocidad
  de atención idéntica entre cajeros, desplazamiento despreciable).
* Las llegadas se generan como en la guía del laboratorio: para cada cliente se
  sortea primero la acción (70 % retiro / 30 % pago), luego el tipo de usuario
  (Tabla 2) y por último el tiempo hasta su llegada ~ Exp(media de llegada del
  tipo, Tabla 1). El servicio es Exp(media de servicio del tipo, Tabla 1).
* El banco recibe clientes durante 480 min; los que están dentro al cierre se
  terminan de atender (no se descartan).
* Números aleatorios comunes: en una misma réplica TODOS los escenarios ven
  exactamente los mismos clientes (llegadas, tipos, tiempos de servicio y el
  sorteo de asignación), de modo que las diferencias entre escenarios se deben
  solo a la configuración de cajas.

Uso
---
    python simulacion_banco.py            # pilotos + réplicas necesarias
    python simulacion_banco.py --replicas 30
"""
from __future__ import annotations

import argparse
import json
import math
from pathlib import Path

import numpy as np
import pandas as pd
from scipy import stats

# --------------------------------------------------------------------------
# Parámetros del enunciado (Tablas 1 y 2)
# --------------------------------------------------------------------------
HORIZONTE = 8 * 60                      # minutos de operación por día
P_ACCION = {"Retiro": 0.70, "Pago": 0.30}
NIVELES = ["Rápido", "Normal", "Lento", "Muy lento"]
P_NIVEL = {
    "Retiro": [0.23, 0.40, 0.17, 0.20],
    "Pago":   [0.10, 0.20, 0.30, 0.40],
}
MEDIA_SERVICIO = {
    "Retiro": [1, 2, 3, 4],
    "Pago":   [3, 3, 5, 7],
}
MEDIA_LLEGADA = {
    "Retiro": [1, 2, 3, 3],
    "Pago":   [1, 2, 3, 4],
}
# Los 8 tipos de usuario, en un orden fijo: índice 0-3 retiros, 4-7 pagos.
TIPOS = [(a, n) for a in ("Retiro", "Pago") for n in NIVELES]
ETIQUETA = [f"{a} - {n}" for a, n in TIPOS]
P_TIPO = np.array([P_ACCION[a] * P_NIVEL[a][NIVELES.index(n)] for a, n in TIPOS])
SERV = np.array([MEDIA_SERVICIO[a][NIVELES.index(n)] for a, n in TIPOS], float)
LLEG = np.array([MEDIA_LLEGADA[a][NIVELES.index(n)] for a, n in TIPOS], float)
ES_RETIRO = np.array([a == "Retiro" for a, _ in TIPOS])

N_REPLICAS_DEFECTO = 1000
UMBRAL_ESPERA = 5.0    # min; criterio de servicio adoptado (ver bitácora D-09)

# Escenarios: nombre -> (cajeros de retiro, cajeros de pago, mixtos, política)
# 'mixto' = todos atienden todo, asignación aleatoria uniforme (M/M/1 puros).
ESCENARIOS = {
    "E1 3 mixtas":            dict(mixtas=3, retiro=0, pago=0, politica="aleatoria"),
    "E2 1 retiro + 2 pagos":  dict(mixtas=0, retiro=1, pago=2, politica="aleatoria"),
    "E3 2 retiros + 1 pago":  dict(mixtas=0, retiro=2, pago=1, politica="aleatoria"),
    "E4 4 mixtas":            dict(mixtas=4, retiro=0, pago=0, politica="aleatoria"),
    "E5 2 retiros + 2 pagos": dict(mixtas=0, retiro=2, pago=2, politica="aleatoria"),
    "S1 3 mixtas (fila más corta)": dict(mixtas=3, retiro=0, pago=0, politica="mas_corta"),
}


# --------------------------------------------------------------------------
# Generación de la demanda de un día (común a todos los escenarios)
# --------------------------------------------------------------------------
def generar_dia(semilla: int) -> pd.DataFrame:
    rng = np.random.default_rng(semilla)
    filas, t = [], 0.0
    while True:
        tipo = rng.choice(8, p=P_TIPO)             # acción + nivel (Tablas 1-2)
        t += rng.exponential(LLEG[tipo])           # llegada con la media del tipo
        if t > HORIZONTE:
            break
        filas.append((t, tipo, rng.exponential(SERV[tipo]), rng.random()))
    return pd.DataFrame(filas, columns=["llegada", "tipo", "servicio", "u"])


# --------------------------------------------------------------------------
# Simulación de un escenario sobre una demanda dada
# --------------------------------------------------------------------------
def simular_escenario(demanda: pd.DataFrame, cfg: dict) -> pd.DataFrame:
    """Devuelve un registro por cliente (espera, servicio, cajero...)."""
    # Lista de cajeros: (nombre, atiende) donde atiende ∈ {mixto, retiro, pago}
    cajeros = ([("mixto", i) for i in range(cfg["mixtas"])]
               + [("retiro", i) for i in range(cfg["retiro"])]
               + [("pago", i) for i in range(cfg["pago"])])
    nombres = [f"C{i + 1}" + ("" if k == "mixto" else f" ({k})")
               for i, (k, _) in enumerate(cajeros)]
    libre = np.zeros(len(cajeros))                  # instante en que queda libre
    fin_pend = [[] for _ in cajeros]                # finales de clientes en el cajero

    out = []
    for t, tipo, s, u in demanda.itertuples(index=False):
        tipo = int(tipo)
        accion = "retiro" if ES_RETIRO[tipo] else "pago"
        elegibles = [i for i, (k, _) in enumerate(cajeros) if k in ("mixto", accion)]
        if cfg["politica"] == "mas_corta":
            # nº de clientes en el sistema de cada cajero al instante t
            en_sis = [sum(f > t for f in fin_pend[i]) for i in elegibles]
            menor = min(en_sis)
            cand = [i for i, n in zip(elegibles, en_sis) if n == menor]
            c = cand[int(u * len(cand)) % len(cand)]
        else:                                        # asignación aleatoria uniforme
            c = elegibles[min(int(u * len(elegibles)), len(elegibles) - 1)]
        inicio = max(t, libre[c])
        fin = inicio + s
        libre[c] = fin
        fin_pend[c].append(fin)
        out.append((t, tipo, c, inicio - t, s, fin - t, fin))
    df = pd.DataFrame(out, columns=["llegada", "tipo", "cajero", "espera",
                                    "servicio", "sistema", "fin"])
    df.attrs["nombres"] = nombres
    return df


def resumir_replica(df: pd.DataFrame) -> dict:
    nombres = df.attrs["nombres"]
    n = len(df)
    res = {
        "n_clientes": n,
        "Wq": df.espera.mean(),
        "W": df.sistema.mean(),
        "Ws": df.servicio.mean(),
        "Wq_max": df.espera.max(),
        "P_espera_gt": (df.espera > UMBRAL_ESPERA).mean(),
        "Lq": n / HORIZONTE * df.espera.mean(),     # Ley de Little (λ̂·Wq)
    }
    for k in range(8):
        sub = df[df.tipo == k]
        res[f"n_t{k}"] = len(sub)
        res[f"Wq_t{k}"] = sub.espera.mean() if len(sub) else np.nan
        res[f"Ws_t{k}"] = sub.servicio.mean() if len(sub) else np.nan
    res["Wq_retiro"] = df[ES_RETIRO[df.tipo.values]].espera.mean()
    res["Wq_pago"] = df[~ES_RETIRO[df.tipo.values]].espera.mean()
    for i, nom in enumerate(nombres):
        sub = df[df.cajero == i]
        cierre = max(HORIZONTE, sub.fin.max()) if len(sub) else HORIZONTE
        res[f"n_c{i}"] = len(sub)
        res[f"Ws_c{i}"] = sub.servicio.mean() if len(sub) else np.nan
        res[f"Wq_c{i}"] = sub.espera.mean() if len(sub) else np.nan
        res[f"W_c{i}"] = sub.sistema.mean() if len(sub) else np.nan
        res[f"rho_c{i}"] = sub.servicio.sum() / cierre
    return res


# --------------------------------------------------------------------------
# Estadística
# --------------------------------------------------------------------------
def ic95(x) -> tuple[float, float, float]:
    x = np.asarray(x, float)
    x = x[~np.isnan(x)]
    m, n = x.mean(), len(x)
    if n < 2:
        return m, np.nan, np.nan
    h = stats.t.ppf(0.975, n - 1) * x.std(ddof=1) / math.sqrt(n)
    return m, m - h, m + h


def replicas_necesarias(x_piloto, error: float) -> int:
    """n tal que la semi-amplitud del IC95 sea ≤ error (fórmula t·s/√n)."""
    x = np.asarray(x_piloto, float)
    n0, s = len(x), x.std(ddof=1)
    n = n0
    while stats.t.ppf(0.975, n - 1) * s / math.sqrt(n) > error:
        n += 1
        if n > 5000:
            break
    return n


# --------------------------------------------------------------------------
# Ejecución completa
# --------------------------------------------------------------------------
def ejecutar(n_replicas: int, semilla_base: int = 0):
    registros, por_cliente = [], []
    for r in range(1, n_replicas + 1):
        demanda = generar_dia(semilla_base + r)
        for nombre, cfg in ESCENARIOS.items():
            df = simular_escenario(demanda, cfg)
            fila = resumir_replica(df)
            fila.update(replica=r, escenario=nombre)
            registros.append(fila)
            if nombre == "E1 3 mixtas":
                d = df.copy()
                d["replica"] = r
                por_cliente.append(d)
    return pd.DataFrame(registros), pd.concat(por_cliente, ignore_index=True)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--replicas", type=int, default=None,
                    help="fuerza el nº de réplicas (por defecto: las necesarias)")
    ap.add_argument("--salida", default=str(Path(__file__).parent / "resultados"))
    args = ap.parse_args()
    out = Path(args.salida)
    out.mkdir(parents=True, exist_ok=True)

    # 1) Piloto de 10 réplicas -> nº de réplicas necesarias --------------------
    piloto, _ = ejecutar(10)
    p = piloto.pivot(index="replica", columns="escenario", values="Wq")
    n_req = {
        "Wq E1 (±0,25 min)": replicas_necesarias(p["E1 3 mixtas"], 0.25),
        "Wq E2 (±0,25 min)": replicas_necesarias(p["E2 1 retiro + 2 pagos"], 0.25),
        "Wq E3 (±0,25 min)": replicas_necesarias(p["E3 2 retiros + 1 pago"], 0.25),
        "dif. E2-E3 (±0,25 min)": replicas_necesarias(
            p["E2 1 retiro + 2 pagos"] - p["E3 2 retiros + 1 pago"], 0.25),
    }
    # Se usan 1000 réplicas por defecto: supera con holgura el mínimo del piloto
    # (max(n_req.values())) y estrecha los intervalos de confianza (bitácora D-11).
    n_final = args.replicas or max(N_REPLICAS_DEFECTO, max(n_req.values()))
    print("Réplicas necesarias según el piloto:", n_req, "-> se usan", n_final)

    # 2) Corrida final -------------------------------------------------------
    res, clientes = ejecutar(n_final)
    res.to_csv(out / "metricas_por_replica_y_escenario.csv", index=False)
    clientes.to_csv(out / "clientes_E1.csv", index=False)

    resumen = {"n_replicas": n_final, "piloto_requeridas": n_req}

    # Punto 1: tiempo de atención por cajero (E1) --------------------------------
    e1 = res[res.escenario == "E1 3 mixtas"]
    p1 = []
    for i in range(3):
        m, lo, hi = ic95(e1[f"Ws_c{i}"])
        mw, lw, hw = ic95(e1[f"Wq_c{i}"])
        mt, lt, ht = ic95(e1[f"W_c{i}"])
        p1.append(dict(cajero=f"C{i + 1}", n_prom=e1[f"n_c{i}"].mean(),
                       servicio=m, servicio_lo=lo, servicio_hi=hi,
                       espera=mw, espera_lo=lw, espera_hi=hw,
                       sistema=mt, sistema_lo=lt, sistema_hi=ht,
                       rho=e1[f"rho_c{i}"].mean()))
    p1 = pd.DataFrame(p1)
    p1.to_csv(out / "punto1_cajeros.csv", index=False)
    resumen["p1"] = p1.to_dict("records")
    resumen["p1_min"] = p1.loc[p1.servicio.idxmin(), "cajero"]
    resumen["p1_max"] = p1.loc[p1.servicio.idxmax(), "cajero"]
    # ¿las diferencias entre cajeros son reales? (bloques = réplicas)
    resumen["p1_friedman_p"] = float(stats.friedmanchisquare(
        e1["Ws_c0"], e1["Ws_c1"], e1["Ws_c2"]).pvalue)
    resumen["p1_friedman_p_sistema"] = float(stats.friedmanchisquare(
        e1["W_c0"], e1["W_c1"], e1["W_c2"]).pvalue)
    # cajero más lento/rápido por réplica
    ws = e1[["Ws_c0", "Ws_c1", "Ws_c2"]].values
    resumen["p1_veces_min"] = np.bincount(ws.argmin(1), minlength=3).tolist()
    resumen["p1_veces_max"] = np.bincount(ws.argmax(1), minlength=3).tolist()
    resumen["p1_teorico_servicio"] = float((P_TIPO * SERV).sum())

    # Punto 2: promedio de usuarios por tipo (todos los cajeros, E1) --------------
    p2 = []
    for k in range(8):
        m, lo, hi = ic95(e1[f"n_t{k}"])
        p2.append(dict(tipo=ETIQUETA[k], promedio=m, lo=lo, hi=hi,
                       desv=e1[f"n_t{k}"].std(ddof=1),
                       esperado=P_TIPO[k] * HORIZONTE / (P_TIPO * LLEG).sum()))
    p2 = pd.DataFrame(p2)
    p2.to_csv(out / "punto2_usuarios_por_tipo.csv", index=False)
    resumen["p2"] = p2.to_dict("records")
    resumen["p2_total_prom"] = float(e1.n_clientes.mean())

    # Punto 3: totales por tipo y réplica ----------------------------------------
    p3 = e1[["replica"] + [f"n_t{k}" for k in range(8)] + ["n_clientes"]].copy()
    p3.columns = ["Réplica"] + ETIQUETA + ["Total"]
    p3.to_csv(out / "punto3_usuarios_por_replica.csv", index=False)
    resumen["p3_replica_min_total"] = int(p3.loc[p3.Total.idxmin(), "Réplica"])
    resumen["p3_min_total"] = int(p3.Total.min())
    resumen["p3_replica_max_total"] = int(p3.loc[p3.Total.idxmax(), "Réplica"])
    resumen["p3_max_total"] = int(p3.Total.max())
    resumen["p3_min_por_tipo"] = {
        et: dict(replica=int(p3.loc[p3[et].idxmin(), "Réplica"]), n=int(p3[et].min()))
        for et in ETIQUETA}
    resumen["p3_filas"] = p3.to_dict("records")

    # Comparación de escenarios (Puntos 4 y 5) -----------------------------------
    comp = []
    for nombre in ESCENARIOS:
        s = res[res.escenario == nombre]
        fila = dict(escenario=nombre)
        for col, et in [("Wq", "Wq"), ("W", "W"), ("Wq_retiro", "Wq_retiro"),
                        ("Wq_pago", "Wq_pago"), ("P_espera_gt", "P_espera"),
                        ("Lq", "Lq"), ("Wq_max", "Wq_max")]:
            m, lo, hi = ic95(s[col])
            fila[et], fila[et + "_lo"], fila[et + "_hi"] = m, lo, hi
        rho_cols = [c for c in s.columns if c.startswith("rho_c") and s[c].notna().any()]
        fila["rho_prom"] = float(s[rho_cols].mean().mean())
        fila["rho_max"] = float(s[rho_cols].mean().max())
        for k in range(8):
            fila[f"Wq_t{k}"] = s[f"Wq_t{k}"].mean()
        comp.append(fila)
    comp = pd.DataFrame(comp)
    comp.to_csv(out / "comparacion_escenarios.csv", index=False)
    resumen["comparacion"] = comp.to_dict("records")

    # Diferencias pareadas (mismos clientes) -------------------------------------
    def pareada(a, b, col="Wq"):
        d = (res[res.escenario == a].set_index("replica")[col]
             - res[res.escenario == b].set_index("replica")[col])
        m, lo, hi = ic95(d)
        t, pv = stats.ttest_1samp(d, 0.0)
        return dict(a=a, b=b, col=col, dif=m, lo=lo, hi=hi, p=float(pv),
                    a_mejor_en=int((d < 0).sum()), n=len(d))

    resumen["pareadas"] = [
        pareada("E2 1 retiro + 2 pagos", "E3 2 retiros + 1 pago", "Wq"),
        pareada("E2 1 retiro + 2 pagos", "E3 2 retiros + 1 pago", "W"),
        pareada("E2 1 retiro + 2 pagos", "E3 2 retiros + 1 pago", "P_espera_gt"),
        pareada("E2 1 retiro + 2 pagos", "E1 3 mixtas", "Wq"),
        pareada("E3 2 retiros + 1 pago", "E1 3 mixtas", "Wq"),
        pareada("E4 4 mixtas", "E1 3 mixtas", "Wq"),
        pareada("E1 3 mixtas", "S1 3 mixtas (fila más corta)", "Wq"),
        pareada("E5 2 retiros + 2 pagos", "E4 4 mixtas", "Wq"),
    ]

    # Verificación contra teoría -------------------------------------------------
    lam = 1.0 / (P_TIPO * LLEG).sum()           # clientes/min (mezcla de llegadas)
    es = (P_TIPO * SERV).sum()
    es2 = (P_TIPO * 2 * SERV ** 2).sum()        # E[S²] de mezcla exponencial
    def pk(lam_c, es_c, es2_c):                  # Pollaczek-Khinchine M/G/1
        rho = lam_c * es_c
        return lam_c * es2_c / (2 * (1 - rho)) if rho < 1 else float("inf")
    # Mezcla de tipos que llega a un cajero mixto (λ/3, mismas proporciones)
    teor = dict(lambda_total=lam, servicio_medio=es, rho_mixto=lam / 3 * es,
                Wq_E1_teorico=pk(lam / 3, es, es2))
    # Cajas especializadas
    for nm, mask in (("retiro", ES_RETIRO), ("pago", ~ES_RETIRO)):
        pa = P_TIPO[mask].sum()
        lam_a = lam * pa
        es_a = (P_TIPO[mask] * SERV[mask]).sum() / pa
        es2_a = (P_TIPO[mask] * 2 * SERV[mask] ** 2).sum() / pa
        teor[f"lambda_{nm}"] = lam_a
        teor[f"servicio_{nm}"] = es_a
        teor[f"carga_{nm}"] = lam_a * es_a                 # Erlangs ofrecidos
        teor[f"Wq_{nm}_1caja"] = pk(lam_a, es_a, es2_a)
        teor[f"Wq_{nm}_2cajas"] = pk(lam_a / 2, es_a, es2_a)
        teor[f"Wq_{nm}_3cajas"] = pk(lam_a / 3, es_a, es2_a)
    teor["Wq_E2_teorico"] = (teor["lambda_retiro"] * teor["Wq_retiro_1caja"]
                             + teor["lambda_pago"] * teor["Wq_pago_2cajas"]) / lam
    teor["Wq_E3_teorico"] = (teor["lambda_retiro"] * teor["Wq_retiro_2cajas"]
                             + teor["lambda_pago"] * teor["Wq_pago_1caja"]) / lam
    teor["Wq_E4_teorico"] = pk(lam / 4, es, es2)
    # Escenario alterno descartado: 8 flujos independientes
    lam_ind = (1.0 / LLEG).sum()
    teor["alt_independientes_lambda"] = lam_ind
    teor["alt_independientes_carga"] = float((SERV / LLEG).sum())
    resumen["teoria"] = teor

    with open(out / "resumen.json", "w", encoding="utf-8") as f:
        json.dump(resumen, f, ensure_ascii=False, indent=2, default=float)

    # Excel con todo -------------------------------------------------------------
    with pd.ExcelWriter(out / "resultados_simulacion_banco.xlsx") as xw:
        p1.to_excel(xw, "P1 cajeros", index=False)
        p2.to_excel(xw, "P2 usuarios por tipo", index=False)
        p3.to_excel(xw, "P3 usuarios por replica", index=False)
        comp.to_excel(xw, "P4-P5 escenarios", index=False)
        res.to_excel(xw, "Metricas por replica", index=False)
    graficar(res, p1, p2, comp, out)
    print("Listo. Resultados en", out)


def graficar(res, p1, p2, comp, out):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    # (1) tiempo de atención por cajero
    fig, ax = plt.subplots(figsize=(6, 4))
    err = [p1.servicio - p1.servicio_lo, p1.servicio_hi - p1.servicio]
    ax.bar(p1.cajero, p1.servicio, yerr=err, capsize=5, color="#2F6690")
    ax.set_ylabel("Tiempo medio de atención (min)")
    ax.set_title("Punto 1 - Tiempo de atención por cajero (E1, IC 95 %)")
    ax.set_ylim(p1.servicio_lo.min() * 0.9, p1.servicio_hi.max() * 1.05)
    fig.tight_layout(); fig.savefig(out / "fig1_cajeros.png", dpi=150); plt.close(fig)

    # (2) usuarios por tipo
    fig, ax = plt.subplots(figsize=(8, 4))
    ax.bar(range(8), p2.promedio, yerr=[p2.promedio - p2.lo, p2.hi - p2.promedio],
           capsize=4, color=["#2F6690"] * 4 + ["#D1495B"] * 4)
    ax.set_xticks(range(8)); ax.set_xticklabels(ETIQUETA, rotation=35, ha="right")
    ax.set_ylabel("Usuarios por día (promedio)")
    ax.set_title("Punto 2 - Usuarios promedio por tipo (E1, IC 95 %)")
    fig.tight_layout(); fig.savefig(out / "fig2_usuarios_tipo.png", dpi=150); plt.close(fig)

    # (3) espera por escenario
    fig, ax = plt.subplots(figsize=(9, 4.5))
    c = comp.copy()
    ax.bar(range(len(c)), c.Wq, yerr=[c.Wq - c.Wq_lo, c.Wq_hi - c.Wq], capsize=4,
           color="#3A7D44")
    ax.axhline(UMBRAL_ESPERA, ls="--", color="gray")
    ax.text(len(c) - 0.5, UMBRAL_ESPERA + 0.1, f"umbral {UMBRAL_ESPERA:g} min",
            ha="right", color="gray")
    ax.set_xticks(range(len(c)))
    ax.set_xticklabels([s.replace(" ", "\n", 1) for s in c.escenario], fontsize=8)
    ax.set_ylabel("Espera media en cola Wq (min)")
    ax.set_title("Puntos 4 y 5 - Espera media por escenario (IC 95 %)")
    fig.tight_layout(); fig.savefig(out / "fig3_escenarios.png", dpi=150); plt.close(fig)

    # (4) espera retiros vs pagos en E2 / E3
    fig, ax = plt.subplots(figsize=(6.5, 4))
    sel = comp[comp.escenario.isin(["E1 3 mixtas", "E2 1 retiro + 2 pagos",
                                    "E3 2 retiros + 1 pago"])]
    x = np.arange(len(sel)); w = 0.38
    ax.bar(x - w / 2, sel.Wq_retiro, w, label="Retiros", color="#2F6690")
    ax.bar(x + w / 2, sel.Wq_pago, w, label="Pagos", color="#D1495B")
    ax.set_xticks(x); ax.set_xticklabels([s.replace(" ", "\n", 1) for s in sel.escenario],
                                         fontsize=8)
    ax.set_ylabel("Espera media (min)"); ax.legend()
    ax.set_title("Punto 5 - Espera por tipo de operación")
    fig.tight_layout(); fig.savefig(out / "fig4_retiro_vs_pago.png", dpi=150); plt.close(fig)


if __name__ == "__main__":
    main()
