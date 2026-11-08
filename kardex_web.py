import streamlit as st
import sqlite3
from datetime import datetime
import pandas as pd

st.set_page_config(page_title="Smart Kardex", layout="wide")

# ==========================================
# BASE DE DATOS
# ==========================================
def get_db_connection():
    return sqlite3.connect('kardex_web.db', check_same_thread=False)

def inicializar_bd():
    conn = get_db_connection()
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS usuarios (dni TEXT PRIMARY KEY, password TEXT, rol TEXT)''')
    c.execute('''CREATE TABLE IF NOT EXISTS kardex (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        insumo TEXT, lote TEXT, abc TEXT, ven TEXT, cpm REAL, 
        stock REAL, punto_reorden REAL, a_pedir REAL, 
        fecha_ingreso TEXT, fecha_salida TEXT, fecha_vencimiento TEXT)''')
    c.execute("SELECT * FROM usuarios WHERE dni='admin'")
    if not c.fetchone():
        c.execute("INSERT INTO usuarios VALUES ('admin', 'admin123', 'Administrador')")
    conn.commit()
    conn.close()

inicializar_bd()

# ==========================================
# LOGIN 
# ==========================================
if 'usuario_actual' not in st.session_state:
    st.session_state['usuario_actual'] = None
    st.session_state['rol_actual'] = None

if st.session_state['usuario_actual'] is None:
    st.title("📦 Kardex Inteligente")
    st.subheader("Acceso al Sistema")
    
    dni = st.text_input("DNI del Usuario")
    password = st.text_input("Contraseña", type="password")
    
    if st.button("Iniciar Sesión", type="primary"):
        conn = get_db_connection()
        res = conn.execute("SELECT rol FROM usuarios WHERE dni=? AND password=?", (dni, password)).fetchone()
        conn.close()
        if res:
            st.session_state['usuario_actual'] = dni
            st.session_state['rol_actual'] = res[0]
            st.rerun()
        else:
            st.error("Credenciales incorrectas.")
    st.stop()

# ==========================================
# GESTIÓN DE TRABAJADORES (SOLO ADMIN)
# ==========================================
if st.session_state['rol_actual'] == "Administrador":
    with st.sidebar:
        st.header("👥 Gestión de Personal")
        st.write("Agrega acceso a tus trabajadores.")
        with st.form("nuevo_usuario_form", clear_on_submit=True):
            n_dni = st.text_input("DNI del Trabajador")
            n_pass = st.text_input("Crear Contraseña")
            n_rol = st.selectbox("Rol", ["Trabajador", "Administrador"])
            
            if st.form_submit_button("Crear Cuenta", type="primary", use_container_width=True):
                if n_dni and n_pass:
                    try:
                        conn = get_db_connection()
                        conn.execute("INSERT INTO usuarios VALUES (?,?,?)", (n_dni, n_pass, n_rol))
                        conn.commit(); conn.close()
                        st.success(f"Cuenta creada para el DNI {n_dni}")
                    except sqlite3.IntegrityError:
                        st.error("Ese DNI ya está registrado.")
                else:
                    st.warning("Completa los datos.")

# ==========================================
# PANEL PRINCIPAL
# ==========================================
col_titulo, col_boton = st.columns([8, 2])
with col_titulo:
    st.header(f"Panel Principal - {st.session_state['rol_actual']}")
with col_boton:
    if st.button("Cerrar Sesión", use_container_width=True):
        st.session_state['usuario_actual'] = None
        st.session_state['rol_actual'] = None
        st.rerun()

st.divider()

def calcular_semaforo(cpm, stock, preorden):
    try: cpm, stock, preorden = float(cpm), float(stock), float(preorden)
    except: return "⚪"
    if stock == 0: return "🔴 Desabastecido"
    if stock < preorden: return "🟡 Substock"
    if cpm > 0 and (stock / cpm) > 6: return "🟠 Sobrestock"
    return "🟢 Normal"

df_kardex = pd.read_sql_query("SELECT * FROM kardex", get_db_connection())
col_form, col_tabla = st.columns([1, 2.5], gap="large")

# --- LADO IZQUIERDO: FORMULARIO Y RETIROS ---
with col_form:
    st.subheader("Agregar Nuevo Insumo")
    insumo = st.text_input("Nombre del Insumo")
    lote = st.text_input("Lote")
    c1, c2 = st.columns(2)
    abc = c1.selectbox("Clasificación ABC", ["A", "B", "C"])
    ven = c2.selectbox("Clasificación VEN", ["V", "E", "N"])
    c3, c4 = st.columns(2)
    cpm = c3.number_input("CPM (Rotación)", min_value=0.0)
    stock = c4.number_input("Stock Inicial", min_value=0.0)
    c5, c6 = st.columns(2)
    preorden = c5.number_input("Punto de Reorden", min_value=0.0)
    apedir = c6.number_input("Cantidad a Pedir", min_value=0.0)
    vence = st.text_input("Fecha de Vencimiento")
    
    if st.button("Guardar Insumo", type="primary", use_container_width=True):
        if insumo:
            fecha_hoy = datetime.now().strftime("%d/%m/%Y %H:%M")
            conn = get_db_connection()
            conn.execute('''INSERT INTO kardex (insumo, lote, abc, ven, cpm, stock, punto_reorden, a_pedir, fecha_ingreso, fecha_salida, fecha_vencimiento) VALUES (?,?,?,?,?,?,?,?,?,?,?)''', 
                        (insumo, lote, abc, ven, cpm, stock, preorden, apedir, fecha_hoy, fecha_hoy, vence))
            conn.commit(); conn.close()
            st.success("Insumo guardado.")
            st.rerun()
        else:
            st.warning("El nombre es obligatorio.")
            
    st.divider()
    
    # SECCIÓN DE RETIRO Y ELIMINACIÓN
    st.subheader("Gestión del Insumo")
    if not df_kardex.empty:
        opciones = df_kardex['id'].astype(str) + " - " + df_kardex['insumo']
        seleccion = st.selectbox("Seleccione el insumo:", opciones)
        id_seleccionado = int(seleccion.split(" - ")[0])
        fila = df_kardex[df_kardex['id'] == id_seleccionado].iloc[0]
        
        st.info(f"Stock actual: **{fila['stock']}** unidades")
        cantidad = st.number_input("Unidades a retirar", min_value=1.0, max_value=float(fila['stock']), value=1.0)
        
        b_retirar, b_eliminar = st.columns(2)
        with b_retirar:
            if st.button("📦 Retirar", use_container_width=True):
                nuevo_stock = fila['stock'] - cantidad
                fecha_salida = datetime.now().strftime("%d/%m/%Y %H:%M")
                conn = get_db_connection()
                conn.execute("UPDATE kardex SET stock=?, fecha_salida=? WHERE id=?", (nuevo_stock, fecha_salida, id_seleccionado))
                conn.commit(); conn.close()
                st.success(f"Retiro registrado.")
                st.rerun()
        with b_eliminar:
            if st.button("🗑️ Borrar Error", use_container_width=True):
                conn = get_db_connection()
                conn.execute("DELETE FROM kardex WHERE id=?", (id_seleccionado,))
                conn.commit(); conn.close()
                st.warning("Insumo eliminado.")
                st.rerun()
    else:
        st.write("No hay insumos registrados.")

# --- LADO DERECHO: TABLA ---
with col_tabla:
    st.subheader("Inventario en Tiempo Real")
    if not df_kardex.empty:
        df_mostrar = df_kardex.copy()
        df_mostrar['Estado'] = df_mostrar.apply(lambda row: calcular_semaforo(row['cpm'], row['stock'], row['punto_reorden']), axis=1)
        orden = ['id', 'insumo', 'lote', 'stock', 'Estado', 'fecha_ingreso', 'fecha_salida', 'fecha_vencimiento']
        st.dataframe(df_mostrar[orden], use_container_width=True, hide_index=True)
    else:
        st.info("El Kardex está vacío.")

st.caption("CREADO POR: NATHALY INGA BOVIS")