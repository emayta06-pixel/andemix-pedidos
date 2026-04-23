import io
import streamlit as st
import sqlite3
import pandas as pd
from datetime import datetime
import os
import hashlib

st.set_page_config(page_title="Andemix Pedidos", page_icon="🏔️", layout="wide")

# ====================== ESTILO ======================
st.markdown("""
<style>
    .main {background-color: #f8f9fa;}
    .stButton>button {background-color: #1b5e20; color: white; font-weight: bold;}
    .stButton>button:hover {background-color: #145a17;}
    h1, h2, h3 {color: #1b5e20;}
    .login-box {
        max-width: 400px;
        margin: 80px auto;
        padding: 2rem;
        background: white;
        border-radius: 12px;
        box-shadow: 0 4px 20px rgba(0,0,0,0.1);
    }
    .role-badge-admin {
        background-color: #1b5e20; color: white;
        padding: 2px 10px; border-radius: 20px; font-size: 12px;
    }
    .role-badge-vendedor {
        background-color: #2e7d32; color: white;
        padding: 2px 10px; border-radius: 20px; font-size: 12px;
    }
</style>
""", unsafe_allow_html=True)

# ====================== BASE DE DATOS ======================
def get_db():
    return sqlite3.connect('andemix_pedidos.db')

def hash_password(password):
    return hashlib.sha256(password.encode()).hexdigest()

with get_db() as conn:
    conn.executescript('''
        CREATE TABLE IF NOT EXISTS vendedores (id INTEGER PRIMARY KEY, nombre TEXT UNIQUE NOT NULL);
        CREATE TABLE IF NOT EXISTS productos (id INTEGER PRIMARY KEY, nombre TEXT UNIQUE NOT NULL, unidad TEXT DEFAULT 'kg');
        CREATE TABLE IF NOT EXISTS precios_vendedora (
            id INTEGER PRIMARY KEY,
            vendedor_id INTEGER,
            producto_id INTEGER,
            precio_mayor REAL NOT NULL,
            precio_cliente REAL NOT NULL,
            fecha_actualizacion TEXT,
            UNIQUE(vendedor_id, producto_id)
        );
        CREATE TABLE IF NOT EXISTS pedidos (
            id INTEGER PRIMARY KEY, fecha TEXT, vendedor_id INTEGER, cliente TEXT,
            total REAL DEFAULT 0.0, estado TEXT DEFAULT 'Pendiente', observaciones TEXT,
            FOREIGN KEY(vendedor_id) REFERENCES vendedores(id)
        );
        CREATE TABLE IF NOT EXISTS pedido_detalle (
            id INTEGER PRIMARY KEY, 
            pedido_id INTEGER, 
            producto_id INTEGER,
            cantidad REAL, 
            precio_unitario REAL,
            subtotal REAL,
            FOREIGN KEY(pedido_id) REFERENCES pedidos(id)
        );
        CREATE TABLE IF NOT EXISTS usuarios (
            id INTEGER PRIMARY KEY,
            username TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            rol TEXT NOT NULL DEFAULT 'vendedor',
            vendedor_id INTEGER,
            FOREIGN KEY(vendedor_id) REFERENCES vendedores(id)
        );
    ''')
    
    # Vendedores
    vendedores_list = ['Betelina Torpoco', 'Maria Pajuelo', 'Flor Pajuelo', 'Jenny Mayta', 
                       'Hayme Rivera', 'Marcela Torpoco', 'Michel Castillo', 'Rosmery',
                       'Hector', 'Ivan Huanuco', 'Mirtha Tinoco']
    for v in vendedores_list:
        conn.execute("INSERT OR IGNORE INTO vendedores (nombre) VALUES (?)", (v,))
    
    # Productos y Precios
    conn.execute("DELETE FROM productos")
    conn.execute("DELETE FROM precios_vendedora")
    
    productos_precios = [
        ('Cuy', 'unidad', 32.0, 35.0),
        ('Filete de Trucha', 'kg', 23.0, 25.0),
        ('Trucha Eviscerada', 'kg', 20.0, 22.0),
        ('Queso Fresco', 'kg', 25.0, 28.0),
        ('Queso Prensado', 'kg', 29.0, 32.0),
        ('Pan Serrano', 'unidad', 2.5, 2.5)
    ]
    
    for nombre, unidad, p_mayor, p_cliente in productos_precios:
        conn.execute("INSERT INTO productos (nombre, unidad) VALUES (?, ?)", (nombre, unidad))
        prod_id = conn.execute("SELECT id FROM productos WHERE nombre = ?", (nombre,)).fetchone()[0]
        for v_id in range(1, len(vendedores_list)+1):
            conn.execute("""
                INSERT INTO precios_vendedora (vendedor_id, producto_id, precio_mayor, precio_cliente, fecha_actualizacion)
                VALUES (?, ?, ?, ?, ?)
            """, (v_id, prod_id, p_mayor, p_cliente, datetime.now().strftime("%Y-%m-%d")))
    
    # Crear usuario administrador Edwin Mayta
    conn.execute("""
        INSERT OR IGNORE INTO usuarios (username, password_hash, rol, vendedor_id)
        VALUES (?, ?, 'admin', NULL)
    """, ('edwin.mayta', hash_password('admin1234')))
    
    # Crear usuarios para cada vendedora (contraseña = nombre en minúsculas sin espacios)
    for v in vendedores_list:
        v_id = conn.execute("SELECT id FROM vendedores WHERE nombre = ?", (v,)).fetchone()
        if v_id:
            username = v.lower().replace(' ', '.').replace('á','a').replace('é','e').replace('í','i').replace('ó','o').replace('ú','u')
            default_pass = v.lower().replace(' ', '').replace('á','a').replace('é','e').replace('í','i').replace('ó','o').replace('ú','u') + '123'
            conn.execute("""
                INSERT OR IGNORE INTO usuarios (username, password_hash, rol, vendedor_id)
                VALUES (?, ?, 'vendedor', ?)
            """, (username, hash_password(default_pass), v_id[0]))
    
    conn.commit()

