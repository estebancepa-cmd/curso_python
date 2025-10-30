import pandas as pd
import plotly.express as px
import streamlit as st
import geocoder
from geopy.distance import geodesic
from datetime import datetime, timedelta
import os
import requests


# ----------------------------------------
# FUNCIONES COMUNES
# ----------------------------------------
@st.cache_data(ttl=3600)
def reconfigura(df, datos):
    try:  
        # Seleccionar solo las columnas que necesitamos
        columnas_seleccionadas =['C.P.', 'Dirección', 'Horario', 'Latitud','Localidad','Longitud (WGS84)','Municipio', 'Precio Gasoleo A', 'Precio Gasolina 95 E5', 'Precio Gasolina 95 E5 Premium','Provincia','Remisión','Rótulo','Tipo Venta', 'IDEESS', 'IDMunicipio', 'IDProvincia', 'IDCCAA']
        # Filtrar columnas (solo las que existan en el DataFrame)
        columnas_disponibles = [col for col in columnas_seleccionadas if col in df.columns]
        df = df[columnas_disponibles]
        
        
        # Limpiar y convertir columnas de precios (reemplazar coma por punto)
        columnas_precio = [col for col in df.columns if 'Precio' in col]
        st.write(columnas_precio)
        for col in columnas_precio:
            df[col] = df[col].str.replace(',', '.').replace('', None)
            df[col] = pd.to_numeric(df[col], errors='coerce')
        
        st.write(f"✓ Datos obtenidos correctamente: {len(df)} estaciones")
        st.write(f"✓ Fecha de actualización: {datos.get('Fecha', 'No disponible')}")
        
        df = df.rename(columns={'Latitud': 'lat', 'Longitud (WGS84)': 'lon'})
        df = df.dropna(subset=['lat', 'lon'])
        df['lat'] = df['lat'].str.replace(',', '.')
        df['lon'] = df['lon'].str.replace(',', '.')
        df['lat'] = pd.to_numeric(df['lat'], errors='coerce')
        df['lon'] = pd.to_numeric(df['lon'], errors='coerce')
        return df
    except Exception as e:
        st.write(f"Error en código reconfigura : {e}")
        return None

def obtener_precios_carburantes(codigo_provincia):
    """
    Obtiene los precios de carburantes de una provincia desde la API del Ministerio.
    
    Parámetros:
    -----------
    codigo_provincia : str o int
        Código de la provincia (por ejemplo, '08' para Barcelona, '28' para Madrid)
    
    Retorna:
    --------
    pandas.DataFrame
        DataFrame con la información de las estaciones de servicio y precios
    """
    
    # Construir la URL
    url = f"https://energia.serviciosmin.gob.es/ServiciosRESTCarburantes/PreciosCarburantes/EstacionesTerrestres/FiltroProvincia/{codigo_provincia}"
    try:
        # Realizar la petición
        response = requests.get(url)
        response.raise_for_status()
        
        # Parsear el JSON
        datos = response.json()
        
        # Extraer la lista de estaciones
        estaciones = datos.get('ListaEESSPrecio', [])
        
        # Crear DataFrame
        df = pd.DataFrame(estaciones)
        
        return df, datos
    
    except Exception as e:
        st.write(f"✗ Error al obtener datos desde internet: {e}")
        return None
  



def calcular_distancia(row):
    try:  
        return geodesic(user_location, (row['lat'], row['lon'])).km
    except:
        return None

def mostrar_gasoli_cercanas(df):
    st.subheader("🗺️ Mapa de gasolineras cercanas")
    fig = px.scatter_mapbox(
        df_filtrado,
        lat="lat",
        lon="lon",
        hover_name="Rótulo",
        hover_data=["Municipio", tipo_combustible, "distancia_km"],
        color=tipo_combustible,
        color_continuous_scale="Turbo",
        zoom=10,
        height=500
    )
    fig.update_layout(mapbox_style="open-street-map", margin={"r":0,"t":0,"l":0,"b":0})
    st.plotly_chart(fig, use_container_width=True)

def enlaces_google_maps(df_filtrado):
    st.subheader("🚗 Cómo llegar")
    for _, row in df_filtrado.head(5).iterrows():
        enlace = f"https://www.google.com/maps/dir/{user_location[0]},{user_location[1]}/{row['lat']},{row['lon']}"
        st.markdown(f"**{row['Rótulo']} - {row['Municipio']}** → [📍 Ver ruta en Google Maps]({enlace})")

def precios_promedio(hist_file):
    hist = pd.read_csv(hist_file)
    hist["Fecha"] = pd.to_datetime(hist["Fecha"], errors='coerce')

    tipo_combustible = st.selectbox("Selecciona combustible", combustibles, key="comb2")

    ultimos_dias = hist[
        (hist["Combustible"] == tipo_combustible) &
        (hist["Fecha"] >= datetime.now() - timedelta(days=14))
    ]

    if not ultimos_dias.empty:
        fig2 = px.line(
            ultimos_dias,
            x="Fecha",
            y="Precio Medio",
            markers=True,
            title=f"Evolución últimos 14 días - {tipo_combustible}",
            color_discrete_sequence=["#2E86DE"]
        )
        st.plotly_chart(fig2, use_container_width=True)
    else:
        st.info("Aún no hay datos suficientes para este combustible.")

def guardar_evolucion_diaria(df_filtrado,hist_file):
    fecha_actual = datetime.now().strftime("%Y-%m-%d")
    precio_prom = round(df_filtrado[tipo_combustible].mean(), 3)

    if not os.path.exists(hist_file):
        hist = pd.DataFrame(columns=["Fecha", "Combustible", "Precio Medio"])
    else:
        hist = pd.read_csv(hist_file)

    if not ((hist["Fecha"] == fecha_actual) & (hist["Combustible"] == tipo_combustible)).any():
        nuevo = pd.DataFrame([[fecha_actual, tipo_combustible, precio_prom]], columns=["Fecha", "Combustible", "Precio Medio"])
        hist = pd.concat([hist, nuevo], ignore_index=True)
        hist.to_csv(hist_file, index=False)

