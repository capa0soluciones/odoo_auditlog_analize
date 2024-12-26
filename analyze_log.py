import urwid
import json
import argparse
import re

def analizar_log(archivo_log, usuario):
    try:
        with open(archivo_log, 'r') as f:
            lineas = f.readlines()
    except FileNotFoundError:
        print(f"Error: Archivo '{archivo_log}' no encontrado.")
        return {}  # Devuelve un diccionario vacío en caso de error

    requests_usuario = []
    for linea in lineas:
        if "monitoring.http.requests" in linea:
            try:
                match = re.search(r'{.*}', linea)
                if match:
                    json_str = match.group(0)
                    log_data = json.loads(json_str)
                    if log_data.get('login') == usuario:
                        fecha_hora = linea.split(" ")[0] + " " + linea.split(" ")[1].split(",")[0]
                        log_data['fecha_hora'] = fecha_hora
                        requests_usuario.append(log_data)
                else:
                    print(f"No se encontró JSON válido en la línea: {linea.strip()}")
            except json.JSONDecodeError:
                print(f"Error al decodificar JSON en la línea: {linea.strip()}")
            except IndexError:
                print(f"Error al extraer fecha/hora en la línea: {linea.strip()}")

    conteo_modelos = {}
    for request in requests_usuario:
        modelo = request.get('model')
        if modelo:
            if modelo not in conteo_modelos:
                conteo_modelos[modelo] = {'cantidad': 0, 'detalles': []}
            conteo_modelos[modelo]['cantidad'] += 1
            conteo_modelos[modelo]['detalles'].append(request)

    return conteo_modelos

class Application:
    def __init__(self, archivo_log):
        self.archivo_log = archivo_log
        self.usuarios = self.obtener_usuarios()
        self.current_user = None
        self.current_model = None
        self.palette = [
            ('reversed', 'standout', ''),
            ('header', 'black', 'white'),  # Definir el estilo del encabezado
        ]

        self.user_buttons = []
        for usuario in self.usuarios:
            boton = urwid.Button(usuario, on_press=self.seleccionar_usuario)
            self.user_buttons.append(urwid.AttrMap(boton, None, focus_map='reversed'))

        self.lista_usuarios = urwid.ListBox(urwid.SimpleListWalker(self.user_buttons))
        self.encabezado = urwid.Text("Selecciona un usuario:")
        self.pila_informacion = urwid.ListBox(urwid.SimpleFocusListWalker([]))

        columnas = urwid.Columns([
            ('weight', 1, urwid.Padding(self.lista_usuarios, left=1, right=1)),
            ('weight', 2, urwid.Padding(self.pila_informacion, left=1, right=1)),
        ], dividechars=1)

        self.widget_principal = urwid.Frame(columnas, header=self.encabezado)
        self.bucle_principal = urwid.MainLoop(self.widget_principal, palette=self.palette, unhandled_input=self.manejar_entrada)
        self.bucle_principal.set_alarm_in(1, self.refrescar_datos)

    def obtener_usuarios(self):
        try:
            with open(self.archivo_log, 'r') as f:
                lineas = f.readlines()
        except FileNotFoundError:
            print(f"Error: Archivo '{self.archivo_log}' no encontrado.")
            return []

        usuarios_encontrados = set()
        for linea in lineas:
            if "monitoring.http.requests" in linea:
                try:
                    match = re.search(r'{.*}', linea)
                    if match:
                        json_str = match.group(0)
                        log_data = json.loads(json_str)
                        usuario = log_data.get('login')
                        if usuario:
                            usuarios_encontrados.add(usuario)
                except (json.JSONDecodeError, IndexError):
                    pass
        return sorted(list(usuarios_encontrados))

    def seleccionar_usuario(self, boton):
        self.current_user = boton.label
        self.current_model = None
        self.mostrar_modelos_usuario()

    def seleccionar_modelo(self, boton):
        self.current_model = boton.label.split(' ')[0]  # Extraer el nombre del modelo
        self.mostrar_detalles_modelo()

    def mostrar_modelos_usuario(self):
        texto_resultados = []
        if self.current_user:
            resultados = analizar_log(self.archivo_log, self.current_user)

            if not resultados:
                texto_resultados.append(urwid.Text(f"No se encontraron requests para '{self.current_user}'.\n"))
            else:
                texto_resultados.append(urwid.Text(f"Modelos para '{self.current_user}':\n"))
                for modelo, datos in resultados.items():
                    boton = urwid.Button(f"{modelo} ({datos['cantidad']})", on_press=self.seleccionar_modelo)
                    texto_resultados.append(urwid.AttrMap(boton, None, focus_map='reversed'))

            self.pila_informacion.body = urwid.SimpleFocusListWalker(texto_resultados)
        else:
            self.pila_informacion.body = urwid.SimpleFocusListWalker([])
            self.encabezado.set_text("Selecciona un usuario:")

    def mostrar_detalles_modelo(self):
        if self.current_user and self.current_model:
            resultados = analizar_log(self.archivo_log, self.current_user)
            detalles = resultados.get(self.current_model, {}).get('detalles', [])

            if not detalles:
                self.pila_informacion.body = urwid.SimpleFocusListWalker([urwid.Text(f"No se encontraron requests para el modelo '{self.current_model}'.\n")])
            else:
                headers = ['UID', 'Fecha y Hora', 'Método', 'Model Method', 'URL']
                table_header = urwid.Columns([
                    ('fixed', 5, urwid.AttrMap(urwid.Text(headers[0]), 'header')),
                    ('fixed', 20, urwid.AttrMap(urwid.Text(headers[1]), 'header')),
                    ('fixed', 10, urwid.AttrMap(urwid.Text(headers[2]), 'header')),
                    ('fixed', 28, urwid.AttrMap(urwid.Text(headers[3]), 'header')),
                    urwid.AttrMap(urwid.Text(headers[4]), 'header')
                ])
                table_rows = [table_header]

                for detalle in detalles:
                    row = urwid.Columns([
                        ('fixed', 4, urwid.Text(str(detalle.get('uid', '') or ''))),
                        ('fixed', 20, urwid.Text(detalle.get('fecha_hora', '') or '')),
                        ('fixed', 7, urwid.Text(detalle.get('method', '') or '')),
                        ('fixed', 28, urwid.Text(detalle.get('model_method', '') or '')),
                        urwid.Text(detalle.get('url', '') or '')
                    ], dividechars=1)
                    table_rows.append(row)

                self.pila_informacion.body = urwid.SimpleFocusListWalker(table_rows)
        else:
            self.pila_informacion.body = urwid.SimpleFocusListWalker([])
            self.encabezado.set_text("Selecciona un usuario y un modelo:")

    def manejar_entrada(self, key):
        if key in ('q', 'Q'):
            raise urwid.ExitMainLoop()

    def refrescar_datos(self, loop, user_data):
        if self.current_user:
            focus_position = self.pila_informacion.get_focus()[1]  # Guardar la posición actual del cursor
            if self.current_model:
                self.mostrar_detalles_modelo()
            else:
                self.mostrar_modelos_usuario()
            if focus_position < len(self.pila_informacion.body):
                self.pila_informacion.set_focus(focus_position)  # Restaurar la posición del cursor
        loop.set_alarm_in(1, self.refrescar_datos)

def main():
    parser = argparse.ArgumentParser(description="Analiza logs de Odoo interactivamente.")
    parser.add_argument("archivo_log", help="Ruta al archivo de log.")
    args = parser.parse_args()

    app = Application(args.archivo_log)
    app.bucle_principal.run()

if __name__ == "__main__":
    main()