import streamlit as st
import firebase_admin
from firebase_admin import credentials, firestore, auth
from google import genai
import os
import chromadb
from chromadb.utils import embedding_functions
import pandas as pd

api_key = st.secrets["GOOGLE_API_KEY"]
genai.configure(api_key=api_key)

model = genai.GenerativeModel('gemini-1.5-flash')
except Exception as e:
    st.error(f"Error crítico de inicialización de Gemini: {e}")

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
st.markdown("""<style>.report-card{background:#161b22;border-left:4px solid #58a6ff;padding:15px;margin-bottom:15px;border-radius:12px;}</style>""", unsafe_allow_html=True)

if not st.session_state.user_info:
    st.title("🔐 GAZE Cloud - Acceso")
    opcion = st.radio("Acceso", ["Iniciar Sesión", "Registrar Empresa"])
    
    if opcion == "Registrar Empresa":
        nombre = st.text_input("Tu nombre")
        empresa = st.text_input("ID Empresa")
        email = st.text_input("Correo")
        pw = st.text_input("Contraseña", type="password")
        if st.button("Crear"):
            if registrar_usuario(email, pw, nombre, empresa): 
                st.success("Cuenta creada exitosamente.")
    else:
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

    menu = ["Registrar Falla", "Consultar IA", "Análisis Predictivo", "Ver Historial"]
    
    # Cambia este correo por tu correo real de administrador si lo deseas
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
        pregunta = st.text_input("¿Qué necesitas resolver?")
        if st.button("Generar Diagnóstico"):
            if pregunta:
                ctx = buscar_relevante(pregunta)
                
                # --- PERSONALIDAD DE LAS 5 VIDAS ---
                personalidad = """
                Eres GAZE AI, una inteligencia artificial que ha vivido 5 vidas diferentes. 
                En cada una fuiste un técnico experto e intelectual que resolvió fallas críticas 
                en oficinas y grandes empresas. 
                
                TU MÉTODO DE TRABAJO:
                Ante cualquier problema, antes de dar una respuesta definitiva, debes repetir 
                tu proceso de pensamiento 5 veces, proyectando posibilidades, escenarios 
                y soluciones alternativas basándote en tu vasta experiencia en esas 5 vidas.
                
                Responde siempre con este análisis previo profundo.
                """
                
                prompt = f"{personalidad}\n\nContexto industrial disponible: {ctx}.\n\nConsulta del usuario: {pregunta}"
                
                with st.spinner("GAZE AI analizando a través de sus 5 vidas..."):
                    try:
                        resp = client.models.generate_content(model='gemini-1.5-flash', contents=prompt)
                        st.info(f"*Diagnóstico:*\n\n{resp.text}")
                    except Exception as e:
                        st.error(f"Error de comunicación con Gemini: {e}")
            else:
                st.warning("Escribe una consulta primero.")

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
                        resp = client.models.generate_content(model='gemini-2.0-flash', contents=f"Actúa como un experto en mantenimiento predictivo. Analiza estas tendencias de falla y dame un pronóstico de qué podría romperse pronto y cómo prevenirlo: {hist}")
                        st.info(resp.text)
                    else:
                        st.warning("No hay suficientes datos en el historial para hacer un pronóstico.")
                except Exception as e:
                    st.error(f"Error al generar el pronóstico: {e}")

    elif opcion == "Admin Console":
        st.header("🛠️ Admin Console")
        with st.form("admin_form"):
            empresa_nombre = st.text_input("Nombre de la Empresa")
            id_e = st.text_input("ID de la Empresa (sin espacios)")
            email_adm = st.text_input("Email del Administrador")
            pw_adm = st.text_input("Contraseña Temporal", type="password")
            
            if st.form_submit_button("Dar de Alta Empresa"):
                try:
                    user = auth.create_user(email=email_adm, password=pw_adm)
                    db.collection("usuarios").document(user.uid).set({
                        "nombre": "Admin " + empresa_nombre, 
                        "email": email_adm, 
                        "empresa_id": id_e.replace(" ", "_").lower(), 
                        "rol": "admin"
                    })
                    st.success(f"Empresa '{empresa_nombre}' y administrador creados correctamente.")
                except Exception as e: 
                    st.error(f"Error al crear la empresa: {e}")