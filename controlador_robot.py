# Desarrollo: Daniel Velazquez
# Módulo de Control de Hardware - Interfaz Serial Atómica para Brazo Mitsubishi

import serial
import time
import sys

class ControladorRobot:
    def __init__(self, port='/dev/ttyUSB0', baudrate=9600):
        """
        Inicializa la conexión serie con el controlador Mitsubishi y activa los servos.
        """
        try:
            self.ser = serial.serial_for_url(
                port, 
                baudrate=baudrate, 
                parity='E', 
                stopbits=2, 
                timeout=1
            )
            self._inicializar_hardware()
        except Exception as e:
            print(f"[CRÍTICO] Fallo de inicialización en el puerto {port}: {e}", file=sys.stderr)
            sys.exit(1)

    def _inicializar_hardware(self):
        """
        Secuencia de inicialización y energización de servomotores (Interlocks de seguridad).
        """
        print("[*] Inicializando enlace de hardware...")
        self._cmd("CNTLON")
        time.sleep(0.2)
        self._cmd("SRVON")
        time.sleep(1.0)
        self._cmd("EXEC OVRD 10")
        print("[+] Servomotores acoplados y velocidad de anulación configurada al 90%.")

    def _cmd(self, command, timeout_retardo=1.5):
        """
        Transmite una trama ASCII al controlador Mitsubishi de forma síncrona.
        Garantiza la lectura atómica orientada a líneas limpiando residuos de la UART.
        """
        try:
            # Ventana mínima de guarda eléctrica entre transacciones seriales secuenciales
            time.sleep(0.04)
            self.ser.reset_input_buffer()
            
            payload = f"1;1;{command}\r".encode('ascii')
            self.ser.write(payload)
            self.ser.flush()
            
            tiempo_limite = time.time() + timeout_retardo
            while time.time() < tiempo_limite:
                if self.ser.in_waiting > 0:
                    respuesta_cruda = self.ser.readline()
                    respuesta_limpia = respuesta_cruda.decode('ascii', errors='ignore').replace('\r', '').replace('\n', '').strip()
                    if respuesta_limpia:
                        return respuesta_limpia
                time.sleep(0.01)
                
            return ""
        except Exception as e:
            print(f"[!] Error crítico en bus serie durante comando '{command}': {e}", file=sys.stderr)
            return ""

    def mover_a_coordenadas(self, x, y, z, pitch=0.0, roll=180.0, var_posicion="P1", nombre_pos="Target"):
        """
        Asigna un vector cartesiano a una variable de posición en el controlador (EXEC Px = (...))
        y posteriormente ejecuta un comando de interpolación de trayectoria síncrono (EXEC MOV Px).
        """
        pos_str = f"XYZ({x:.1f}, {y:.1f}, {z:.1f})"
        
        # Etapa 1: Definición explícita de la variable de posición en memoria
        comando_def = f"EXEC {var_posicion} = ({x:.1f}, {y:.1f}, {z:.1f}, {pitch:.1f}, {roll:.1f})"
        print(f"[*] Definiendo variable {var_posicion} en hardware: {pos_str}")
        
        res_def = self._cmd(comando_def, timeout_retardo=1.5)
        if "QOK" not in res_def.upper():
            print(f"[CRÍTICO] Fallo en la asignación de la variable {var_posicion} (Respuesta: '{res_def}'). Abortando.")
            return False

        # Etapa 2: Despacho cinemático referenciando el identificador simbólico de memoria
        comando_mov = f"EXEC MOV {var_posicion}"
        print(f"[*] Transmitiendo vector cinemático: {nombre_pos} -> MOV {var_posicion}")
        
        res_mov = self._cmd(comando_mov, timeout_retardo=2.0)
        print(res_mov)
            
        if "QOK" in res_mov.upper():
            print(f"[+] Comando validado en hardware. Monitoreando ciclo de trayectoria para {nombre_pos}...")
            
            # Ventana de guarda extendida para asegurar el desenganche del estado de reposo 
            # y dar tiempo a la aceleración de los servomotores antes de interrogar la UART
            time.sleep(0.6) 
                
            conteo_errores_trama = 0
            while True:
                res_limpio = self._cmd("STATE").strip()
                
                if res_limpio:
                    # Extraer única y exclusivamente dígitos numéricos (descarta ecos de comando y texto)
                    digitos_validos = [c for c in res_limpio if c.isdigit()]
                    
                    if digitos_validos:
                        estado_actual = digitos_validos[-1]
                        
                        if estado_actual == "0":
                            # Doble verificación temporal para evitar capturar estados transitorios
                            time.sleep(0.08)
                            verificacion = self._cmd("STATE").strip()
                            digitos_verif = [c for c in verificacion if c.isdigit()]
                            
                            if digitos_verif and digitos_verif[-1] == "0":
                                print(f"[+] Mecanismo estático. Destino {nombre_pos} alcanzado de forma segura.")
                                return True
                        else:
                            print(f"[*] Ejecutando perfil dinámico para {nombre_pos}. Estado actual: {estado_actual}")
                            conteo_errores_trama = 0
                    else:
                        print(f"[!] Trama de telemetría no numérica descartada: '{res_limpio}'")
                else:
                    conteo_errores_trama += 1
                    if conteo_errores_trama > 15:
                        print(f"[CRÍTICO] Pérdida de enlace UART con el robot durante monitoreo de {nombre_pos}.")
                        return False
                   
                time.sleep(0.15)
        else:
            print(f"[CRÍTICO] El controlador denegó el movimiento hacia {nombre_pos} mediante {var_posicion} (Respuesta: '{res_mov}'). Abortando.")
            return False
            
    def cerrar_interfaz(self):
        """
        Desenergiza los servos de forma controlada y libera el recurso del sistema operativo.
        """
        print("[*] Desactivando servomotores y cerrando puerto...")
        self._cmd("SRVOFF")
        self._cmd("CNTLOFF")
        if self.ser.is_open:
            self.ser.close()
        print("[+] Interfaz de hardware liberada.")
