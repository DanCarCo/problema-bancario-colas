# Bitácora de decisiones — Problema bancario (Actividad didáctica 2-M3)

Registro de las decisiones de modelado, método y análisis tomadas al resolver el caso del
Banco de Colombia. Cada entrada indica el contexto, las alternativas, la decisión, su
justificación y la evidencia (o el estado) asociada.

**Fuentes usadas:** `Instrucciones.pdf` (enunciado + rúbrica de Canvas, fuente de verdad),
`SEMANA 6/Laboratorio - Problema Bancario.html` (guía del laboratorio) y material de teoría
de colas de la semana 6.
**Código:** `simulacion_banco.py` · **Resultados:** `resultados/` (CSV, Excel, figuras, `resumen.json`).

> Estado de los pendientes al final del documento.

---

## A. Interpretación del enunciado

### D-01 · Jerarquía de fuentes
- **Contexto:** el PDF (Canvas) y la guía HTML coinciden en datos pero difieren en la
  rúbrica y en detalles de entrega (la guía pide `Apellido_Nombre_problemaBancario`, portada,
  índice y anexos; la rúbrica de Canvas pondera además video y repositorio GitHub).
- **Decisión:** el PDF manda; la guía se usa como complemento (datos, formato sugerido, escenarios).
- **Justificación:** es lo que califica el asesor. Cumplir ambos no es contradictorio.
- **Efecto:** el informe tendrá Introducción, Metodología, Resultados y Conclusiones (PDF) más
  portada, índice y anexos (guía).

### D-02 · "Cajero electrónico" en la rúbrica = cajero (caja) adicional
- **Contexto:** el criterio "Análisis del caso" dice "crear un nuevo cajero electrónico", pero el
  enunciado aclara que el banco **no** tiene cajeros electrónicos y habla de "cajas".
- **Decisión:** se interpreta como agregar una **cuarta caja** atendida por una persona.
- **Justificación:** coherencia con el enunciado ("nuevo cajero" en el punto 4).

### D-03 · Cómo se generan las llegadas (decisión crítica)
- **Contexto:** la Tabla 1 da una media de llegada por cada uno de los 8 tipos de usuario y la
  Tabla 2 da probabilidades de tipo. Hay dos lecturas posibles:
  1. **8 flujos de Poisson independientes**, cada uno con su media de llegada.
  2. **Un solo flujo** donde cada cliente toma un tipo con la probabilidad de la Tabla 2 y el
     tiempo hasta su llegada es Exp(media de llegada de ese tipo) (así lo hace el código de la guía).
- **Decisión:** lectura 2.
- **Justificación (evidencia):** con la lectura 1 la tasa total sería 4,25 clientes/min y la carga
  ofrecida 12,25 Erlangs, es decir, **imposible de atender con 3 cajeros** (se necesitarían ≥13).
  Además la lectura 1 volvería innecesaria la Tabla 2 y el dato del 70 %/30 %. La lectura 2
  usa todos los datos y da un sistema estable: λ = 0,417 clientes/min (un cliente cada 2,40 min),
  servicio medio 3,198 min, ρ = 0,444 por cajero.
- **Limitación aceptada:** en la lectura 2 el tipo del cliente y el intervalo previo a su llegada están
  correlacionados, así que el proceso no es Poisson puro; se usa como aproximación del enunciado.

### D-04 · Probabilidades de tipo
- **Decisión:** probabilidad conjunta = P(acción) × P(nivel | acción): retiros 0,70 × (0,23; 0,40; 0,17; 0,20)
  y pagos 0,30 × (0,10; 0,20; 0,30; 0,40). Cada fila de la Tabla 2 suma 1,00 (verificado).
- **Justificación:** la nota de la guía lo exige ("el 70 % de *todos* los usuarios hacen retiros").
- **Evidencia:** el promedio simulado de usuarios por tipo coincide con el esperado (Punto 2).

---

## B. Modelado