def evolucion_precios(hist_file):
    hist = pd.read_csv(hist_file)
    hist["Fecha"] = pd.to_datetime(hist["Fecha"], errors='coerce')

    dias = st.slider("Días a mostrar", 3, 30, 14)

    ultimos = hist[hist["Fecha"] >= datetime.now() - timedelta(days=dias)]

    if ultimos.empty:
        st.info("No hay datos suficientes todavía. Recolecta algunos días más.")
    else:
        fig3 = px.line(
            ultimos,
            x="Fecha",
            y="Precio Medio",
            color="Combustible",
            markers=True,
            title=f"Evolución comparativa últimos {dias} días",
            color_discrete_sequence=px.colors.qualitative.Bold
        )
        st.plotly_chart(fig3, use_container_width=True)

        resumen = ultimos.groupby("Combustible")["Precio Medio"].mean().reset_index()
        st.write("💡 **Precio promedio en el período:**")
        st.dataframe(resumen)
        
def comparativa_evolucion_precios(hist_file):
    hist = pd.read_csv(hist_file)
    hist["Fecha"] = pd.to_datetime(hist["Fecha"], errors='coerce')

    dias = st.slider("Días a mostrar", 3, 30, 14)

    ultimos = hist[hist["Fecha"] >= datetime.now() - timedelta(days=dias)]

    if ultimos.empty:
        st.info("No hay datos suficientes todavía. Recolecta algunos días más.")
    else:
        fig3 = px.line(
            ultimos,
            x="Fecha",
            y="Precio Medio",
            color="Combustible",
            markers=True,
            title=f"Evolución comparativa últimos {dias} días",
            color_discrete_sequence=px.colors.qualitative.Bold
        )
        st.plotly_chart(fig3, use_container_width=True)

        resumen = ultimos.groupby("Combustible")["Precio Medio"].mean().reset_index()
        st.write("💡 **Precio promedio en el período:**")
        st.dataframe(resumen)

def existe_historico(hist_file):
    if os.path.exists(hist_file):
        return True
    else:
        st.warning("Aún no hay datos históricos. Usa la pestaña principal para generar registros.")
        return False
#----- Inicio programa
# ----------------------------------------
# CONFIGURACIÓN GENERAL
# ----------------------------------------
st.set_page_config(page_title="⛽ Gasolineras Barcelona", layout="wide")
st.title("⛽ Dashboard de Gasolineras en Barcelona")

# ----------------------------------------
# PESTAÑAS DEL DASHBOARD
# ----------------------------------------
tab1, tab2, tab3 = st.tabs(["📍 Gasolineras Cercanas", "📈 Evolución Individual", "⚖️ Comparativa de Combustibles"])

# Ejemplo con Barcelona (código 08)
codigo_provincia = "08"

df, datos = obtener_precios_carburantes(codigo_provincia)
df = reconfigura(df, datos)
if df is not None:
    # Mostrar información básica
    st.write(f"\nColumnas disponibles: {df.columns.tolist()}")
    st.write(f"\nPrimeras filas:")

# Tipos de combustible disponibles
combustibles = ["Precio Gasolina 95 E5", "Precio Gasoleo A", "Precio Gasolina 95 E5 Premium"]

# Archivo local para histórico
hist_file = "./dat/historial_precios.csv"

# ----------------------------------------
# PESTAÑA 1: GASOLINERAS CERCANAS
# ----------------------------------------
with tab1:
    st.subheader("📍 Gasolineras más cercanas a tu ubicación")

    # Detectar ubicación automática
    g = geocoder.ip('me')
    if g.latlng:
        lat  = 41.387027
        lon  = 2.170024
        user_location = g.latlng
        user_location = (lat, lon) # provoco que coja Barcelona
        st.success(f"Ubicación detectada: {user_location}")
    else:
        st.warning("No se pudo detectar automáticamente. Ingresa tu ubicación manualmente:")
        lat = st.number_input("Latitud", value=40.4168)
        lon = st.number_input("Longitud", value=-3.7038)
        user_location = (lat, lon)

    tipo_combustible = st.selectbox("Tipo de combustible", combustibles)
    dist_max = st.slider("Distancia máxima (km)", 5, 100, 25)

    # Limpiar y calcular distancia 
    df_temp = df

    #st.spinner("Calculando distancias..."):
    if df_temp is not None:
        df_temp['distancia_km'] = df_temp.apply(calcular_distancia, axis=1)
        df_filtrado = df_temp[df_temp['distancia_km'] <= dist_max].sort_values('distancia_km')
      
        # Mostrar mapa de gasolineras cercanas
        mostrar_gasoli_cercanas(df_filtrado)

        # Guardar evolución diaria
        guardar_evolucion_diaria(df_filtrado, hist_file)

        # Enlaces a Google Maps
        enlaces_google_maps(df_filtrado)
    else:
        st.error("No se ha encontrado datos")
# ----------------------------------------
# PESTAÑA 2: EVOLUCIÓN INDIVIDUAL
# ----------------------------------------
with tab2:
    st.subheader("📈 Evolución de precios promedio")

    if existe_historico(hist_file):
        precios_promedio(hist_file)

# ----------------------------------------
# PESTAÑA 3: COMPARATIVA ENTRE COMBUSTIBLES
# ----------------------------------------
with tab3:
    st.subheader("⚖️ Comparativa de evolución de precios")

    if existe_historico(hist_file):
        comparativa_evolucion_precios(hist_file)
