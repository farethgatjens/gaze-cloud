import streamlit as st
import firebase_admin
from firebase_admin import credentials, firestore, auth
from google import genai
import os
import chromadb
from chromadb.utils import embedding_functions
import pandas as pd

# --- INICIALIZACIÓN MODERNA Y CORRECTA ---

# Inicializamos el cliente directamente sin 'configure'
client = genai.Client(api_key=st.secrets["GOOGLE_API_KEY"])

# Ahora, cuando quieras generar contenido, usa el cliente:
# resp = client.models.generate_content(model='gemini-1.5-flash', contents=prompt)

# --- INICIALIZACIÓN DE FIREBASE (Modo Ultra Robusto) ---
if not firebase_admin._apps:
    try:
        # Prioridad 1: Intenta cargar el archivo físico que creaste
        if os.path.exists("firebase_key.json"):
            cred = credentials.Certificate("firebase_key.json")
        else:
            # Prioridad 2: Fallback a los secrets (SIN json.loads)
            cred_dict = dict(st.secrets["FIREBASE_KEY"])
            cred = credentials.Certificate(cred_dict)
            
        firebase_admin.initialize_app(cred)
    except Exception as e:
        st.error(f"🚨 Error crítico al inicializar Firebase: {e}")

try:
    db = firestore.client()
except Exception as e:
    st.error(f"🚨 Error al conectar con la base de datos Firestore: {e}")

try:
    client = genai.Client(api_key=st.secrets["GOOGLE_API_KEY"])
except Exception as e:
    st.error(f"🚨 Error al cargar la API de Google Gemini: {e}")

# --- CONFIGURACIÓN DE CHROMA Y SESIÓN ---
chroma_client = chromadb.PersistentClient(path="./base_datos_gaze")
ef = embedding_functions.DefaultEmbeddingFunction()

if 'user_info' not in st.session_state: 
    st.session_state.user_info = None

def registrar_usuario(email, password, nombre, empresa_id):
    try:
        user = auth.create_user(email=email, password=password)
        db.collection("usuarios").document(user.uid).set({
            "nombre": nombre, "email": email,
            "empresa_id": empresa_id.replace(" ", "_").lower(), "rol": "admin"
        })
        return True
    except Exception as e:
        st.error(f"Error al registrar: {e}")
        return False

# --- INTERFAZ ---
st.set_page_config(page_title="GAZE Cloud", layout="centered")

# --- ESTILIZADO BLACK & RED ---
st.markdown("""
    <style>
    /* Fondo principal */
    .stApp { background-color: #0a0a0a; color: #ffffff; }
    /* Estilo de los botones */
    div.stButton > button { background-color: #d10000; color: white; border: 1px solid #ff0000; border-radius: 5px; }
    div.stButton > button:hover { background-color: #ff0000; border: 1px solid #ffffff; }
    /* Tarjetas de información */
    .stInfo, .stSuccess { background-color: #1a1a1a !important; border-left: 5px solid #d10000 !important; color: #ffffff !important; }
    /* Títulos */
    h1, h2, h3 { color: #d10000 !important; }
    /* Mantener tu clase original para el historial */
    .report-card { background: #161b22; border-left: 4px solid #d10000; padding:10px; margin-bottom:10px; }
    </style>
    
    """, unsafe_allow_html=True)
# --- INTERFAZ DE LOGIN (SOLO LOGIN) ---
if not st.session_state.user_info:
    st.title("🔐 GAZE Cloud - Acceso")
    
    # Eliminamos el st.radio y el Registro. Solo dejamos el login.
    email = st.text_input("Correo")
    pw = st.text_input("Contraseña", type="password")
    
    if st.button("Entrar"):
        try:
            usuarios = db.collection("usuarios").where("email", "==", email).stream()
            user_encontrado = False
            for u in usuarios:
                st.session_state.user_info = u.to_dict()
                st.session_state.empresa = u.to_dict()['empresa_id']
                user_encontrado = True
            
            if user_encontrado:
                st.rerun()
            else:
                st.warning("Credenciales incorrectas o usuario no encontrado.")
        except Exception as e:
            st.error(f"Error al intentar iniciar sesión: {e}")