### D-05 · Cajeros = tres colas M/M/1 **independientes**, asignación aleatoria uniforme
- **Contexto:** el enunciado exige modelar los cajeros "como M/M/1, pues son independientes". El
  código de ejemplo de la guía, en cambio, usa **una sola fila** compartida y asigna al primer cajero
  libre (eso es M/M/3, no tres M/M/1).
- **Alternativas:** (a) fila única M/M/c; (b) 3 filas con asignación aleatoria uniforme; (c) 3 filas,
  el cliente elige la fila más corta.
- **Decisión:** (b) como caso base (E1); (c) solo como análisis de sensibilidad (S1).
- **Justificación:** (b) es literalmente 3 M/M/1 con tasa λ/3 cada una (descomposición de Poisson) y
  es lo que pide el enunciado.
- **Evidencia/impacto:** la política (c) reduce la espera media de 3,39 a 0,79 min (−2,60 min, IC95 % [2,53; 2,67]).
  Esto es un hallazgo en sí mismo (ver D-17).
- **No se reutilizó el código de la guía** por esta discrepancia y porque era solo un esqueleto.

### D-06 · Horizonte, arranque y cierre
- **Decisión:** 480 min por réplica; el sistema parte vacío; llegan clientes hasta el minuto 480 y los
  que quedan en el banco al cierre **se terminan de atender**.
- **Justificación:** un banco no expulsa clientes que ya están dentro; descartarlos sesgaría a la baja
  esperas y usuarios. Parte vacío porque el enunciado habla de "un solo día".
- **Efecto conocido:** el arranque vacío subestima ligeramente la espera frente a la teoría de régimen
  estacionario (ver D-15).

### D-07 · Disciplina de cola
- **Decisión:** FIFO por cajero, sin abandono ni cambio de fila (jockeying), servicio sin interrupción.
- **Justificación:** es el supuesto estándar de M/M/1; el enunciado no menciona abandonos.

### D-08 · Desplazamiento e inicio de atención
- **Decisión:** desplazamiento y cambio entre clientes = 0 min; velocidad de atención idéntica entre cajeros.
- **Justificación:** lo indica el enunciado ("inmediata … despreciable").

### D-09 · Números aleatorios comunes y semillas
- **Decisión:** en la réplica *r* se usa la semilla *r* (`numpy.random.default_rng(r)`) y **todos los
  escenarios reciben exactamente los mismos clientes** (llegadas, tipos, tiempos de servicio y sorteo de asignación).
- **Justificación:** (i) reproducibilidad exacta; (ii) las comparaciones entre escenarios son pareadas, lo
  que reduce mucho la varianza de las diferencias.
- **Consecuencia importante:** los conteos de usuarios por réplica son iguales en todos los escenarios,
  de modo que "el modelo con menos usuarios" del Punto 3 solo puede significar **la réplica** (ver D-13).

---

## C. Método estadístico

### D-10 · Qué es "tiempo promedio de atención"
- **Decisión:** el indicador principal es el **tiempo de servicio** del cajero (lo que usa la guía en su
  `groupby('cajero')['tiempo_servicio']`). Se reportan además espera en cola (Wq) y tiempo en el sistema (W).
- **Justificación:** "atención" ≈ tiempo que el cajero dedica al cliente; la espera se usa para el Punto 4.

### D-11 · Número de réplicas
- **Contexto:** el enunciado pide "al menos 10"; la rúbrica pide "detallar la cantidad de réplicas necesarias".
- **Método:** piloto de 10 réplicas y fórmula t·s/√n ≤ e, con e = 0,25 min, para (a) Wq de E1, E2, E3 y
  (b) la diferencia pareada E2−E3.
- **Resultado del piloto:** E1 → 42; E2 → 347; E3 → 120; diferencia E2−E3 → **434** (el mínimo necesario).
- **Decisión final (a pedido del usuario):** **1000 réplicas** en la corrida final. Supera con holgura el mínimo de 434
  y estrecha los intervalos (la diferencia E2−E3 pasó de ±0,33 a ±0,21 min). El script usa 1000 por defecto y lo
  ajusta hacia arriba si el piloto exigiera más. Las 434 réplicas previas quedaron reemplazadas, no se mezclaron.
