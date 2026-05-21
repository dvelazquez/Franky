# Desarrollo: Daniel Velazquez
# Módulo de Control de Hardware - Interfaz Serial Atómica para Brazo Mitsubishi

import serial
import time
import sys

class ControladorRobot:
    def __init__(self, port='/dev/ttyUSB0', baudrate=9600):
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

    def _cmd(self, command):
        """
        Transmite una trama ASCII al controlador garantizando los tiempos de ciclo del CR1.
        """
        try:
            # Limpiar buffers del sistema operativo antes de la transacción
            self.ser.reset_input_buffer()
            self.ser.reset_output_buffer()

            payload = f"1;1;{command}\r".encode('ascii')
            self.ser.write(payload)
            
            # El CR1 requiere un retardo mínimo de procesamiento de comandos interactivos
            time.sleep(0.5) 
            
            if self.ser.in_waiting:
                respuesta = self.ser.read(self.ser.in_waiting).decode('ascii').strip()
                return respuesta
            return ""
        except Exception as e:
            print(f"[!] Error de comunicación serie: {e}", file=sys.stderr)
            return ""

    def _inicializar_hardware(self):
        """
        Secuencia de inicialización con retardos extendidos para evitar colisiones de buffer.
        """
        print("[*] Inicializando enlace de hardware...")
        self._cmd("CNTLON")
        time.sleep(0.5)
        self._cmd("SRVON")
        time.sleep(1.5)  # Tiempo crítico para la magnetización y liberación de frenos físicos
        self._cmd("EXEC OVRD 90")
        time.sleep(0.5)
        print("[+] Servomotores acoplados y velocidad de anulación configurada al 90%.")

    def mover_a_coordenadas(self, x, y, z, pitch=0.0, roll=180.0):
        """
        Despacha un comando de movimiento cartesiano emulando la sintaxis nativa de ControlRobot7.py
        """
        # Formatear la cadena eliminando espacios redundantes dentro del paréntesis de la pose
        # Sintaxis exacta validada por firmware: EXEC MOV (120.0,-240.0,270.0,0.0,180.0)
        comando_mov = f"EXEC MOV ({float(x)},{float(y)},{float(z)},{float(pitch)},{float(roll)})"
        print(f"[*] Despachando comando de trayectoria: {comando_mov}")
        
        res_mov = self._cmd(comando_mov)
        
        # Depuración en consola de la respuesta exacta del firmware
        print(f"[*] Respuesta directa del controlador: '{res_mov}'")
        
        # Validar la aceptación de la instrucción por parte del CR1
        if "QoK" not in res_mov:
            print(f"[CRÍTICO] Controlador rechazó la instrucción cinemática. Respuesta: '{res_mov}'", file=sys.stderr)
            return False

        print("[*] Monitoreando estado de ejecución de la trayectoria...")
        time.sleep(0.2)  # Ventana cinemática inicial

        while True:
            res = self._cmd("STATE")
            res_limpio = res.strip().replace("\r", "").replace("\n", "")
            
            if res_limpio:
                # Extraer la cadena de dígitos para aislar el bit de estado operativo
                digitos_estado = "".join([c for c in res_limpio if c.isdigit()])
                
                if digitos_estado:
                    estado_actual = digitos_estado[-1]
                    
                    if estado_actual == "0":
                        print(f"[+] Movimiento finalizado con éxito (STATE 0).")
                        return True
                    else:
                        print(f"[*] Robot en movimiento: Estado [{estado_actual}] | Trama: '{res_limpio}'")
                else:
                    print(f"[!] Trama sin dígitos numéricos: '{res_limpio}'", file=sys.stderr)
            else:
                print("[!] Alerta: Respuesta vacía en la lectura de estado.", file=sys.stderr)
            
            time.sleep(0.1)  # Ajuste de frecuencia de consulta para no saturar la CPU del robot
