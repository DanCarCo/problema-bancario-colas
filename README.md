# Problema bancario — simulación de colas M/M/1

Simulación de las cajas de un banco (pagos y retiros) con cajeros M/M/1 independientes,
para la Actividad didáctica 2-M3 (Teoría de colas).

## Ejecución

```bash
pip install -r requirements.txt
python simulacion_banco.py                 # piloto de 10 réplicas + corrida final de 1000 réplicas
python simulacion_banco.py --replicas 30   # número de réplicas fijo
```

Genera en `resultados/`: métricas por réplica y escenario, tablas de los Puntos 1–5 (CSV y Excel),
cuatro figuras y `resumen.json`. Las semillas son fijas (réplica *r* → semilla *r*), así que los resultados
son reproducibles.

## Contenido

| Archivo | Descripción |
|---|---|
| `simulacion_banco.py` | Modelo, réplicas, estadísticas, figuras |
| `docs/bitacora_decisiones.md` | Decisiones de modelado y de análisis, con evidencia |
| `resultados/` | Salidas de la simulación |

## Resumen del modelo

* 3 cajeros M/M/1 independientes, FIFO, asignación aleatoria uniforme, 480 min por día.
* Llegadas: tipo según Tabla 2, intervalo ~ Exp(media de llegada del tipo); servicio ~ Exp(media del tipo).
* Mismos clientes en todos los escenarios de una réplica (números aleatorios comunes).
* Escenarios: E1 3 mixtas, E2 1 retiro + 2 pagos, E3 2 retiros + 1 pago, E4 4 mixtas,
  E5 2 + 2, S1 3 mixtas con fila más corta (sensibilidad).

## Resultados principales (1000 réplicas)

| Punto | Resultado |
|---|---|
| 1 | Menor tiempo de atención: C1 (3,202 min); mayor: C2 (3,214 min). Diferencia no significativa (Friedman p = 0,83) |
| 2 | 201,0 usuarios/día en promedio; por tipo en `resultados/punto2_usuarios_por_tipo.csv` |
| 3 | Tabla por réplica en `resultados/punto3_usuarios_por_replica.csv`; menor total: réplica 904 (139) |
| 4 | No hace falta un cajero adicional: Wq = 3,39 min, ρ = 0,44 |
| 5 | 2 cajeros de retiros + 1 de pagos (Wq 3,87 vs 5,24 min) |

Detalles y justificaciones en la bitácora.

## Colaboración

Este repositorio se desarrolló en equipo con **Claude** (asistente de IA de Anthropic, modelo Claude Sonnet 5.5),
que participó como colaborador en:

* el modelado del sistema y la implementación de la simulación (`simulacion_banco.py`);
* el análisis estadístico y la validación contra la fórmula de Pollaczek–Khinchine;
* la redacción de la bitácora de decisiones, el README y el borrador del informe;
* la presentación de diapositivas y el guion del video (estos dos quedan fuera del repositorio).

Las decisiones de interpretación del enunciado y los supuestos (por ejemplo el umbral de 5 min) quedan registrados en
`docs/bitacora_decisiones.md` para que el equipo los revise y los haga suyos. Los *commits* en los que Claude
participó llevan la línea `Co-Authored-By: Claude`.