else:
    nombre_col = f"historia_{st.session_state.empresa}"
    collection = chroma_client.get_or_create_collection(name=nombre_col, embedding_function=ef)

    def guardar_en_vector(texto, id_unico): 
        collection.add(documents=[texto], ids=[id_unico])
        
    def buscar_relevante(query): 
        res = collection.query(query_texts=[query], n_results=3)
        return "\n".join(res['documents'][0]) if res['documents'][0] else "No hay historial."

        st.sidebar.success(f"Hola, {st.session_state.user_info['nombre']}")
        if st.sidebar.button("Cerrar Sesión"): 
            st.session_state.user_info = None
            st.rerun()

    menu = ["Registrar Falla", "Consultar IA", "Análisis Predictivo", "Ver Historial", "📁 Repositorio Empresarial"]
        
    if st.session_state.user_info.get('email') == "gatjensdaniel@gmail.com": 
        menu.append("Admin Console")
            
    opcion = st.sidebar.selectbox("Panel de Control", menu)

    if opcion == "Registrar Falla":
        st.header("📝 Nuevo Reporte")
        nombre_tecnico = st.text_input("Técnico")
        falla = st.text_area("Detalles")
        if st.button("Enviar"):
            if nombre_tecnico and falla:
                ref = db.collection(st.session_state.empresa).document()
                ref.set({"trabajador": nombre_tecnico, "falla": falla, "timestamp": firestore.SERVER_TIMESTAMP})
                guardar_en_vector(falla, ref.id)
                st.success("Reporte procesado e indexado en la base de datos.")
            else:
                st.warning("Por favor, llena ambos campos antes de enviar.")

    elif opcion == "Consultar IA":
        st.header("🧠 Consulta GAZE AI")
        if "historial_chat" not in st.session_state:
            st.session_state.historial_chat = []

        pregunta = st.text_input("¿Qué necesitas resolver o analizar?")
        col1, col2 = st.columns([1, 1])
        with col1:
            if st.button("Generar Diagnóstico / Enviar"):
                if pregunta:
                    ctx = buscar_relevante(pregunta)
                    conversacion_previa = "\n".join(st.session_state.historial_chat[-6:])
                    prompt = f"""
                    Eres GAZE AI, consultor experto en mantenimiento. 
                    REGLAS: Usa el contexto si es útil. 
                    Contexto Industrial: {ctx}
                    Conversación previa: {conversacion_previa}
                    Pregunta: {pregunta}
                    """
                    with st.spinner("GAZE AI analizando..."):
                        try:
                            resp = client.models.generate_content(model='gemini-1.5-pro', contents=prompt)
                            st.session_state.historial_chat.append(f"Técnico: {pregunta}")
                            st.session_state.historial_chat.append(f"GAZE AI: {resp.text}")
                            st.rerun()
                        except Exception as e:
                            st.error(f"Error: {e}")
        with col2:
            if st.button("Cerrar Chat"):
                st.session_state.historial_chat = []
                st.rerun()

        for i, mensaje in enumerate(st.session_state.historial_chat):
            if mensaje.startswith("Técnico:"): st.info(mensaje)
            else:
                st.success(mensaje)
                if st.button("Guardar solución", key=f"guardar_ai_{i}"):
                    guardar_en_vector(mensaje, f"IA_SOLUCION_{i}") 
                    st.toast("¡Solución aprendida!")

    elif opcion == "Ver Historial":
        st.header("🌐 Historial")
        busq = st.text_input("Buscar:")
        try:
            docs = db.collection(st.session_state.empresa).order_by("timestamp", direction=firestore.Query.DESCENDING).stream()
            res = [d.to_dict() for d in docs if (busq.lower() in str(d.to_dict()).lower())]
            if res:
                df = pd.DataFrame(res)
                st.download_button("📥 Descargar CSV", df.to_csv(index=False).encode('utf-8'), 'reportes.csv')
                for d in res[:50]:
                    st.markdown(f"<div class='report-card'><b>Técnico: {d.get('trabajador', 'Desconocido')}</b><br>{d.get('falla', 'Sin detalles')}</div>", unsafe_allow_html=True)
        except Exception as e:
            st.error(f"Error: {e}")

    elif opcion == "Análisis Predictivo":
        st.header("🔮 Oráculo de Gaze")
        if st.button("Pronosticar"):
            with st.spinner("Analizando tendencias..."):
                try:
                    docs = db.collection(st.session_state.empresa).limit(40).stream()
                    hist = "\n".join([d.to_dict().get('falla', '') for d in docs])
                    if hist.strip():
                        resp = client.models.generate_content(model='gemini-1.5-flash', contents=f"Analiza estas fallas y dame un pronóstico: {hist}")
                        st.info(resp.text)
                    else: st.warning("No hay suficientes datos.")
                except Exception as e:
                    st.error(f"Error: {e}")

    elif opcion == "📁 Repositorio Empresarial":
        st.header("📁 Repositorio Digital y Asistente Documental")
        archivo_subido = st.file_uploader("Selecciona el archivo", type=["pdf", "docx", "txt", "exe"])
        descripcion = st.text_area("Descripción:")
        if st.button("Guardar en Repositorio"):
            if archivo_subido:
                guardar_en_vector(f"Doc: {archivo_subido.name}. Desc: {descripcion}", f"DOC_{archivo_subido.name}")
                st.success("Guardado con éxito")
        
        st.markdown("---")
        pregunta_empresario = st.text_input("Pregunta al asistente de gerencia:")
        if st.button("Consultar Repositorio"):
            if pregunta_empresario:
                ctx = buscar_relevante(pregunta_empresario)
                resp = client.models.generate_content(model='gemini-1.5-pro', contents=f"Contexto: {ctx}. Pregunta: {pregunta_empresario}")
                st.write(resp.text)

    elif opcion == "Admin Console":
        if st.session_state.user_info.get('email') == "gatjensdaniel@gmail.com":
            st.header("🛠️ Admin Console")
            with st.form("admin_form"):
                empresa_nombre = st.text_input("Nombre de la Empresa")
                id_e = st.text_input("ID de la Empresa")
                if st.form_submit_button("Dar de Alta Empresa"):
                    st.success("Empresa creada.")
        else:
            st.error("⛔ Acceso denegado.")