# ====================== AUTH FUNCTIONS ======================
def autenticar(username, password):
    with get_db() as conn:
        row = conn.execute("""
            SELECT u.id, u.username, u.rol, u.vendedor_id, v.nombre as vendedor_nombre
            FROM usuarios u
            LEFT JOIN vendedores v ON u.vendedor_id = v.id
            WHERE u.username = ? AND u.password_hash = ?
        """, (username, hash_password(password))).fetchone()
        return row

def cambiar_password(user_id, nueva_password):
    with get_db() as conn:
        conn.execute("UPDATE usuarios SET password_hash = ? WHERE id = ?", 
                     (hash_password(nueva_password), user_id))
        conn.commit()

def listar_usuarios():
    with get_db() as conn:
        return pd.read_sql("""
            SELECT u.id, u.username, u.rol, v.nombre as vendedor_nombre
            FROM usuarios u LEFT JOIN vendedores v ON u.vendedor_id = v.id
            ORDER BY u.rol DESC, u.username
        """, conn)

# ====================== DATOS FUNCTIONS ======================
def cargar_vendedores():
    with get_db() as conn:
        return pd.read_sql("SELECT id, nombre FROM vendedores ORDER BY nombre", conn)

def obtener_precios_vendedora(vendedor_id):
    with get_db() as conn:
        return pd.read_sql("""
            SELECT p.id as producto_id, p.nombre, p.unidad, 
                   pv.precio_mayor, pv.precio_cliente
            FROM productos p
            JOIN precios_vendedora pv ON p.id = pv.producto_id 
            WHERE pv.vendedor_id = ?
            ORDER BY p.nombre
        """, conn, params=(vendedor_id,))

def guardar_precios_vendedora(vendedor_id, precios_data):
    with get_db() as conn:
        fecha = datetime.now().strftime("%Y-%m-%d %H:%M")
        for prod_id, p_mayor, p_cliente in precios_data:
            conn.execute("""
                INSERT INTO precios_vendedora (vendedor_id, producto_id, precio_mayor, precio_cliente, fecha_actualizacion)
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(vendedor_id, producto_id) 
                DO UPDATE SET precio_mayor=?, precio_cliente=?, fecha_actualizacion=?
            """, (vendedor_id, prod_id, p_mayor, p_cliente, fecha, p_mayor, p_cliente, fecha))
        conn.commit()