- **Costo:** la simulación tarda segundos; la tabla por réplica (Punto 3) va completa en el Excel y en el informe se
  mostrarán las 10 primeras (piloto) más los extremos.
- **Por qué no solo 10:** con 10 réplicas la semiamplitud de Wq en E2 sería muy grande y no permitiría decidir.
- **Nota:** las conclusiones no cambiaron entre 434 y 1000 réplicas; sí cambiaron los extremos del Punto 1 y 3 (ver D-13),
  lo que confirma que son ruido.

### D-12 · Pruebas e intervalos
- **Decisión:** IC95 % con la *t* de Student sobre los promedios por réplica; diferencias entre escenarios con
  *t* pareada; comparación de cajeros con la prueba de Friedman (bloques = réplicas).
- **Justificación:** las réplicas son independientes; Friedman no exige normalidad ni igualdad de varianzas.

---

## D. Respuesta a cada punto

### D-13 · Puntos 1–3 (interpretación y resultado)
- **Punto 1 — cajero con menor y mayor tiempo de atención.** *Decisión:* calcular el tiempo de servicio medio de
  cada cajero en E1 y señalar el mínimo y el máximo, pero **declarar que la diferencia no es significativa**.
  *Resultado (1000 réplicas):* C1 el menor (3,202 min), C2 el mayor (3,214 min); diferencia de 0,012 min; Friedman
  p = 0,83. Los tres cajeros son idénticos por supuesto (D-08), así que el "mejor" y el "peor" cambian de una réplica
  a otra (C1 fue el más rápido en 327, C2 en 322 y C3 en 351 de las 1000). Con 434 réplicas habían salido C3 y C1:
  el ranking cambia con la muestra, prueba de que es azar. Valor teórico: 3,198 min.
  *Justificación:* reportar el mínimo/máximo como si fueran reales sería engañoso; se cumple lo pedido y se
  advierte la limitación.
- **Punto 2 — promedio de usuarios por tipo en todos los cajeros.** *Decisión:* promedio diario por cada uno de
  los 8 tipos (más total) con IC95 %. *Resultado:* 201,0 usuarios/día en total; coincide con el valor esperado
  (p. ej. Retiro-Normal 56,6 vs 56,1 esperado).
- **Punto 3 — total por tipo en cada réplica y "modelo con menor cantidad de usuarios por tipo".**
  *Decisión:* tabla completa por réplica; se identifica la **réplica** con menos usuarios en total y por tipo.
  *Resultado:* de las 1000, la réplica 904 tiene el menor total (139); entre las 10 réplicas del piloto, la menor
  es la 4 (200). Pagos-Rápido llega a 0 usuarios en la réplica 303.
  *Justificación de la lectura:* por D-09 los escenarios comparten clientes, así que solo las réplicas difieren.

### D-14 · Punto 4 — ¿hace falta un nuevo cajero?
- **Criterios definidos (el enunciado dice "todos los criterios del modelo" sin fijarlos):**
  Wq medio ≤ 5 min (umbral **supuesto por nosotros**, no del enunciado), utilización < 85 %, Wq por tipo y
  P(espera > 5 min).
- **Resultado en E1 (3 cajas):** Wq = 3,39 min (IC95 % [3,30; 3,48]); W = 6,59 min; Lq = 1,43 clientes; ρ = 0,444;
  P(espera > 5 min) = 21,8 %. Con 4 cajas (E4): Wq = 2,13 min, ρ = 0,334, P = 14,3 %.
- **Decisión:** **no es necesario** crear un cajero nuevo: el sistema es estable, con ρ = 44 %, y la espera
  media cumple el umbral. Un cuarto cajero reduciría la espera 1,26 min (−37 %, IC95 % [1,20; 1,31]) pero
  dejaría las cajas al 33 % de uso.
