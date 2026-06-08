import streamlit as st
import firebase_admin
from firebase_admin import credentials, firestore, auth
from google import genai
import os
import chromadb
from chromadb.utils import embedding_functions
import pandas as pd

# --- INICIALIZACIÓN ---
client = genai.Client(api_key=st.secrets["GOOGLE_API_KEY"])

if not firebase_admin._apps:
    try:
        if os.path.exists("firebase_key.json"):
            cred = credentials.Certificate("firebase_key.json")
        else:
            cred_dict = dict(st.secrets["FIREBASE_KEY"])
            cred = credentials.Certificate(cred_dict)
        firebase_admin.initialize_app(cred)
    except Exception as e:
        st.error(f"🚨 Error crítico al inicializar Firebase: {e}")

db = firestore.client()
chroma_client = chromadb.PersistentClient(path="./base_datos_gaze")
ef = embedding_functions.DefaultEmbeddingFunction()

if 'user_info' not in st.session_state: 
    st.session_state.user_info = None

# --- ESTILIZADO PROFESIONAL ---
st.set_page_config(page_title="GAZE Cloud", layout="centered")
st.markdown("""
    <style>
    .stApp { background-color: #050505; color: #e0e0e0; }
    .glass-card {
        background-color: #121212;
        padding: 30px;
        border-radius: 15px;
        border: 1px solid #2b2b2b;
        box-shadow: 0 8px 32px 0 rgba(209, 0, 0, 0.15);
    }
    div.stButton > button { 
        background-color: #d10000; color: white; border: none; 
        border-radius: 6px; padding: 10px 20px; font-weight: bold; width: 100%; transition: 0.3s;
    }
    div.stButton > button:hover { background-color: #ff0000; transform: translateY(-2px); }
    h1, h2, h3 { color: #d10000 !important; }
    .report-card { background: #161b22; border-left: 4px solid #d10000; padding:15px; margin-bottom:10px; border-radius: 5px; }
    </style>
    """, unsafe_allow_html=True)

# --- LOGIN ---
if not st.session_state.user_info:
    c1, c2, c3 = st.columns([1, 2, 1])
    with c2:
        st.markdown("<div class='glass-card'>", unsafe_allow_html=True)
        st.markdown("<h1 style='text-align: center;'>🔐 GAZE Cloud</h1>", unsafe_allow_html=True)
        email = st.text_input("Correo Electrónico")
        pw = st.text_input("Contraseña", type="password")
        if st.button("ACCEDER AL SISTEMA"):
            usuarios = db.collection("usuarios").where("email", "==", email).stream()
            for u in usuarios:
                st.session_state.user_info = u.to_dict()
                st.session_state.empresa = u.to_dict()['empresa_id']
                st.rerun()
            st.warning("Credenciales incorrectas.")
        st.markdown("</div>", unsafe_allow_html=True)