def guardar_pedido(vendedor_id, cliente, items, observaciones):
    with get_db() as conn:
        total = sum(item['subtotal'] for item in items)
        c = conn.execute("""
            INSERT INTO pedidos (fecha, vendedor_id, cliente, total, observaciones)
            VALUES (?, ?, ?, ?, ?)
        """, (datetime.now().strftime("%Y-%m-%d %H:%M"), vendedor_id, cliente, total, observaciones))
        pedido_id = c.lastrowid
        for item in items:
            conn.execute("""
                INSERT INTO pedido_detalle (pedido_id, producto_id, cantidad, precio_unitario, subtotal)
                VALUES (?, ?, ?, ?, ?)
            """, (pedido_id, item['producto_id'], item['cantidad'], item['precio_usado'], item['subtotal']))
        conn.commit()
    return pedido_id

def cargar_pedidos(vendedor_id=None):
    """Si vendedor_id es None, carga todos (admin). Si no, filtra por vendedor."""
    with get_db() as conn:
        if vendedor_id:
            return pd.read_sql("""
                SELECT p.id, p.fecha, v.nombre as vendedor, p.cliente, p.total, p.estado, p.observaciones 
                FROM pedidos p LEFT JOIN vendedores v ON p.vendedor_id = v.id 
                WHERE p.vendedor_id = ?
                ORDER BY p.id DESC
            """, conn, params=(vendedor_id,))
        else:
            return pd.read_sql("""
                SELECT p.id, p.fecha, v.nombre as vendedor, p.cliente, p.total, p.estado, p.observaciones 
                FROM pedidos p LEFT JOIN vendedores v ON p.vendedor_id = v.id 
                ORDER BY p.id DESC
            """, conn)

def actualizar_estado(pedido_id, nuevo_estado):
    with get_db() as conn:
        conn.execute("UPDATE pedidos SET estado = ? WHERE id = ?", (nuevo_estado, pedido_id))
        conn.commit()

# ====================== PANTALLA LOGIN ======================
def mostrar_login():
    logo_path = "Logo_Andemix.jpg"
    if os.path.exists(logo_path):
        col1, col2, col3 = st.columns([1, 2, 1])
        with col2:
            st.image(logo_path, width=300)
    elif os.path.exists("Uploads/Logo_Andemix.jpg"):
        col1, col2, col3 = st.columns([1, 2, 1])
        with col2:
            st.image("Uploads/Logo_Andemix.jpg", width=300)

    st.markdown("<h2 style='text-align:center; color:#1b5e20;'>Andemix Pedidos</h2>", unsafe_allow_html=True)
    st.markdown("<p style='text-align:center; color:#555;'>Sistema de Gestión de Pedidos</p>", unsafe_allow_html=True)
    st.markdown("---")

    col1, col2, col3 = st.columns([1, 1.2, 1])
    with col2:
        st.markdown("#### 🔐 Iniciar Sesión")
        username = st.text_input("Usuario", placeholder="tu.usuario")
        password = st.text_input("Contraseña", type="password", placeholder="••••••••")
        
        if st.button("Ingresar", use_container_width=True, type="primary"):
            if username and password:
                user = autenticar(username.strip(), password)
                if user:
                    st.session_state.logged_in = True
                    st.session_state.user_id = user[0]
                    st.session_state.username = user[1]
                    st.session_state.rol = user[2]
                    st.session_state.vendedor_id = user[3]
                    st.session_state.vendedor_nombre = user[4]
                    st.session_state.carrito = []
                    st.rerun()
                else:
                    st.error("❌ Usuario o contraseña incorrectos")
            else:
                st.warning("Por favor ingresa usuario y contraseña")

        with st.expander("ℹ️ Información de acceso"):
            st.caption("Administrador: edwin.mayta / admin1234")
            st.caption("Vendedoras: tu.nombre / tunombre123")
            st.caption("Ejemplo: betelina.torpoco / betelinatorporco123")

