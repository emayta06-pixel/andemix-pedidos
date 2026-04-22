import io
import streamlit as st
import sqlite3
import pandas as pd
from datetime import datetime
import os

st.set_page_config(page_title="Andemix Pedidos", page_icon="🏔️", layout="wide")

# ====================== ESTILO ======================
st.markdown("""
<style>
    .main {background-color: #f8f9fa;}
    .stButton>button {background-color: #1b5e20; color: white; font-weight: bold;}
    .stButton>button:hover {background-color: #145a17;}
    h1, h2, h3 {color: #1b5e20;}
</style>
""", unsafe_allow_html=True)

# Logo
logo_path = "Logo_Andemix.jpg"
if os.path.exists(logo_path):
    st.image(logo_path, width=450)
elif os.path.exists("Uploads/Logo_Andemix.jpg"):
    st.image("Uploads/Logo_Andemix.jpg", width=450)

st.title("Andemix Pedidos")
st.markdown("**Sistema de Gestión de Pedidos**")

# ====================== BASE DE DATOS ======================
def get_db():
    return sqlite3.connect('andemix_pedidos.db')

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
        -- Recrear tabla pedido_detalle con todas las columnas necesarias
        DROP TABLE IF EXISTS pedido_detalle;
        CREATE TABLE pedido_detalle (
            id INTEGER PRIMARY KEY, 
            pedido_id INTEGER, 
            producto_id INTEGER,
            cantidad REAL, 
            precio_unitario REAL,
            subtotal REAL,
            FOREIGN KEY(pedido_id) REFERENCES pedidos(id)
        );
    ''')
    
    # Vendedores
    vendedores_list = ['Batelina Torpoco', 'Maria Pajuelo', 'Flor Pajuelo', 'Jenny Mayta', 
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
    
    conn.commit()

# ====================== FUNCIONES ======================
def cargar_vendedores():
    with get_db() as conn:
        return pd.read_sql("SELECT id, nombre FROM vendedores ORDER BY nombre", conn)

def obtener_precios_vendedora(vendedor_id):
    with get_db() as conn:
        df = pd.read_sql("""
            SELECT p.id as producto_id, p.nombre, p.unidad, 
                   pv.precio_mayor, pv.precio_cliente
            FROM productos p
            JOIN precios_vendedora pv ON p.id = pv.producto_id 
            WHERE pv.vendedor_id = ?
            ORDER BY p.nombre
        """, conn, params=(vendedor_id,))
        return df

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

def cargar_pedidos():
    with get_db() as conn:
        return pd.read_sql("""
            SELECT p.id, p.fecha, v.nombre as vendedor, p.cliente, p.total, p.estado, p.observaciones 
            FROM pedidos p LEFT JOIN vendedores v ON p.vendedor_id = v.id 
            ORDER BY p.id DESC
        """, conn)

def actualizar_estado(pedido_id, nuevo_estado):
    with get_db() as conn:
        conn.execute("UPDATE pedidos SET estado = ? WHERE id = ?", (nuevo_estado, pedido_id))
        conn.commit()

# ====================== INTERFAZ ======================
tabs = st.tabs(["📝 Nuevo Pedido", "💰 Mis Precios", "📋 Ver Pedidos", "📊 Dashboard"])

with tabs[0]:
    st.subheader("Nuevo Pedido")
    vendedores = cargar_vendedores()
    vendedor_nombre = st.selectbox("Vendedora", vendedores['nombre'])
    vendedor_id = int(vendedores[vendedores['nombre'] == vendedor_nombre]['id'].values[0])
    
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
            st.success(f"Agregado: {cantidad} x {producto} ({tipo_precio})")
    
    with col2:
        st.subheader("Pedido Actual")
        if st.session_state.carrito:
            df_carrito = pd.DataFrame(st.session_state.carrito)
            st.dataframe(df_carrito[['producto', 'cantidad', 'precio_usado', 'tipo_precio', 'subtotal']], 
                        hide_index=True, use_container_width=True)
            st.success(f"**TOTAL: S/. {df_carrito['subtotal'].sum():.2f}**")
            
            if st.button("✅ Guardar Pedido", type="primary", use_container_width=True):
                if not cliente or not cliente.strip():
                    st.error("❌ Ingresa el nombre del cliente")
                else:
                    pid = guardar_pedido(vendedor_id, cliente.strip(), st.session_state.carrito, observaciones)
                    st.balloons()
                    st.success(f"🎉 Pedido #{pid} guardado correctamente!")
                    st.session_state.carrito = []
                    st.rerun()
        else:
            st.info("El carrito está vacío")

with tabs[1]:
    st.subheader("💰 Configurar Mis Precios")
    vendedores = cargar_vendedores()
    vendedor_nombre = st.selectbox("Seleccionar Vendedora", vendedores['nombre'], key="precios_vendedora")
    vendedor_id = int(vendedores[vendedores['nombre'] == vendedor_nombre]['id'].values[0])
    
    st.write(f"**Configurando precios para:** {vendedor_nombre}")
    precios_actuales = obtener_precios_vendedora(vendedor_id)
    st.dataframe(precios_actuales[['nombre', 'precio_mayor', 'precio_cliente']], hide_index=True, use_container_width=True)
    
    st.subheader("Actualizar Precios")
    nuevos_precios = []
    for _, row in precios_actuales.iterrows():
        col1, col2, col3 = st.columns([3, 2, 2])
        with col1: st.write(f"**{row['nombre']}**")
        with col2: 
            p_mayor = st.number_input("Precio por Mayor", value=float(row['precio_mayor']), step=0.5, key=f"mayor_{row['producto_id']}")
        with col3: 
            p_cliente = st.number_input("Precio al Cliente", value=float(row['precio_cliente']), step=0.5, key=f"cliente_{row['producto_id']}")
        nuevos_precios.append((int(row['producto_id']), p_mayor, p_cliente))
    
    if st.button("💾 Guardar Precios", type="primary"):
        guardar_precios_vendedora(vendedor_id, nuevos_precios)
        st.success(f"Precios actualizados para **{vendedor_nombre}**")
        st.rerun()

with tabs[2]:
    st.subheader("📋 Todos los Pedidos")
    df = cargar_pedidos()
    if not df.empty:
        filtro = st.selectbox("Estado", ["Todos", "Pendiente", "Confirmado", "Procesado", "Entregado"])
        df_mostrar = df if filtro == "Todos" else df[df['estado'] == filtro]
        st.dataframe(df_mostrar, hide_index=True, use_container_width=True)
        
        st.subheader("Actualizar Estado")
        col1, col2 = st.columns(2)
        with col1: pedido_id = st.number_input("ID Pedido", min_value=1, step=1)
        with col2: estado_nuevo = st.selectbox("Nuevo Estado", ["Pendiente","Confirmado","Procesado","Entregado"])
        if st.button("Actualizar Estado"):
            actualizar_estado(pedido_id, estado_nuevo)
            st.success("Estado actualizado")
            st.rerun()
    else:
        st.info("No hay pedidos aún.")

with tabs[3]:
    st.subheader("📊 Dashboard")
    df = cargar_pedidos()
    if not df.empty:
        c1,c2,c3 = st.columns(3)
        c1.metric("Total Pedidos", len(df))
        c2.metric("Monto Total", f"S/. {df['total'].sum():.2f}")
        c3.metric("Pendientes", len(df[df['estado']=='Pendiente']))
        st.bar_chart(df.groupby('vendedor')['total'].sum())
    else:
        st.info("No hay datos suficientes.")

# ====================== EXPORTAR EXCEL ======================
with tabs[2]:  # En la pestaña "Ver Pedidos"
    if st.button("📊 Exportar Todos los Pedidos a Excel", type="secondary", use_container_width=True):
        df = cargar_pedidos()
        if not df.empty:
            output = io.BytesIO()
            with pd.ExcelWriter(output, engine='openpyxl') as writer:
                df.to_excel(writer, sheet_name='Pedidos', index=False)
            st.download_button(
                label="💾 Descargar Excel",
                data=output.getvalue(),
                file_name=f"Andemix_Pedidos_{datetime.now().strftime('%Y%m%d_%H%M')}.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )
        else:
            st.info("No hay pedidos para exportar")
# ====================== BACKUP AUTOMÁTICO ======================
if st.button("💾 Backup Base de Datos", type="secondary"):
    import shutil
    backup_name
st.caption("Andemix - El Verdadero Sabor de los Andes © 2026")