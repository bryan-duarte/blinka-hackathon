# Blinka Hackathon — Contexto del repositorio

## Entregable

Agente funcionando.

## El reto en una frase

Construir un agente que revise las cuentas de una empresa y decida cuáles pagar por ella, dentro de las reglas que la empresa define, y que le pida permiso a una persona cuando algo se sale de esas reglas.

## Cómo funciona hoy

1. Llega una factura o cuenta de cobro por correo, PDF o chat.
2. Alguien de finanzas la revisa, la compara con lo acordado y busca los datos de quien cobra.
3. Pide aprobación por chat o correo.
4. Entra a la plataforma y crea el pago a mano, muchas veces en otra moneda y hacia otro país.
5. Concilia en una hoja de cálculo qué se pagó y por qué.

Todo eso es manual, se repite cada mes y depende de que una persona esté disponible.

## A quién afecta

Empresas constituidas en EE. UU. que operan en varios países, con equipo, proveedores y contratistas en Latinoamérica y otras regiones. Sus equipos de finanzas hacen decenas de pagos al mes.

## Por qué importa ahora

Cada vez más empresas están armando sus propios agentes y quieren que también se encarguen de pagar. Lo que falta resolver es la confianza: que el agente pague solo lo que debe, explique cada decisión y nunca se pase de los límites que le pusieron.

## Hasta dónde llega el flujo

El reto termina cuando el agente decide qué hacer con cada factura: **pagarla, frenarla o escalarla a una persona**. No hay que mover dinero real ni conectarse a una plataforma de pagos: basta con que el agente tome la decisión, la registre y explique por qué.

## Qué entra y qué no

### Entra

- Leer una factura y extraer a quién, cuánto, en qué moneda y para cuándo.
- Decidir si se paga según reglas configurables: límites por pago y por periodo, beneficiarios permitidos y aprobación humana por encima de cierto monto.
- Dejar un registro de cada decisión: pagó, frenó o escaló, y por qué.

### No entra

- Ejecutar pagos reales o mover dinero.
- Abrir cuentas.
- Verificar la identidad de las empresas.
- Decisiones de cumplimiento o fraude.
- El diseño de la app de Blinka.

## Con qué trabajar

No hay API ni facturas de ejemplo: cada equipo arma su propio set de datos. Se pueden crear facturas simuladas (PDF, imagen, correo o mensaje de chat) o compartirlas entre equipos, junto con las reglas de pago de una empresa ficticia.

Incluir casos normales y casos trampa, por ejemplo:

- Un cobro duplicado.
- Un beneficiario nuevo que no está en la lista permitida.
- Una factura que no cuadra con lo acordado.
- Un monto que supera el límite y necesita aprobación humana.
- Saldo o presupuesto insuficiente para el periodo.