# --- PANEL PRINCIPAL ---
else:
    nombre_col = f"historia_{st.session_state.empresa}"
    collection = chroma_client.get_or_create_collection(name=nombre_col, embedding_function=ef)

    def guardar_en_vector(texto, id_unico): collection.add(documents=[texto], ids=[id_unico])
    def buscar_relevante(query): 
        res = collection.query(query_texts=[query], n_results=3)
        return "\n".join(res['documents'][0]) if res['documents'][0] else "No hay historial."

    st.sidebar.success(f"Hola, {st.session_state.user_info['nombre']}")
    if st.sidebar.button("Cerrar Sesión"): 
        st.session_state.user_info = None
        st.rerun()

    menu = ["Registrar Falla", "Consultar IA", "Análisis Predictivo", "Ver Historial", "📁 Repositorio Empresarial"]
    if st.session_state.user_info.get('email') == "gatjensdaniel@gmail.com": menu.append("Admin Console")
    opcion = st.sidebar.selectbox("Panel de Control", menu)

    st.markdown("<div class='glass-card'>", unsafe_allow_html=True)

    if opcion == "Registrar Falla":
        st.header("📝 Nuevo Reporte")
        nombre_tecnico = st.text_input("Técnico")
        falla = st.text_area("Detalles de la falla", height=150)
        if st.button("Enviar Reporte"):
            ref = db.collection(st.session_state.empresa).document()
            ref.set({"trabajador": nombre_tecnico, "falla": falla, "timestamp": firestore.SERVER_TIMESTAMP})
            guardar_en_vector(falla, ref.id)
            st.success("Reporte procesado.")

    
    elif opcion == "Consultar IA":
        st.header("🧠 Consulta GAZE AI")
        if "historial_chat" not in st.session_state: st.session_state.historial_chat = []
        
        pregunta = st.text_input("¿Qué necesitas resolver o analizar?")
        if st.button("Generar Diagnóstico / Enviar"):
            if pregunta:
                ctx = buscar_relevante(pregunta)
                conversacion_previa = "\n".join(st.session_state.historial_chat[-6:])
                
                # --- RECUPERANDO EL RAZONAMIENTO EXPERTO ---
                prompt = f"""
                Eres GAZE AI, consultor experto en mantenimiento,empresario,accesor,secretario. 
                Tienes memoria de esta conversación y acceso al historial de la empresa.


                REGLAS INNEGOCIABLES:
                1. Si el contexto de la empresa tiene información útil, úsala.
                2. Estructura siempre tu respuesta:
                   📌 Análisis de Reportes Previos: (Menciona reportes si los hay)
                   💡 Diagnóstico de GAZE: (Tu análisis)
                   🛠️ Soluciones y Apoyo: (Pasos recomendados)

                Contexto Industrial: {ctx}
                Conversación previa: {conversacion_previa}
                Nueva pregunta: {pregunta}
                """
                
                with st.spinner("GAZE AI analizando a través de sus 5 vidas..."):
                    try:
                        resp = client.models.generate_content(model='gemini-2.5-flash', contents=prompt)
                        st.session_state.historial_chat.append(f"Técnico: {pregunta}")
                        st.session_state.historial_chat.append(f"GAZE AI: {resp.text}")
                        st.rerun()
                    except Exception as e:
                        st.error(f"Error: {e}")
        
        # Mostrar historial con estilos
        for i, mensaje in enumerate(st.session_state.historial_chat):
            if mensaje.startswith("Técnico:"): st.info(mensaje)
            else:
                st.success(mensaje)
                if st.button("Guardar solución", key=f"guardar_ai_{i}"):
                    guardar_en_vector(mensaje, f"IA_SOLUCION_{i}") 
                    st.toast("¡Solución aprendida!")

    elif opcion == "Ver Historial":
        st.header("🌐 Historial de Reportes")
        docs = db.collection(st.session_state.empresa).order_by("timestamp", direction=firestore.Query.DESCENDING).stream()
        for d in docs:
            d_dict = d.to_dict()
            st.markdown(f"<div class='report-card'><b>{d_dict.get('trabajador')}</b><br>{d_dict.get('falla')}</div>", unsafe_allow_html=True)

    elif opcion == "Análisis Predictivo":
        st.header("🔮 Oráculo de Gaze")
        if st.button("Ejecutar Pronóstico"):
            docs = db.collection(st.session_state.empresa).limit(20).stream()
            hist = "\n".join([d.to_dict().get('falla', '') for d in docs])
            resp = client.models.generate_content(model='gemini-2.5-flash', contents=f"Analiza: {hist}")
            st.info(resp.text)

    elif opcion == "📁 Repositorio Empresarial":
        st.header("📁 Repositorio Digital")
        archivo = st.file_uploader("Subir Archivo", type=["pdf", "txt", "docx"])
        desc = st.text_area("Descripción")
        if st.button("Guardar en Repositorio"):
            guardar_en_vector(f"Doc: {archivo.name}. Desc: {desc}", f"DOC_{archivo.name}")
            st.success("Guardado con éxito")

    elif opcion == "Admin Console":
        st.header("🛠️ Admin Console")
        with st.form("admin_form"):
            empresa_nombre = st.text_input("Nombre de la Empresa")
            id_e = st.text_input("ID de la Empresa")
            email_adm = st.text_input("Email del Admin")
            pw_adm = st.text_input("Contraseña Temporal", type="password")
            if st.form_submit_button("Dar de Alta Empresa"):
                st.success("Empresa creada correctamente.")
    
    st.markdown("</div>", unsafe_allow_html=True)