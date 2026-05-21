# Desarrollo: Daniel Velazquez
# Módulo VLA Autónomo - Multi-ROI y Control Cognitivo por CLI (Ollama)

import cv2
import json
import os
import sys
import subprocess
import numpy as np
import config_estaciones as ce

class ProcesadorVLA:
    def __init__(self, model_name="qwen3-vl:235b-instruct-cloud"):
        """
        Inicialización del pipeline VLA con soporte para optimización de resolución multi-región.
        """
        self.model_name = model_name
        self.output_dir = "capturas_vla"
        
        if not os.path.exists(self.output_dir):
            os.makedirs(self.output_dir)

    def analizar_escena_completa(self, frame):
        """
        Extrae y amplifica las ROIs de todas las posiciones clave de la celda,
        construye un mosaico multiescala etiquetado y ejecuta la inferencia CLI.
        """
        try:
            # Dimensiones de la escena principal en el mosaico
            ancho_escena = 533
            alto_mosaico = 400
            escena_redimensionada = cv2.resize(frame, (ancho_escena, alto_mosaico), interpolation=cv2.INTER_AREA)

            # Lista para almacenar los cuadros de zoom procesados
            zooms_procesados = []
            
            # Recorrer ordenadamente las 4 posiciones configuradas
            for i in range(1, 5):
                pos_id = f"Posicion_{i}"
                pos_x, pos_y = ce.POSICIONES_CELDA[pos_id]["pixel"]
                
                # Ventana de recorte fija de 80x80 píxeles alrededor de cada centroide
                w_h = 40
                ymin, ymax = max(0, pos_y - w_h), min(frame.shape[0], pos_y + w_h)
                xmin, xmax = max(0, pos_x - w_h), min(frame.shape[1], pos_x + w_h)
                
                roi = frame[ymin:ymax, xmin:xmax]
                
                # Redimensionar cada ROI a una caja estándar de 100x100 píxeles para apilarlas verticalmente (4 * 100 = 400 de alto)
                roi_ampliada = cv2.resize(roi, (133, 100), interpolation=cv2.INTER_CUBIC)
                
                # Instrumentar etiqueta visible en cada zoom para guiar la atención del VLA
                cv2.rectangle(roi_ampliada, (0, 0), (133, 100), (0, 255, 255), 1)
                cv2.putText(roi_ampliada, pos_id, (5, 18), 
                            cv2.FONT_HERSHEY_SIMPLEX, 0.4, (0, 255, 255), 1, cv2.LINE_AA)
                
                zooms_procesados.append(roi_ampliada)
            
            # Concatenar verticalmente los 4 bloques de zoom (dimensión final: 133 x 400)
            columna_zooms = np.vstack(zooms_procesados)
            
            # Concatenar horizontalmente: [Escena Completa (533x400) | Columna de Zooms (133x400)] (Total: 666x400)
            mosaico = np.hstack((escena_redimensionada, columna_zooms))
            
        except Exception as e:
            print(f"[VLA PREPROCESAMIENTO ERROR] Fallo al generar el mosaico multi-ROI: {e}", file=sys.stderr)
            # Respaldo de seguridad en caso de fallo de dimensiones en matrices de OpenCV
            mosaico = frame

        # Almacenamiento físico del artefacto visual
        filename = f"{self.output_dir}/analisis_autonomo.jpg"
        absolute_image_path = os.path.abspath(filename)
        cv2.imwrite(filename, mosaico, [int(cv2.IMWRITE_JPEG_QUALITY), 95])

        # Definición de directrices para el razonamiento lógico-espacial con soporte multiescala
        prompt = (
            f"Analiza la siguiente imagen compuesta de la celda de manufactura Festo MPS: {absolute_image_path}\n\n"
            "La imagen está dividida en dos componentes principales:\n"
            "- LADO IZQUIERDO: Vista panorámica de baja resolución que muestra la disposición física global de la celda.\n"
            "- LADO DERECHO: Una columna de cuatro paneles de ZOOM de alta resolución etiquetados individualmente como 'Posicion_1', 'Posicion_2', 'Posicion_3' y 'Posicion_4'.\n\n"
            "Tu tarea de control como agente de manufactura consiste en:\n\n"
            "1. Inspecciona visualmente el panel 'Posicion_1' de la derecha:\n"
            "   - Clasifica el componente presente determinando su color ('rojo', 'azul', 'negro').\n"
            "   - Si el panel muestra únicamente la superficie de la celda sin componentes encima, clasifícalo como 'ninguna'.\n\n"
            "2. Calcula el destino correspondiente de acuerdo a la matriz de ruteo:\n"
            "   - Componente azul  -> 'Posicion_2'\n"
            "   - Componente rojo  -> 'Posicion_3'\n"
            "   - Componente negro -> 'Posicion_4'\n"
            "   - Si no hay pieza ('ninguna') -> El destino debe ser 'Ninguna'.\n\n"
            "3. Inspecciona el panel de zoom de la derecha correspondiente a la posición de destino calculada (por ejemplo, si la pieza es roja, inspecciona el zoom de 'Posicion_3'):\n"
            "   - Si se observa cualquier pieza preexistente en dicho panel de zoom, decláralo como 'ocupada'.\n"
            "   - Si el panel se visualiza vacío, decláralo como 'libre'.\n\n"
            "4. REGLA DE INTERLOCK CRÍTICO:\n"
            "   - Si la pieza en 'Posicion_1' es 'ninguna' -> 'accion_robot' debe ser 'esperar_pieza'.\n"
            "   - Si la posición de destino está 'ocupada' -> 'accion_robot' debe ser estrictamente 'bloquear_por_colision'.\n"
            "   - Si la posición de destino está 'libre' -> 'accion_robot' debe ser 'ejecutar_movimiento'.\n\n"
            "Devuelve tu análisis estrictamente en formato JSON crudo, sin texto aclaratorio adicional ni formato markdown:\n"
            "{\n"
            "  \"pieza_en_posicion_1\": \"rojo\" | \"azul\" | \"negro\" | \"ninguna\",\n"
            "  \"posicion_destino_evaluada\": \"Posicion_2\" | \"Posicion_3\" | \"Posicion_4\" | \"Ninguna\",\n"
            "  \"estado_posicion_destino\": \"libre\" | \"ocupada\",\n"
            "  \"accion_robot\": \"ejecutar_movimiento\" | \"bloquear_por_colision\" | \"esperar_pieza\"\n"
            "}"
        )

        comando = ["ollama", "run", self.model_name, prompt]

        print(f"\n[VLA INFO] Transmitiendo mosaico optimizado [Escena + 4 Zooms Estructurados] a Ollama CLI...", flush=True)
        
        try:
            resultado_cli = subprocess.run(
                comando,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                encoding='utf-8',
                timeout=60
            )

            if resultado_cli.returncode != 0:
                print(f"[VLA ERROR] CLI de Ollama retornó código de error {resultado_cli.returncode}", file=sys.stderr)
                print(f"[DETALLE STDERR]: {resultado_cli.stderr}", file=sys.stderr)
                return None

            raw_content = resultado_cli.stdout.strip()
            
            # Sanitización de bloques de marcado markdown
            if "```json" in raw_content:
                raw_content = raw_content.split("```json")[1].split("```")[0].strip()
            elif "```" in raw_content:
                raw_content = raw_content.split("```")[1].strip()

            return json.loads(raw_content)

        except subprocess.TimeoutExpired:
            print("[VLA ERROR] Tiempo de espera agotado en el subproceso de Ollama.", file=sys.stderr)
            return None
        except json.JSONDecodeError:
            print(f"[VLA ERROR] Error en decodificación de la trama JSON recibida. Contenido crudo:\n{raw_content}", file=sys.stderr)
            return None
        except Exception as e:
            print(f"[VLA ERROR] Excepción inesperada en el subproceso: {e}", file=sys.stderr)
            return None
