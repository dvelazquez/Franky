# Desarrollo: Daniel Velazquez
# Orquestador Principal - Control Híbrido con Retrovideofeed de Inferencia e Integración de Brazo Robótico

import cv2
import sys
import json
import os
import config_estaciones as ce
import time
from procesador_vla import ProcesadorVLA
from procesador_vision import ProcesadorVision
from controlador_robot import ControladorRobot  # Integración del nuevo módulo atómico

def main():
    # Inicialización del backend de captura de video V4L2 en Linux
    cap = cv2.VideoCapture(1, cv2.CAP_V4L2)
    if not cap.isOpened():
        print("Error crítico: Interfaz V4L2 no disponible.", file=sys.stderr)
        sys.exit(1)
        
    cap.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc(*'MJPG'))
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)

    # Instanciación de los núcleos de procesamiento y control
    vla_core = ProcesadorVLA()
    vision_local = ProcesadorVision()
    robot_control = ControladorRobot(port='/dev/ttyUSB0')  # Instanciación por hardware del controlador

    # Identificadores de las ventanas de despliegue gráfico
    WINDOW_LIVE = "Celda_MPS - Monitoreo Local"
    WINDOW_MOSAIC = "Mosaico VLA - Entrada de Inferencia"
    
    cv2.namedWindow(WINDOW_LIVE, cv2.WINDOW_AUTOSIZE)

    print("\n=== SISTEMA CELDA_MPS CONFIGURADO (HÍBRIDO + COGNITIVO) ===")
    print("- Monitoreo local activo en pantalla.")
    print("- Control por puerto serial del brazo Mitsubishi activo.")
    print("- Presione 'e' o ESPACIO para procesar inferencia con Qwen-VL.")
    print("- Presione 'q' para salir de forma segura.")
    print("===========================================================\n")

    while True:
        ret, frame = cap.read()
        if not ret:
            print("Fallo en la captura de cuadro desde el backend V4L2.", file=sys.stderr)
            break

        frame_visualizacion = frame.copy()
        frame_instrumentado, estado_celda = vision_local.procesar_cuadro(frame_visualizacion)
        cv2.imshow(WINDOW_LIVE, frame_instrumentado)
        
        key = cv2.waitKey(1) & 0xFF
        
        if key == ord('e') or key == ord(' '):
            print("\n[EVENTO CAPTURA] Capturando cuadro crudo para el VLA. Procesando...")
            
            frame_overlay = frame_instrumentado.copy()
            cv2.putText(frame_overlay, "EJECUTANDO INFERENCIA QWEN-VL...", (30, 240),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 255), 2)
            cv2.imshow(WINDOW_LIVE, frame_overlay)
            cv2.waitKey(100)  # Forzar el ciclo de refresco del servidor gráfico X11
            
            resultado = vla_core.analizar_escena_completa(frame)
            
            mosaico_path = os.path.join("capturas_vla", "analisis_autonomo.jpg")
            if os.path.exists(mosaico_path):
                mosaico_img = cv2.imread(mosaico_path)
                if mosaico_img is not None:
                    cv2.namedWindow(WINDOW_MOSAIC, cv2.WINDOW_NORMAL)
                    cv2.imshow(WINDOW_MOSAIC, mosaico_img)
                    cv2.waitKey(10)
                else:
                    print("[ERROR SISTEMA] El mosaico existe en disco pero no pudo ser decodificado por OpenCV.", file=sys.stderr)
            else:
                print("[ERROR SISTEMA] No se encontró el archivo físico del mosaico para visualización.", file=sys.stderr)

            if resultado:
                pieza = resultado.get("pieza_en_posicion_1", "ninguna")
                destino = resultado.get("posicion_destino_evaluada", "Ninguna")
                estado_dest = resultado.get("estado_posicion_destino", "libre")
                accion = resultado.get("accion_robot", "esperar_pieza")
                
                print("\n=======================================================")
                print(f"[VLA COGNITIVO] Objeto en Posición_1: {pieza.upper()}")
                print(f"[VLA COGNITIVO] Destino Calculado: {destino}")
                print(f"[VLA COGNITIVO] Estado de Destino: {estado_dest.upper()}")
                print(f"[VLA COGNITIVO] Acción Cinemática: {accion.upper()}")
                
                # Validación cruzada determinista con la configuración geométrica e interlocks
# Validación cruzada determinista con la configuración geométrica e interlocks
                if (accion in ["ejecutar_movimiento", "ejecutar_movement"]) and (destino in ce.POSICIONES_CELDA):
                    coords_origen = ce.POSICIONES_CELDA["Posicion_1"]["robot"]
                    coords_destino = ce.POSICIONES_CELDA[destino]["robot"]
                    
                    print(f"\n[CONTROL INTERLOCK] Trayectoria validada y autorizada.")
                    print(f" -> PICK  (Origen Posicion_1) XYZ [mm]: {coords_origen} via P1")
                    print(f" -> PLACE (Destino {destino}) XYZ [mm]: {coords_destino} via P2")
                    
                    # Ejecución física de la trayectoria síncrona mediante el driver serial
                    print("\n[EJECUCIÓN CINEMÁTICA] Despachando comandos físicos al hardware...")
                    
                    # 1. Almacenamiento geométrico y desplazamiento síncrono al punto de recogida (P1)
                    success = robot_control.mover_a_coordenadas(
                        coords_origen[0], coords_origen[1], coords_origen[2], 
                        var_posicion="P1", 
                        nombre_pos="Posicion_1"
                    )
                    
                    # 2. Si el PICK es exitoso, descompresionar hardware y despachar al punto de descarga (P2)
                    if success:
                        print("[MECATRÓNICA] Captura de origen confirmada. Estabilizando presión y servos...")
                        
                        # RETARDO CRÍTICO: Da un margen de 400ms para que el firmware del controlador Mitsubishi 
                        # cierre el ciclo de control del primer movimiento y limpie sus registros antes de recibir el comando PLACE.
                        time.sleep(0.4) 
                        
                        print("[MECATRÓNICA] Transicionando a vector de descarga...")
                        robot_control.mover_a_coordenadas(
                            coords_destino[0], coords_destino[1], coords_destino[2], 
                            var_posicion="P2", 
                            nombre_pos=destino
                        )
                    else:
                        print("[MECATRÓNICA] Movimiento abortado por fallo de confirmación en el eslabón de origen.", file=sys.stderr)
                        
                elif accion == "bloquear_por_colision":
                    print(f"\n[ALERTA CRÍTICA] Trayectoria bloqueada. Destino {destino} ocupado o con riesgo de colisión.")
                else:
                    print(f"\n[CONTROL] Sistema en estado de espera (Standby).")
                print("=======================================================\n")
                
            print("[EVENTO FINALIZADO] Retornando al flujo de video en vivo...\n")

        elif key == ord('q'):
            break

    # Liberación controlada de recursos de hardware
    cap.release()
    robot_control.cerrar_interfaz()
    cv2.destroyAllWindows()

if __name__ == "__main__":
    main()