- **Sensibilidad (se debe decir en el informe):** la conclusión depende del umbral. Si el banco exigiera, por ejemplo,
  P(espera > 5 min) < 15 %, entonces el cuarto cajero sí sería necesario. Y existe una mejora sin costo: que el
  cliente elija la fila más corta (S1, Wq = 0,79 min), más efectiva que un cajero extra.

### D-15 · Punto 5 — cajas exclusivas
- **Escenarios comparados:** E2 (1 retiro + 2 pagos) y E3 (2 retiros + 1 pago), con diferencias pareadas.
- **Criterio principal:** menor espera media ponderada por cliente (Wq), con P(espera>5 min) y espera por tipo de
  operación como criterios de apoyo.
- **Resultado:** E3 gana: Wq 3,87 vs 5,24 min (diferencia 1,37 min, IC95 % [1,16; 1,58]); P(espera>5) 20,7 % vs
  32,8 %. Cargas ofrecidas: retiros 0,683 Erlangs, pagos 0,651.
- **Decisión:** **2 cajeros para retiros y 1 para pagos.**
- **Costo de la decisión (se debe decir):** en E3 los pagos esperan 8,99 min de media frente a 1,58 de los retiros;
  gana en promedio porque el 70 % de los clientes hace retiros. Además, **ninguna** configuración especializada
  supera a las 3 cajas mixtas (E1: 3,39 min), por el efecto de agrupar recursos.
- **Si se contrata un cuarto cajero:** la mejor es 2 retiros + 2 pagos (E5: 1,89 min), ligeramente mejor que
  4 mixtas (2,13 min).

### D-16 · Validación del simulador
- **Decisión:** contrastar con Pollaczek–Khinchine (M/G/1 con servicio hiperexponencial).
- **Resultado:** Wq teórico vs simulado — E1: 3,39 vs 3,39; E4: 2,12 vs 2,13; E2: 5,06 vs 5,24; E3: 4,22 vs 3,87.
- **Lectura honesta:** E1, E4 y E2 coinciden con la teoría dentro de los IC95 %; E3 queda por debajo del valor teórico
  (IC95 % simulado [3,71; 4,04] vs 4,22), es decir, la simulación da algo menos de espera que P–K. Las diferencias se explican por el arranque vacío (D-06) y por que el proceso de llegadas de D-03 no es Poisson puro.

### D-17 · Escenarios extra
- **Decisión:** además de E1–E4 de la guía se agregan **E5** (2+2) y **S1** (fila más corta). 
- **Justificación:** E5 completa la comparación si se agrega un cajero; S1 acota el efecto de la asignación
  aleatoria exigida por el enunciado (D-05).

---

## E. Entrega

### D-18 · Estructura del repositorio y herramientas
- **Decisión:** Python (numpy/pandas/scipy/matplotlib), un único script reproducible con semillas fijas,
  `requirements.txt`, README, `resultados/` versionado y esta bitácora en `docs/`.
- **Justificación:** criterios "Implementación" y "Repositorio en GitHub" de la rúbrica (README, instrucciones,
  archivos y evidencias).

### D-19 · Guion de video
- **Decisión (por indicación del usuario):** **no se redacta aún**. Cuando se haga, deberá apoyarse en D-03, D-05,
  D-11, D-14 y D-15, que son lo que más conviene explicar.

---

## Pendientes y riesgos abiertos

| # | Pendiente | Responsable |
|---|-----------|-------------|
| 1 | Informe en Word/PDF (portada, índice, Introducción, Metodología, Resultados, Conclusiones, Anexos) | por hacer |
| 2 | Nombre del archivo final `Apellido_Nombre_problemaBancario` — falta confirmar apellido/nombre | usuario |
| 3 | Crear/publicar el repositorio en GitHub y pegar el enlace en Canvas | usuario |
| 4 | Guion y grabación del video de sustentación | pospuesto |
| 5 | Confirmar que el umbral de 5 min (D-14) es aceptable para el asesor; si no, ajustar | usuario |
| 6 | Entrega por Canvas: vence el domingo 22 de nov a las 23:59 (2 intentos) | usuario |
