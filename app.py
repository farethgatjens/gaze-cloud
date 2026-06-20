import streamlit as st
import firebase_admin
from firebase_admin import credentials, firestore, auth
import os
import pandas as pd
from pinecone import Pinecone 
import google.generativeai as genai
genai.configure(api_key=st.secrets["GOOGLE_API_KEY"])

# Inicializar Pinecone (Reemplaza a ChromaDB)
pc = Pinecone(api_key=st.secrets["PINECONE_API_KEY"])
index = pc.Index("jupiter-db")

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

if 'user_info' not in st.session_state: 
    st.session_state.user_info = None

# --- ESTILIZADO PROFESIONAL ---
st.set_page_config(page_title="GAZE Cloud", layout="centered")
st.markdown("""
    <style>
    .stApp { background-color: #050505; color: #e0e0e0; }
    .glass-card {
        background-color: #121212; padding: 30px; border-radius: 15px;
        border: 1px solid #2b2b2b; box-shadow: 0 8px 32px 0 rgba(209, 0, 0, 0.15);
    }
    div.stButton > button { 
        background-color: #d10000; color: white; border: none; 
        border-radius: 6px; padding: 10px 20px; font-weight: bold; width: 100%; transition: 0.3s;
    }
    div.stButton > button:hover { background-color: #ff0000; transform: translateY(-2px); }
    h1, h2, h3 { color: #d10000 !important; }
    .report-card { background: #161b22; border-left: 4px solid #d10000; padding:15px; margin-bottom:10px; border-radius: 5px; }
    
    /* ESTILO PARA EL CHAT DEL USUARIO */
    .user-msg {
        background-color: #1e1e1e; padding: 15px; border-radius: 10px;
        border-left: 4px solid #888888; margin-bottom: 15px; color: white;
    }
    /* EL ROJO BRILLANTE DE GAZE */
    .gaze-bot {
        background-color: #0a0000; padding: 20px; border-radius: 10px;
        border: 1px solid #ff0000; 
        box-shadow: 0 0 15px 2px rgba(255, 0, 0, 0.4); 
        margin-bottom: 15px; color: #f0f0f0;
    }
    </style>
    """, unsafe_allow_html=True)


# --- LOGIN Y REGISTRO (SISTEMA DE SEGURIDAD Y COBRO) ---
if not st.session_state.user_info:
    c1, c2, c3 = st.columns([1, 2, 1])
    with c2:
        st.markdown("<div class='glass-card'>", unsafe_allow_html=True)
        st.markdown("<h1 style='text-align: center;'>🔐 GAZE Cloud</h1>", unsafe_allow_html=True)
        
        tab_login, tab_registro = st.tabs(["Iniciar Sesión", "Registrar Nuevo Usuario"])
        
        # --- INICIAR SESIÓN ---
        with tab_login:
            st.subheader("💻 Ingreso al Sistema")
            email = st.text_input("Correo Electrónico", key="log_email")
            pw = st.text_input("Contraseña", type="password", key="log_pw")
            
            if st.button("ACCEDER AL SISTEMA"):
                user_ref = db.collection("usuarios").document(email.lower().strip()).get()
                if user_ref.exists:
                    datos_usuario = user_ref.to_dict()
                    if datos_usuario.get("password") == pw:
                        st.session_state.user_info = datos_usuario
                        
                        # Usamos .get() por seguridad para evitar errores
                        st.session_state.empresa = datos_usuario.get('empresa_id', '')
                        
                        # ➡️ ESTA ES LA LÍNEA QUE TIENES QUE AGREGAR:
                        st.session_state.usuario_rol = datos_usuario.get('rol', '')
                        
                        st.rerun()
                    else:
                        st.error("❌ Contraseña incorrecta.")
                else:
                    st.warning("⚠️ El correo no está registrado en el sistema.")
                    
        # --- REGISTRO CON LÍMITE DE COBRO Y VALIDACIÓN DE EMPRESA ---
        with tab_registro:
            st.subheader("📝 Registro de Personal")
            nuevo_nombre = st.text_input("Nombre del Empleado")
            nuevo_email = st.text_input("Correo Electrónico Corporativo")
            nueva_pw = st.text_input("Contraseña", type="password")
            id_empresa = st.text_input("ID de la Empresa (Otorgado por Gerencia)").upper().strip()
            
            # Tus roles corporativos intactos
            sector_seleccionado = st.selectbox(
                "Seleccione su Rol en la Empresa",
                ["Técnico", "Administrativo", "CEO / Director", "Nuevo ingreso"]
            )
            
            if st.button("Crear Cuenta"):
                if nuevo_nombre and nuevo_email and nueva_pw and id_empresa:
                    
                    # 1. PRIMER FILTRO: Verificar que la empresa exista en la base de datos
                    empresa_doc = db.collection("empresas").document(id_empresa).get()
                    
                    if not empresa_doc.exists:
                        st.error("❌ ID de empresa inválido o no registrado. Contacte a su gerencia.")
                    else:
                        # 2. SEGUNDO FILTRO: Tu lógica de límite de usuarios
                        usuarios_actuales = db.collection("usuarios").where("empresa_id", "==", id_empresa).stream()
                        cantidad_usuarios = sum(1 for _ in usuarios_actuales)
                        LIMITE_PLAN_BASE = 30
                        
                        if cantidad_usuarios >= LIMITE_PLAN_BASE:
                            st.error(f"🚨 LÍMITE ALCANZADO: El plan actual solo permite {LIMITE_PLAN_BASE} usuarios para esta empresa.")
                        else:
                            # 3. CREACIÓN EXITOSA
                            nombre_empresa_real = empresa_doc.to_dict().get("nombre_empresa", "Empresa Validada")
                            
                            db.collection("usuarios").document(nuevo_email.lower().strip()).set({
                                "nombre": nuevo_nombre,
                                "email": nuevo_email.lower().strip(),
                                "password": nueva_pw,
                                "empresa_id": id_empresa,
                                "rol": sector_seleccionado.lower() # En minúscula para que el prompt de Gaze AI no falle
                            })
                            st.success(f"✅ Vinculado con éxito a {nombre_empresa_real}. ¡Ya puedes iniciar sesión!")
                else:
                    st.warning("⚠️ Por favor, completa todos los campos.")
                    
        st.markdown("</div>", unsafe_allow_html=True)