# ====================== INTERFAZ PRINCIPAL ======================
def mostrar_app():
    # Header con info de usuario
    col_logo, col_title, col_user = st.columns([2, 3, 2])
    
    logo_path = "Logo_Andemix.jpg"
    with col_logo:
        if os.path.exists(logo_path):
            st.image(logo_path, width=200)
        elif os.path.exists("Uploads/Logo_Andemix.jpg"):
            st.image("Uploads/Logo_Andemix.jpg", width=200)

    with col_title:
        st.title("Andemix Pedidos")
        st.markdown("**Sistema de Gestión de Pedidos**")

    with col_user:
        st.markdown("<br>", unsafe_allow_html=True)
        rol = st.session_state.rol
        nombre_display = "Edwin Mayta (Admin)" if rol == 'admin' else st.session_state.vendedor_nombre
        badge = "🛡️ Administrador" if rol == 'admin' else "👤 Vendedora"
        st.markdown(f"**{badge}**")
        st.markdown(f"*{nombre_display}*")
        if st.button("🚪 Cerrar Sesión", type="secondary"):
            for key in list(st.session_state.keys()):
                del st.session_state[key]
            st.rerun()

    st.markdown("---")

    # Tabs según rol
    if st.session_state.rol == 'admin':
        tabs = st.tabs(["📝 Nuevo Pedido", "💰 Precios", "📋 Todos los Pedidos", "📊 Dashboard", "⚙️ Administración"])
    else:
        tabs = st.tabs(["📝 Nuevo Pedido", "💰 Mis Precios", "📋 Mis Pedidos", "🔑 Mi Cuenta"])

    # ===== TAB: NUEVO PEDIDO =====
    with tabs[0]:
        st.subheader("Nuevo Pedido")
        
        # Admin puede seleccionar vendedora, vendedora ya está fija
        if st.session_state.rol == 'admin':
            vendedores = cargar_vendedores()
            vendedor_nombre = st.selectbox("Vendedora", vendedores['nombre'])
            vendedor_id = int(vendedores[vendedores['nombre'] == vendedor_nombre]['id'].values[0])
        else:
            vendedor_id = st.session_state.vendedor_id
            vendedor_nombre = st.session_state.vendedor_nombre
            st.info(f"📋 Registrando pedido como: **{vendedor_nombre}**")

        precios = obtener_precios_vendedora(vendedor_id)
        cliente = st.text_input("Nombre del Cliente", placeholder="Nombre o negocio")
        observaciones = st.text_area("Observaciones / Dirección", height=80)

        if 'carrito' not in st.session_state:
            st.session_state.carrito = []

        col1, col2 = st.columns([3, 2])

        with col1:
            st.subheader("Agregar al Pedido")
            producto = st.selectbox("Producto", precios['nombre'].tolist())
            prod_row = precios[precios['nombre'] == producto].iloc[0]
            tipo_precio = st.radio("Tipo de Precio", ["Precio por Mayor", "Precio al Cliente"], horizontal=True)
            precio_usado = float(prod_row['precio_mayor'] if tipo_precio == "Precio por Mayor" else prod_row['precio_cliente'])
            st.info(f"**Precio aplicado:** S/. {precio_usado:.2f}")
            cantidad = st.number_input("Cantidad", min_value=0.5, step=0.5, value=1.0)

            if st.button("➕ Agregar al Pedido", use_container_width=True):
                subtotal = round(cantidad * precio_usado, 2)
                st.session_state.carrito.append({
                    'producto_id': int(prod_row['producto_id']),
                    'producto': producto,
                    'cantidad': cantidad,
                    'precio_usado': precio_usado,
                    'tipo_precio': tipo_precio,
                    'subtotal': subtotal
                })
                st.success(f"Agregado: {cantidad} x {producto}")

        with col2:
            st.subheader("Pedido Actual")
            if st.session_state.carrito:
                df_carrito = pd.DataFrame(st.session_state.carrito)
                st.dataframe(df_carrito[['producto', 'cantidad', 'precio_usado', 'tipo_precio', 'subtotal']],
                             hide_index=True, use_container_width=True)
                st.success(f"**TOTAL: S/. {df_carrito['subtotal'].sum():.2f}**")

                col_g, col_c = st.columns(2)
                with col_g:
                    if st.button("✅ Guardar Pedido", type="primary", use_container_width=True):
                        if not cliente or not cliente.strip():
                            st.error("❌ Ingresa el nombre del cliente")
                        else:
                            pid = guardar_pedido(vendedor_id, cliente.strip(), st.session_state.carrito, observaciones)
                            st.balloons()
                            st.success(f"🎉 Pedido #{pid} guardado!")
                            st.session_state.carrito = []
                            st.rerun()
                with col_c:
                    if st.button("🗑️ Limpiar", use_container_width=True):
                        st.session_state.carrito = []
                        st.rerun()
            else:
                st.info("El carrito está vacío")

    # ===== TAB: PRECIOS =====
    with tabs[1]:
        st.subheader("💰 Configurar Precios")
        
        if st.session_state.rol == 'admin':
            vendedores = cargar_vendedores()
            vendedor_nombre_p = st.selectbox("Seleccionar Vendedora", vendedores['nombre'], key="precios_sel")
            vendedor_id_p = int(vendedores[vendedores['nombre'] == vendedor_nombre_p]['id'].values[0])
        else:
            vendedor_id_p = st.session_state.vendedor_id
            vendedor_nombre_p = st.session_state.vendedor_nombre
            st.write(f"**Tus precios actuales, {vendedor_nombre_p}:**")

        precios_actuales = obtener_precios_vendedora(vendedor_id_p)
        st.dataframe(precios_actuales[['nombre', 'precio_mayor', 'precio_cliente']], 
                     hide_index=True, use_container_width=True)

        if st.session_state.rol == 'admin':
            st.subheader("Actualizar Precios")
            nuevos_precios = []
            for _, row in precios_actuales.iterrows():
                col1, col2, col3 = st.columns([3, 2, 2])
                with col1: st.write(f"**{row['nombre']}**")
                with col2:
                    p_mayor = st.number_input("Mayor", value=float(row['precio_mayor']), step=0.5, key=f"mayor_{row['producto_id']}")
                with col3:
                    p_cliente = st.number_input("Cliente", value=float(row['precio_cliente']), step=0.5, key=f"cliente_{row['producto_id']}")
                nuevos_precios.append((int(row['producto_id']), p_mayor, p_cliente))

            if st.button("💾 Guardar Precios", type="primary"):
                guardar_precios_vendedora(vendedor_id_p, nuevos_precios)
                st.success(f"✅ Precios actualizados para **{vendedor_nombre_p}**")
                st.rerun()
        else:
            st.info("💡 Contacta al administrador para actualizar tus precios.")

    # ===== TAB: PEDIDOS =====
    with tabs[2]:
        # Admin ve todos, vendedora solo los suyos
        if st.session_state.rol == 'admin':
            st.subheader("📋 Todos los Pedidos")
            df = cargar_pedidos()
        else:
            st.subheader(f"📋 Mis Pedidos - {st.session_state.vendedor_nombre}")
            df = cargar_pedidos(vendedor_id=st.session_state.vendedor_id)

        if not df.empty:
            filtro = st.selectbox("Filtrar por Estado", ["Todos", "Pendiente", "Confirmado", "Procesado", "Entregado"])
            df_mostrar = df if filtro == "Todos" else df[df['estado'] == filtro]
            st.dataframe(df_mostrar, hide_index=True, use_container_width=True)

            # Solo admin puede cambiar estado
            if st.session_state.rol == 'admin':
                st.subheader("Actualizar Estado")
                col1, col2 = st.columns(2)
                with col1:
                    pedido_id = st.number_input("ID Pedido", min_value=1, step=1)
                with col2:
                    estado_nuevo = st.selectbox("Nuevo Estado", ["Pendiente", "Confirmado", "Procesado", "Entregado"])
                if st.button("Actualizar Estado"):
                    actualizar_estado(pedido_id, estado_nuevo)
                    st.success("Estado actualizado")
                    st.rerun()

            # Exportar Excel (disponible para todos)
            if st.button("📊 Exportar a Excel", type="secondary"):
                import importlib
                output = io.BytesIO()
                if importlib.util.find_spec("openpyxl") is not None:
                    with pd.ExcelWriter(output, engine='openpyxl') as writer:
                        df_mostrar.to_excel(writer, sheet_name='Pedidos', index=False)
                    file_name = f"Andemix_Pedidos_{datetime.now().strftime('%Y%m%d_%H%M')}.xlsx"
                    mime = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                elif importlib.util.find_spec("xlsxwriter") is not None:
                    with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
                        df_mostrar.to_excel(writer, sheet_name='Pedidos', index=False)
                    file_name = f"Andemix_Pedidos_{datetime.now().strftime('%Y%m%d_%H%M')}.xlsx"
                    mime = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                else:
                    output.write(df_mostrar.to_csv(index=False).encode('utf-8-sig'))
                    file_name = f"Andemix_Pedidos_{datetime.now().strftime('%Y%m%d_%H%M')}.csv"
                    mime = "text/csv"
                    st.warning("⚠️ openpyxl no instalado. Descargando como CSV. Agrega openpyxl a requirements.txt")
                st.download_button(
                    label="💾 Descargar archivo",
                    data=output.getvalue(),
                    file_name=file_name,
                    mime=mime
                )
        else:
            st.info("No hay pedidos aún.")

    # ===== TAB 4: DASHBOARD (admin) o MI CUENTA (vendedor) =====
    if st.session_state.rol == 'admin':
        with tabs[3]:
            st.subheader("📊 Dashboard General")
            df = cargar_pedidos()
            if not df.empty:
                c1, c2, c3, c4 = st.columns(4)
                c1.metric("Total Pedidos", len(df))
                c2.metric("Monto Total", f"S/. {df['total'].sum():.2f}")
                c3.metric("Pendientes", len(df[df['estado'] == 'Pendiente']))
                c4.metric("Entregados", len(df[df['estado'] == 'Entregado']))
                st.bar_chart(df.groupby('vendedor')['total'].sum())
                
                st.subheader("Resumen por Vendedora")
                resumen = df.groupby('vendedor').agg(
                    Pedidos=('id', 'count'),
                    Total=('total', 'sum'),
                    Promedio=('total', 'mean')
                ).round(2).reset_index()
                resumen['Total'] = resumen['Total'].apply(lambda x: f"S/. {x:.2f}")
                resumen['Promedio'] = resumen['Promedio'].apply(lambda x: f"S/. {x:.2f}")
                st.dataframe(resumen, hide_index=True, use_container_width=True)
            else:
                st.info("No hay datos suficientes.")

        # ===== TAB 5: ADMINISTRACIÓN (admin) =====
        with tabs[4]:
            st.subheader("⚙️ Administración de Usuarios")
            usuarios = listar_usuarios()
            st.dataframe(usuarios, hide_index=True, use_container_width=True)

            st.markdown("---")
            st.subheader("🔑 Cambiar Contraseña de Usuario")
            user_ids = usuarios['id'].tolist()
            user_names = usuarios['username'].tolist()
            user_options = [f"{uid} - {uname}" for uid, uname in zip(user_ids, user_names)]
            sel = st.selectbox("Seleccionar usuario", user_options)
            new_pass = st.text_input("Nueva contraseña", type="password", key="admin_newpass")
            conf_pass = st.text_input("Confirmar contraseña", type="password", key="admin_confpass")
            if st.button("Cambiar Contraseña", type="primary"):
                if new_pass and new_pass == conf_pass:
                    uid = int(sel.split(" - ")[0])
                    cambiar_password(uid, new_pass)
                    st.success("✅ Contraseña actualizada correctamente")
                elif new_pass != conf_pass:
                    st.error("❌ Las contraseñas no coinciden")
                else:
                    st.warning("Ingresa la nueva contraseña")

            st.markdown("---")
            if st.button("💾 Backup Base de Datos", type="secondary"):
                import shutil
                backup_name = f"backup_andemix_{datetime.now().strftime('%Y%m%d_%H%M%S')}.db"
                shutil.copy('andemix_pedidos.db', backup_name)
                st.success(f"✅ Backup guardado: {backup_name}")

    else:
        # Tab Mi Cuenta para vendedoras
        with tabs[3]:
            st.subheader("🔑 Mi Cuenta")
            st.write(f"**Usuario:** {st.session_state.username}")
            st.write(f"**Nombre:** {st.session_state.vendedor_nombre}")
            st.write(f"**Rol:** Vendedora")
            
            st.markdown("---")
            st.subheader("Cambiar mi Contraseña")
            pass_actual = st.text_input("Contraseña actual", type="password", key="pass_actual")
            pass_nueva = st.text_input("Nueva contraseña", type="password", key="pass_nueva")
            pass_conf = st.text_input("Confirmar nueva contraseña", type="password", key="pass_conf")
            
            if st.button("Actualizar Contraseña", type="primary"):
                if pass_actual and pass_nueva and pass_conf:
                    user = autenticar(st.session_state.username, pass_actual)
                    if not user:
                        st.error("❌ Contraseña actual incorrecta")
                    elif pass_nueva != pass_conf:
                        st.error("❌ Las nuevas contraseñas no coinciden")
                    elif len(pass_nueva) < 6:
                        st.warning("La contraseña debe tener al menos 6 caracteres")
                    else:
                        cambiar_password(st.session_state.user_id, pass_nueva)
                        st.success("✅ Contraseña actualizada correctamente")
                else:
                    st.warning("Completa todos los campos")

    st.markdown("---")
    st.caption("Andemix - El Verdadero Sabor de los Andes © 2026")

# ====================== MAIN ======================
if 'logged_in' not in st.session_state:
    st.session_state.logged_in = False

if not st.session_state.logged_in:
    mostrar_login()
else:
    mostrar_app()
