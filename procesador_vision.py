import cv2
import numpy as np
import umbrales_color as uc
import config_estaciones as ce

class ProcesadorVision:
    def __init__(self):
        self.kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (5, 5))

    def _calcular_centroide(self, contour):
        M = cv2.moments(contour)
        if M["m00"] != 0:
            cX = int(M["m10"] / M["m00"])
            cY = int(M["m01"] / M["m00"])
            return cX, cY
        return None

    def procesar_cuadro(self, frame):
        """
        Segmenta el cuadro, detecta contornos y actualiza el estado de la celda.
        Devuelve el frame instrumentado y el diccionario de estado (JSON ready).
        """
        hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)

        # 1. Generación de máscaras binarias utilizando los umbrales atómicos
        m_red = cv2.bitwise_or(
            cv2.inRange(hsv, uc.LOWER_RED1, uc.UPPER_RED1), 
            cv2.inRange(hsv, uc.LOWER_RED2, uc.UPPER_RED2)
        )
        m_blue = cv2.inRange(hsv, uc.LOWER_BLUE, uc.UPPER_BLUE)
        m_black = cv2.inRange(hsv, uc.LOWER_BLACK, uc.UPPER_BLACK)

        # 2. Filtrado morfológico de alta frecuencia
        m_red = cv2.morphologyEx(m_red, cv2.MORPH_CLOSE, self.kernel)
        m_blue = cv2.morphologyEx(m_blue, cv2.MORPH_CLOSE, self.kernel)
        m_black = cv2.morphologyEx(m_black, cv2.MORPH_CLOSE, self.kernel)

        # Inicialización del diccionario de telemetría simbólica
        estado_celda = {
            pos: {"ocupado": False, "color": "ninguno", "robot_xyz": datos["robot"]} 
            for pos, datos in ce.POSICIONES_CELDA.items()
        }

        # Dibujar las regiones de tolerancia cuadráticas de la celda
        for nombre, datos in ce.POSICIONES_CELDA.items():
            ref_x, ref_y = datos["pixel"]
            cv2.rectangle(frame, 
                          (ref_x - ce.TOLERANCIA_PIXELS, ref_y - ce.TOLERANCIA_PIXELS), 
                          (ref_x + ce.TOLERANCIA_PIXELS, ref_y + ce.TOLERANCIA_PIXELS), 
                          (0, 255, 255), 1)
            cv2.putText(frame, nombre, (ref_x - 40, ref_y - ce.TOLERANCIA_PIXELS - 5),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.4, (0, 255, 255), 1)

        # 3. Canales de búsqueda condicional por color
        canales = [
            ("Rojo", m_red, (0, 0, 255)), 
            ("Azul", m_blue, (255, 0, 0)), 
            ("Negro", m_black, (50, 50, 50))
        ]

        for nombre_color, mascara, bgr_color in canales:
            contours, _ = cv2.findContours(mascara, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
            
            for c in contours:
                if cv2.contourArea(c) > ce.AREA_MINIMA_CONTOUT:
                    centroide = self._calcular_centroide(c)
                    if centroide is not None:
                        posX, posY = centroide

                        # Evaluación espacial condicional de coincidencia (Match)
                        for nombre_pos, datos in ce.POSICIONES_CELDA.items():
                            ref_x, ref_y = datos["pixel"]
                            dentro_x = (ref_x - ce.TOLERANCIA_PIXELS) <= posX <= (ref_x + ce.TOLERANCIA_PIXELS)
                            dentro_y = (ref_y - ce.TOLERANCIA_PIXELS) <= posY <= (ref_y + ce.TOLERANCIA_PIXELS)

                            if dentro_x and dentro_y:
                                estado_celda[nombre_pos]["ocupado"] = True
                                estado_celda[nombre_pos]["color"] = nombre_color
                                
                                # Renderizado analítico sobre la imagen
                                cv2.circle(frame, (posX, posY), 6, (0, 255, 0), -1)
                                cv2.rectangle(frame, cv2.boundingRect(c), bgr_color, 2)
                                cv2.putText(frame, f"{nombre_color} en {nombre_pos}", (posX + 15, posY - 15),
                                            cv2.FONT_HERSHEY_SIMPLEX, 0.5, bgr_color, 2)

        return frame, estado_celda