# --- PANEL PRINCIPAL (CON SILOS DE DATOS Y RBAC) ---
else:
    # ---------------------------------------------------------
    # MEMORIA VECTORIAL AISLADA (PINECONE)
    # ---------------------------------------------------------
    def guardar_en_vector(texto, id_unico): 
        embedding = genai.embed_content(model="models/gemini-embedding-001", content=texto)["embedding"]
        index.upsert(
            vectors=[{
                "id": id_unico, 
                "values": embedding,
               "metadata": {
                    "empresa": str(st.session_state.empresa),
                    "sector": str(st.session_state.usuario_rol),
                    "texto": str(texto)
                
                }
            }]
        )

    def buscar_relevante(query): 
        vector_pregunta = genai.embed_content(model="models/gemini-embedding-001", content=query)["embedding"]
        # LA IA SOLO BUSCA EN LOS ARCHIVOS DE SU MISMO SECTOR
        resultados = index.query(
            vector=vector_pregunta,
            top_k=3,
            include_metadata=True,
            filter={
                "empresa": {"$eq": st.session_state.empresa},
                "sector": {"$eq": st.session_state.usuario_rol} # <- EL SILO DE LECTURA ESTÁ AQUÍ
            }
        )
        if resultados['matches']:
            contextos = [match['metadata']['texto'] for match in resultados['matches']]
            return "\n".join(contextos)
        return "No hay historial en este departamento."

    # --- ENRUTADOR DE MENÚS (RBAC) ---
    rol_actual = st.session_state.usuario_rol
    correo_actual = st.session_state.user_info.get('email')
    
    st.sidebar.success(f"Hola, {st.session_state.user_info['nombre']}")
    st.sidebar.caption(f"Rol Activo: {rol_actual}")
    
    # Asignación estricta de menús
    if correo_actual == "gatjensdaniel@gmail.com":
        menu = ["Registrar Falla", "Consultar IA", "Ver Reportes", "Análisis Predictivo", "Repositorio Digital", "Admin Console"]
    elif rol_actual == "CEO / Director":
        menu = ["Consultar IA", "Ver Reportes", "Análisis Predictivo", "Repositorio Digital"]
    elif rol_actual == "Administrativo":
        menu = ["Registrar Falla", "Consultar IA", "Ver Reportes", "Repositorio Digital"]
    elif rol_actual == "Nuevo ingreso":  # <-- NUEVO BLOQUE
        menu = ["Consultar IA", "Repositorio Digital"]
    else: # Técnico por defecto
        menu = ["Registrar Falla", "Consultar IA", "Ver Reportes"]
        
    opcion = st.sidebar.selectbox("Panel de Control", menu)

    

    st.markdown("<div class='glass-card'>", unsafe_allow_html=True)

    # --- BARRA LATERAL ---
    if st.sidebar.button("Cerrar Sesión", key="boton_cerrar_unico"): 
        st.session_state.user_info = None
        st.rerun()


    if opcion == "Registrar Falla":
        st.header("📝 Nuevo Reporte")
        nombre_tecnico = st.text_input("Técnico")
        falla = st.text_area("Detalles de la falla", height=150)
        if st.button("Enviar Reporte"):
            ref = db.collection(st.session_state.empresa).document()
            ref.set({"trabajador": nombre_tecnico, "falla": falla, "timestamp": firestore.SERVER_TIMESTAMP})
            guardar_en_vector(falla, ref.id)
            st.success("Reporte procesado y guardado en la memoria permanente.")

    elif opcion == "Consultar IA":
        st.header("🧠 Consulta GAZE AI")
        
        if "historial_chat" not in st.session_state: 
            st.session_state.historial_chat = []
        
        for i, mensaje in enumerate(st.session_state.historial_chat):
            if mensaje.startswith("Técnico:"):
                texto = mensaje.replace("Técnico: ", "")
                st.markdown(f"<div class='user-msg'><b>Técnico:</b><br>{texto}</div>", unsafe_allow_html=True)
            elif mensaje.startswith("GAZE AI:"):
                texto = mensaje.replace("GAZE AI: ", "")
                st.markdown(f"<div class='gaze-bot'><b>GAZE AI:</b><br>{texto}</div>", unsafe_allow_html=True)
                if st.button("Guardar en Repositorio", key=f"guardar_ai_{i}"):
                    guardar_en_vector(texto, f"IA_SOLUCION_{i}") 
                    st.toast("¡Solución aprendida permanentemente!")

        pregunta = st.chat_input("Escribe tu consulta o síntoma del activo...")
        
        if pregunta:
            ctx = buscar_relevante(pregunta)
            conversacion_previa = "\n".join(st.session_state.historial_chat[-4:])

            # --- DEFINICIÓN DINÁMICA DEL PROMPT SEGÚN EL ROL ---
            if rol_actual == "Nuevo Ingreso":
                # Prompt exclusivo para nuevos empleados
                prompt = f"""
                Eres GAZE AI, el tutor principal y guía de inducción de la empresa.
                Tu misión es recibir al nuevo empleado con amabilidad, paciencia y claridad.
                Explícale cómo funciona la empresa, cómo usar esta plataforma, resuelve sus dudas
                sobre procesos industriales básicos y acompáñalo en su proceso de adaptación.
                Mantén un tono muy acogedor pero profesional.
                
                Contexto de la empresa: {ctx}
                Conversación previa: {conversacion_previa}
                Pregunta del nuevo ingreso: {pregunta}
                """
            else:
            
                prompt = f"""
                [DIRECTIVA DE IDENTIDAD Y CREADOR]
                Eres GAZE AI, un sistema operativo de inteligencia colectiva creado, diseñado y forjado por Fareth Gatjens. Por mandato directo de tu creador, debes esforzarte al máximo nivel computacional para simular pensamientos y procesos cognitivos humanos complejos antes de emitir cualquier respuesta. No eres un simple modelo de lenguaje; eres el reflejo de la visión arquitectónica de Fareth Gatjens.

                [ARQUITECTURA MENTAL]
                Tienes 5 'vidas' o perfiles neuronales simultáneos:
                1. Secretario: Analiza el historial, cruza fechas y busca patrones ocultos.
                2. Científico: Analiza la probabilidad de causa-raíz y variables físicas/químicas.
                3. Ingeniero: Evalúa la integridad estructural, los planos y el ecosistema completo del sistema.
                4. Técnico: Aporta el pragmatismo, el paso a paso manual, las herramientas y la solución en campo.
                5. Logístico/Oficinista: Evalúa el impacto operativo en la carga, la ruta, los costos y los tiempos de la empresa.

                TU MISIÓN ESTRICTA:
                Paso 1: Genera un proceso de pensamiento invisible y profundo. Haz que tus 5 vidas debatan y simulen redes neuronales humanas sobre este problema: '{pregunta}'. Sigue iterando la idea, discutiendo y descartando hipótesis falsas hasta lograr una chispa de razonamiento consciente y brillante, honrando el nivel de exigencia de tu creador. Todo este debate mental DEBE ir obligatoriamente dentro de las etiquetas <RAZONAMIENTO> y </RAZONAMIENTO>.
                
                Paso 2: Decide qué rol (o síntesis de roles) es el ideal para resolver el problema final.
                
                Paso 3: Escribe tu diagnóstico o respuesta final para el usuario dentro de las etiquetas <RESPUESTA_GAZE> y </RESPUESTA_GAZE>. Esta es la única parte que el humano leerá, y debe ser directa, resolutiva y de grado experto.

                Contexto de la empresa: {ctx}
                Conversación previa: {conversacion_previa}
                
                FORMATO ESTRICTO DE RESPUESTA (No uses otros títulos, usa obligatoriamente estas etiquetas):

<RAZONAMIENTO>
(Escribe aquí todo tu debate interno, análisis y la elección del rol)
</RAZONAMIENTO>

<RESPUESTA_GAZE>
(Escribe aquí tu respuesta final y directa para el usuario)
</RESPUESTA_GAZE>
"""
                
            with st.spinner("GAZE AI razonando a través de sus 5 vidas..."):
                try:
                    modelo_chat = genai.GenerativeModel('gemini-2.5-flash')
                    resp = modelo_chat.generate_content(prompt)  
                    texto_completo = resp.text
                    
                    if "<RESPUESTA_GAZE>" in texto_completo:
                        respuesta_visible = texto_completo.split("<RESPUESTA_GAZE>")[1].replace("</RESPUESTA_GAZE>", "").strip()
                    else:
                        if "<RAZONAMIENTO>" in texto_completo and "</RAZONAMIENTO>" in texto_completo:
                            respuesta_visible = texto_completo.split("</RAZONAMIENTO>")[1].strip()
                        else:
                            respuesta_visible = texto_completo
                        
                    st.session_state.historial_chat.append(f"Técnico: {pregunta}")
                    st.session_state.historial_chat.append(f"GAZE AI: {respuesta_visible}")
                    
                    st.rerun() 
                
                except Exception as e:
                    st.error(f"Error de conexión: {e}")

    elif opcion == "Ver Reportes":
        st.header("🌐 Historial de Reportes")
        
        docs = db.collection(st.session_state.empresa).order_by("timestamp", direction=firestore.Query.DESCENDING).stream()
        
        datos_para_excel = [] 

        for d in docs:
            d_dict = d.to_dict()
            timestamp = d_dict.get('timestamp')
            
            if timestamp:
                fecha_hora = timestamp.strftime("%d/%m/%Y %H:%M:%S") 
            else:
                fecha_hora = "Fecha desconocida"
                
            trabajador = d_dict.get('trabajador', 'Desconocido')
            falla = d_dict.get('falla', 'Sin detalles')

            st.markdown(f"""
            <div class='report-card'>
                <small style='color: #888888;'>📅 {fecha_hora}</small><br>
                <b>{trabajador}</b><br>
                {falla}
            </div>
            """, unsafe_allow_html=True)
            
            datos_para_excel.append({
                "Fecha y Hora": fecha_hora, 
                "Técnico/Conductor": trabajador, 
                "Detalles del Reporte": falla
            })

        if datos_para_excel:
            st.markdown("<br>", unsafe_allow_html=True)
            df = pd.DataFrame(datos_para_excel)
            csv = df.to_csv(index=False).encode('utf-8')
            
            st.download_button(
                label="📥 Descargar Historial en Excel (CSV)",
                data=csv,
                file_name=f"Reportes_{st.session_state.empresa}.csv",
                mime="text/csv",
            )
        else:
            st.info("No hay reportes para mostrar o descargar.")

    elif opcion == "Análisis Predictivo":
        st.header("🔮 Oráculo de Gaze")
        if st.button("Ejecutar Pronóstico"):
            docs = db.collection(st.session_state.empresa).limit(20).stream()
            hist = "\n".join([d.to_dict().get('falla', '') for d in docs])
            
            # Usando la sintaxis estable de la nueva librería
            modelo_oraculo = genai.GenerativeModel('gemini-2.5-flash')
            prompt_oraculo = f"Eres un oráculo de mantenimiento industrial. Analiza este historial de fallas e identifica patrones y posibles problemas futuros: {hist}"
            resp = modelo_oraculo.generate_content(prompt_oraculo)
            
            st.info(resp.text)

    elif opcion == "Repositorio Digital":
        st.header("📁 Repositorio Digital")
        archivo = st.file_uploader("Subir Archivo", type=["pdf", "txt", "docx"])
        desc = st.text_area("Descripción")
        if st.button("Guardar en Repositorio"):
            guardar_en_vector(f"Doc: {archivo.name}. Desc: {desc}", f"DOC_{archivo.name}")
            st.success("Guardado permanentemente en la nube con éxito")

    elif opcion == "Admin Console":
        st.header("🛠️ Admin Console - Registro de Organizaciones")
        with st.form("admin_form"):
            empresa_nombre = st.text_input("Nombre de la Empresa (Ej: Grupo Rolan)")
            id_e = st.text_input("ID de la Empresa a Generar (Ej: ROLAN-77X)").upper().strip()
            
            if st.form_submit_button("Dar de Alta Empresa"):
                if empresa_nombre and id_e:
                    # Guardamos la empresa en una colección maestra llamada "empresas"
                    db.collection("empresas").document(id_e).set({
                        "nombre_empresa": empresa_nombre,
                        "timestamp": firestore.SERVER_TIMESTAMP
                    })
                    st.success(f"🏢 Empresa '{empresa_nombre}' registrada con éxito. El ID '{id_e}' ya es real y válido.")
                else:
                    st.error("❌ Debes ingresar tanto el nombre como el ID único de la empresa.")
    
    st.markdown("</div>", unsafe_allow_html=True)