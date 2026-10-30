"""Tendencias sobre series anuales: pendiente de Sen y Mann-Kendall.

Se usan en el generador de la malla (`tools/malla_global.py`) y sirven de
referencia para el cálculo que hace el navegador.
"""

import math
from collections import Counter


def sen(valores):
    """Pendiente de Sen: mediana de las pendientes entre todos los pares."""
    if len(valores) < 3:
        return None
    pendientes = []
    for i in range(len(valores) - 1):
        for j in range(i + 1, len(valores)):
            pendientes.append((valores[j] - valores[i]) / (j - i))
    pendientes.sort()
    total = len(pendientes)
    medio = total // 2
    if total % 2:
        return pendientes[medio]
    return (pendientes[medio - 1] + pendientes[medio]) / 2.0


def pendiente_decada(valores):
    """Pendiente de Sen expresada por década (la serie es anual)."""
    pendiente = sen(valores)
    if pendiente is None:
        return None
    return pendiente * 10.0


def mann_kendall(valores):
    """Prueba de Mann-Kendall: devuelve ``(z, p)`` de dos colas.

    Usa la aproximación normal con corrección de continuidad y varianza
    corregida por empates. Con menos de 10 puntos no hay potencia suficiente
    y se devuelve ``None``.
    """
    if len(valores) < 10:
        return None

    n = len(valores)
    s = 0
    for i in range(n - 1):
        for j in range(i + 1, n):
            if valores[j] > valores[i]:
                s += 1
            elif valores[j] < valores[i]:
                s -= 1

    conteos = Counter(valores)
    var = (
        n * (n - 1) * (2 * n + 5)
        - sum(t * (t - 1) * (2 * t + 5) for t in conteos.values())
    ) / 18.0
    if var <= 0:
        return 0.0, 1.0

    if s > 0:
        z = (s - 1) / math.sqrt(var)
    elif s < 0:
        z = (s + 1) / math.sqrt(var)
    else:
        z = 0.0

    p = 2 * (1 - 0.5 * (1 + math.erf(abs(z) / math.sqrt(2))))
    return z, p
