# Desarrollo: Daniel Velazquez
# Configuración geométrica de la celda Festo MPS

# Mapeo de Píxeles vs Coordenadas de Robot (XYZ en mm)
POSICIONES_CELDA = {
    "Posicion_1": {"pixel": (180, 90), "robot": (120, -240, 270)},
    "Posicion_2": {"pixel": (125, 216), "robot": (250, 20, 220)},
    "Posicion_3": {"pixel": (170, 260), "robot": (250, 137, 180)},
    "Posicion_4": {"pixel": (525, 240), "robot": (40, 330, 180)}#,
    #"Posicion_5": {"pixel": (150, 150), "robot": (110, 80, 200)}
}

# Parámetros globales de la celda
TOLERANCIA_PIXELS = 25
AREA_MINIMA_CONTOUT = 300
