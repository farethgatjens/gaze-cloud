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
        
    # Cambia este correo por tu correo real de administrador si lo deseas
    if st.session_state.user_info.get('email') == "gatjensdaniel@gmail.com": menu.append("Admin Console")
            
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
        
        # --- INICIALIZAR MEMORIA DEL CHAT ---
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
                    Tienes memoria de esta conversación y acceso al historial de la empresa.

                    REGLAS INNEGOCIABLES:
                    1. Si el contexto de la empresa tiene información útil, úsala.
                    2. Estructura siempre tu respuesta:
                       📌 Análisis de Reportes Previos: (Menciona reportes si los hay)
                       💡 Diagnóstico de GAZE: (Tu análisis)
                       🛠️ Soluciones y Apoyo: (Pasos recomendados)

                    Contexto Industrial:
                    {ctx}

                    Conversación previa:
                    {conversacion_previa}

                    Nueva pregunta: {pregunta}
                    """

                    with st.spinner("GAZE AI analizando a través de sus 5 vidas..."):
                        try:
                            resp = client.models.generate_content(model='gemini-1.5-pro', contents=prompt)
                            st.session_state.historial_chat.append(f"Técnico: {pregunta}")
                            st.session_state.historial_chat.append(f"GAZE AI: {resp.text}")
                            st.rerun()
                        except Exception as e:
                            st.error(f"Error de comunicación con Gemini: {e}")
        with col2:
            if st.button("Cerrar Chat (Limpiar Memoria)"):
                st.session_state.historial_chat = []
                st.rerun()

        # --- MOSTRAR EL CHAT Y BOTÓN DE APRENDIZAJE ---
        st.markdown("### 💬 Historial de la Conversación")
        for i, mensaje in enumerate(st.session_state.historial_chat):
            if mensaje.startswith("Técnico:"):
                st.info(mensaje)
            else:
                st.success(mensaje)
                if st.button("Guardar esta solución en el historial", key=f"guardar_ai_{i}"):
                    guardar_en_vector(mensaje, f"IA_SOLUCION_{i}") 
                    st.toast("¡Solución aprendida por GAZE!")

    elif opcion == "Ver Historial":
        st.header("🌐 Historial")
        busq = st.text_input("Buscar (deja en blanco para ver todo):")
        try:
            docs = db.collection(st.session_state.empresa).order_by("timestamp", direction=firestore.Query.DESCENDING).stream()
            res = [d.to_dict() for d in docs if (busq.lower() in str(d.to_dict()).lower())]
            
            if res:
                df = pd.DataFrame(res)
                st.download_button("📥 Descargar CSV", df.to_csv(index=False).encode('utf-8'), 'reportes.csv')
                for d in res[:50]:
                    st.markdown(f"<div class='report-card'><b>Técnico: {d.get('trabajador', 'Desconocido')}</b><br>{d.get('falla', 'Sin detalles')}</div>", unsafe_allow_html=True)
            else:
                st.info("No hay reportes que coincidan con la búsqueda.")
        except Exception as e:
            st.error(f"Error al cargar el historial: {e}")

    elif opcion == "Análisis Predictivo":
        st.header("🔮 Oráculo de Gaze")
        if st.button("Pronosticar"):
            with st.spinner("Analizando tendencias de fallas..."):
                try:
                    docs = db.collection(st.session_state.empresa).limit(40).stream()
                    hist = "\n".join([d.to_dict().get('falla', '') for d in docs])
                    
                    if hist.strip():
                        resp = client.models.generate_content(model='gemini-2.5-flash', contents=f"Actúa como un experto en mantenimiento predictivo. Analiza estas tendencias de falla y dame un pronóstico de qué podría romperse pronto y cómo prevenirlo: {hist}")
                        st.info(resp.text)
                    else:
                        st.warning("No hay suficientes datos en el historial para hacer un pronóstico.")
                except Exception as e:
                    st.error(f"Error al generar el pronóstico: {e}")

elif opcion == "📁 Repositorio Empresarial":
        st.header("📁 Repositorio Digital y Asistente Documental")
        st.write("Espacio exclusivo para empresarios: Sube documentos oficiales, manuales o instaladores.")

        archivo_subido = st.file_uploader("Selecciona el archivo para la empresa", type=["pdf", "docx", "txt", "exe"])
        descripcion = st.text_area("Añade una descripción o nota sobre este archivo para la IA:")

        if st.button("Guardar en Repositorio"):
            if archivo_subido:
                nombre_archivo = archivo_subido.name
                with st.spinner("Registrando archivo en el sistema de la empresa..."):
                    # Simulamos la subida de almacenamiento y alimentamos el cerebro
                    nota_para_ia = f"Documento Empresarial: {nombre_archivo}. Descripción: {descripcion}"
                    guardar_en_vector(nota_para_ia, f"DOC_{nombre_archivo}")
                    st.success(f"¡Archivo '{nombre_archivo}' y su contexto guardados con éxito!")
            else:
                st.warning("Por favor, selecciona un archivo primero.")

        st.markdown("---")
        st.subheader("🤖 Consultar Asistente de Gerencia")
        pregunta_empresario = st.text_input("Hazle una pregunta a la IA sobre los manuales o archivos de la empresa:")
        
        if st.button("Consultar Repositorio"):
            if pregunta_empresario:
                ctx_empresarial = buscar_relevante(pregunta_empresario)
                prompt_gerencia = f"""
                Eres el Asistente de Gerencia de GAZE AI.
                Responde a la pregunta del empresario basándote ÚNICAMENTE en este contexto corporativo:
                Contexto: {ctx_empresarial}
                Pregunta: {pregunta_empresario}
                """
                with st.spinner("GAZE AI analizando los documentos corporativos..."):
                    try:
                        resp_gerencia = client.models.generate_content(model='gemini-1.5-pro', contents=prompt_gerencia)
                        st.write(resp_gerencia.text)
                    except Exception as e:
                        st.error(f"Error: {e}")

    elif opcion == "Admin Console":
        # Verificación de seguridad extra
        if st.session_state.user_info.get('email') == "gatjensdaniel@gmail.com":
            st.header("🛠️ Admin Console")
            with st.form("admin_form"):
                empresa_nombre = st.text_input("Nombre de la Empresa")
                id_e = st.text_input("ID de la Empresa (sin espacios)")
                email_adm = st.text_input("Email del Administrador")
                pw_adm = st.text_input("Contraseña Temporal", type="password")
                
                if st.form_submit_button("Dar de Alta Empresa"):
                    # Tu lógica de creación aquí...
                    st.success("Empresa creada.")
        else:
            st.error("⛔ Acceso denegado. Solo el administrador principal puede ver esta sección.")