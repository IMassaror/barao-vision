
import streamlit as st
import cv2
import numpy as np
import easyocr
import requests
import re
import pandas as pd
from datetime import datetime

# Configuração da página para Mobile
st.set_page_config(page_title="Barão Geek Vision", layout="centered")

st.title("🧙‍♂️ Barão Geek - Scanner Pro")
st.write("Protótipo de Triagem Automatizada para TCG")

# Inicializa o estado do app para guardar as cartas na memória da sessão
if "estoque" not in st.session_state:
    st.session_state.estoque = []

# Inicializa o motor de OCR (Usa cache do Streamlit para não carregar toda hora)
@st.cache_resource
def carrega_ocr():
    return easyocr.Reader(['en'])

reader = carrega_ocr()

def buscar_carta(set_code, number):
    # Tenta Magic primeiro
    url = f"https://api.scryfall.com/cards/{set_code.lower()}/{number}"
    res = requests.get(url)
    if res.status_code == 200:
        d = res.json()
        return {"Jogo": "Magic", "Nome": d.get("name"), "Edição": set_code.upper(), "Número": number, "Raridade": d.get("rarity").upper()}
    return None

# Componente que ativa a Câmera do Celular nativamente no navegador
foto_upload = st.camera_input("Aponte para o rodapé esquerdo da carta")

if foto_upload is not None:
    # Processa a imagem enviada
    bytes_data = foto_upload.getvalue()
    cv2_img = cv2.imdecode(np.frombuffer(bytes_data, np.uint8), cv2.IMREAD_COLOR)
    
    # Recorta a parte inferior onde fica o rodapé
    h, w, _ = cv2_img.shape
    recorte = cv2_img[int(h*0.7):h, 0:w]
    
    # Executa a IA
    with st.spinner("Analisando rodapé da carta..."):
        result = reader.readtext(recorte, detail=0)
        texto = " ".join(result).upper()
        
        # Procura o padrão de Letras + Números (ex: MH3 052)
        padrao = re.search(r'([A-Z0-9]{3,4})\s+([0-9]{3,4})', texto)
        
        if padrao:
            set_code, num_card = padrao.group(1), padrao.group(2)
            carta = buscar_carta(set_code, num_card)
            
            if carta:
                # Evita duplicar a mesma carta na mesma batida de foto
                if not any(c['Nome'] == carta['Nome'] and c['Número'] == carta['Número'] for c in st.session_state.estoque):
                    st.session_state.estoque.append(carta)
                st.success(f"🎉 Encontrado: {carta['Nome']} ({carta['Raridade']})")
            else:
                st.warning(f"Código detectado ({set_code} {num_card}), mas não encontrado no banco de dados. Tente focar melhor.")
        else:
            st.error(f"Não consegui isolar o código. Texto lido: '{texto}'. Aproxime mais o rodapé.")

# Exibe a tabela do lote atual na tela do celular
if st.session_state.estoque:
    st.subheader("📋 Lote de Boosters Aberto")
    df = pd.DataFrame(st.session_state.estoque)
    st.dataframe(df)
    
    # Botão mágico de Download do CSV para o sistema da loja
    csv = df.to_csv(index=False).encode('utf-8')
    st.download_button(
        label="📥 Baixar CSV para o Sistema da Loja",
        data=csv,
        file_name=f"lote_barao_geek_{datetime.now().strftime('%d-%m-%Y')}.csv",
        mime="text/csv",
    )
