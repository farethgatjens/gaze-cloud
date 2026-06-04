Import streamlit as st
import firebase_admin
from firebase_admin import credentials, firestore, auth
from google import genai
import json
import os
import chromadb
from chromadb.utils import embedding_functions
import pandas as pd

# --- INICIALIZACIÓN FIREBASE ---
if not firebase_admin._apps:
    key_dict = json.loads(st.secrets["FIREBASE_KEY"])
    cred = credentials.Certificate(key_dict)
    firebase_admin.initialize_app(cred)
db = firestore.client()
client = genai.Client(api_key=st.secrets["GOOGLE_API_KEY"])

# --- CONFIGURACIÓN CHROMA (PERSISTENTE) ---
chroma_client = chromadb.PersistentClient(path="./base_datos_gaze")
ef = embedding_functions.DefaultEmbeddingFunction()

# --- GESTIÓN DE SESIÓN ---
if 'user_info' not in st.session_state: st.session_state.user_info = None

def registrar_usuario(email, password, nombre, empresa_id):
    try:
        user = auth.create_user(email=email, password=password)
        db.collection("usuarios").document(user.uid).set({
            "nombre": nombre, "email": email,
            "empresa_id": empresa_id.replace(" ", "_").lower(), "rol": "admin"
        })
        return True
    except Exception as e:
        st.error(f"Error: {e}"); return False

# --- DISEÑO ---
st.set_page_config(page_title="GAZE Cloud", layout="centered")
st.markdown("""<style>.report-card{background:#161b22;border-left:4px solid #58a6ff;padding:15px;margin-bottom:15px;border-radius:12px;}</style>""", unsafe_allow_html=True)

if not st.session_state.user_info:
    st.title("🔐 GAZE Cloud - Acceso")
    opcion = st.radio("Acceso", ["Iniciar Sesión", "Registrar Empresa"])
    if opcion == "Registrar Empresa":
        nombre = st.text_input("Tu nombre"); empresa = st.text_input("ID Empresa")
        email = st.text_input("Correo"); pw = st.text_input("Contraseña", type="password")
        if st.button("Crear"):
            if registrar_usuario(email, pw, nombre, empresa): st.success("Cuenta creada.")
    else:
        email = st.text_input("Correo"); pw = st.text_input("Contraseña", type="password")
        if st.button("Entrar"):
            usuarios = db.collection("usuarios").where("email", "==", email).stream()
            for u in usuarios:
                st.session_state.user_info = u.to_dict()
                st.session_state.empresa = u.to_dict()['empresa_id']
                st.rerun()
else:
    # Aislamiento por empresa en Chroma
    nombre_col = f"historia_{st.session_state.empresa}"
    collection = chroma_client.get_or_create_collection(name=nombre_col, embedding_function=ef)

    def guardar_en_vector(texto, id_unico): collection.add(documents=[texto], ids=[id_unico])
    def buscar_relevante(query): 
        res = collection.query(query_texts=[query], n_results=3)
        return "\n".join(res['documents'][0]) if res['documents'][0] else "No hay historial."

    st.sidebar.success(f"Hola, {st.session_state.user_info['nombre']}")
    if st.sidebar.button("Cerrar Sesión"): st.session_state.user_info = None; st.rerun()

    menu = ["Registrar Falla", "Consultar IA", "Análisis Predictivo", "Ver Historial"]
    if st.session_state.user_info['email'] == "gatjensdaniel@gmail.com": menu.append("Admin Console")
    opcion = st.sidebar.selectbox("Panel de Control", menu)

    if opcion == "Registrar Falla":
        st.header("📝 Nuevo Reporte")
        nombre_tecnico = st.text_input("Técnico"); falla = st.text_area("Detalles")
        if st.button("Enviar"):
            ref = db.collection(st.session_state.empresa).document()
            ref.set({"trabajador": nombre_tecnico, "falla": falla, "timestamp": firestore.SERVER_TIMESTAMP})
            guardar_en_vector(falla, ref.id); st.success("Reporte procesado.")

    elif opcion == "Consultar IA":
        st.header("🧠 Consulta GAZE AI")
        pregunta = st.text_input("¿Qué necesitas resolver?")
        if st.button("Generar Diagnóstico"):
            ctx = buscar_relevante(pregunta)
            prompt = f"""
            Eres GAZE AI, un sistema experto de diagnóstico técnico industrial.
            METODOLOGÍA DE ANÁLISIS:
            Antes de responder, realiza una simulación interna de 'Tres Vidas Paralelas':
            1. Vida del Técnico de Campo: Analiza el desgaste físico, condiciones ambientales y urgencia inmediata.
            2. Vida del Analítico de Datos: Calcula probabilidades de falla, patrones recurrentes y vida útil.
            3. Vida del Experto Legendario: Un técnico con décadas de experiencia que ha resuelto situaciones críticas.
            
            Calcula todas las situaciones posibles y soluciones viables desde estas tres perspectivas.
            CONTEXTO: {ctx}
            CONSULTA: {pregunta}
            """
            with st.spinner("GAZE AI está aplicando razonamiento profundo..."):
                resp = client.models.generate_content(model='gemini-2.0-flash', contents=prompt)
                st.info(f"*Diagnóstico de GAZE AI:*\n\n{resp.text}")

    elif opcion == "Ver Historial":
        st.header("🌐 Historial")
        c1, c2 = st.columns(2)
        f_i = c1.date_input("Desde", None); f_f = c2.date_input("Hasta", None)
        busq = st.text_input("Buscar:")
        docs = db.collection(st.session_state.empresa).order_by("timestamp", direction=firestore.Query.DESCENDING).stream()
        res = [d.to_dict() for d in docs if (busq.lower() in str(d.to_dict()).lower())]
        
        if res:
            st.download_button("📥 Descargar CSV", pd.DataFrame(res).to_csv(index=False).encode('utf-8'), 'reportes.csv')
            for d in res[:50]:
                st.markdown(f"<div class='report-card'><b>{d.get('trabajador')}</b><br>{d.get('falla')}</div>", unsafe_html=True)

    elif opcion == "Análisis Predictivo":
        st.header("🔮 Oráculo de Gaze")
        if st.button("Pronosticar"):
            docs = db.collection(st.session_state.empresa).limit(40).stream()
            hist = "\n".join([d.to_dict().get('falla', '') for d in docs])
            resp = client.models.generate_content(model='gemini-2.0-flash', contents=f"Analiza: {hist}")
            st.info(resp.text)

    elif opcion == "Admin Console":
        st.header("🛠️ Admin Console")
        with st.form("admin_form"):
            nombre = st.text_input("Empresa"); id_e = st.text_input("ID"); email = st.text_input("Email"); pw = st.text_input("Pass", type="password")
            if st.form_submit_button("Dar de Alta"):
                try:
                    user = auth.create_user(email=email, password=pw)
                    db.collection("usuarios").document(user.uid).set({"nombre": "Admin", "email": email, "empresa_id": id_e, "rol": "admin"})
                    st.success("Empresa creada.")
                except Exception as e: st.error(e)

