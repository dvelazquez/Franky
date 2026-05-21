import numpy as np

# ROJO: Requiere doble máscara por segmentación cíclica en el canal Hue
LOWER_RED1 = np.array([0, 120, 70])
UPPER_RED1 = np.array([10, 255, 255])
LOWER_RED2 = np.array([170, 120, 70])
UPPER_RED2 = np.array([180, 255, 255])

# AZUL: Rango continuo estándar
LOWER_BLUE = np.array([100, 150, 50])
UPPER_BLUE = np.array([140, 255, 255])

# NEGRO: Restricción estricta sobre el canal Value (Luminosidad)
LOWER_BLACK = np.array([0, 0, 0])
UPPER_BLACK = np.array([180, 255, 55])
