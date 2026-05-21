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

    def _cmd(self, command):
        """
        Transmite una trama ASCII al controlador y retorna la respuesta limpia.
        """
        try:
            payload = f"1;1;{command}\r".encode('ascii')
            self.ser.write(payload)
            time.sleep(0.05)  # Tiempo de asentamiento del buffer físico
            
            if self.ser.in_waiting:
                respuesta = self.ser.read(self.ser.in_waiting).decode('ascii').strip()
                return respuesta
            return ""
        except Exception as e:
            print(f"[!] Error de comunicación serie: {e}", file=sys.stderr)
            return ""

    def _inicializar_hardware(self):
        """
        Secuencia de inicialización y energización de servomotores (Interlocks de seguridad).
        """
        print("[*] Inicializando enlace de hardware...")
        self._cmd("CNTLON")
        time.sleep(0.2)
        self._cmd("SRVON")
        time.sleep(1.0)
        self._cmd("EXEC OVRD 90")
        print("[+] Servomotores acoplados y velocidad de anulación configurada al 90%.")

    def mover_a_coordenadas(self, x, y, z, pitch=0.0, roll=180.0):
        """
        Despacha un comando de movimiento cartesiano y bloquea el hilo de ejecución
        hasta que el estado del robot retorne a 0 (Estático).
        """
        # Formatear el comando de movimiento síncrono con la pose destino
        comando_mov = f"EXEC MOV ({x:.1f}, {y:.1f}, {z:.1f}, {pitch:.1f}, {roll:.1f})"
        print(f"[*] Despachando comando de movimiento cartesiano: XYZ({x}, {y}, {z})")
        
        res_mov = self._cmd(comando_mov)
        
        # Validar la aceptación del comando por el firmware del controlador
        if "QoK" not in res_mov:
            print(f"[CRÍTICO] Controlador rechazó la instrucción cinemática. Respuesta: {res_mov}", file=sys.stderr)
            return False

        print("[*] Monitoreando estado de ejecución de la trayectoria...")
        time.sleep(0.15)  # Ventana cinemática inicial para el desarrollo del perfil de aceleración

        while True:
            res = self._cmd("STATE")
            res_limpio = res.strip()
            
            if res_limpio:
                estado_actual = res_limpio[-1]
                
                if estado_actual == "0":
                    print(f"[+] Movimiento finalizado con éxito (STATE 0).")
                    break
                else:
                    print(f"[*] Robot en movimiento: Estado actual [{estado_actual}]")
            else:
                print("[!] Alerta: Trama vacía o error de paridad en la UART.", file=sys.stderr)
            
            time.sleep(0.05)  # Frecuencia de muestreo del lazo de estado (20 Hz)
        
        return True

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
