import streamlit as st
import cv2
import numpy as np
import easyocr
import requests
import re
import pandas as pd
from datetime import datetime

st.set_page_config(page_title="Barão Geek Vision", layout="centered")

st.title("🧙‍♂️ Barão Geek - Scanner Pro")
st.write("Protótipo de Triagem Automatizada: Magic, Pokémon e Lorcana")

if "estoque" not in st.session_state:
    st.session_state.estoque = []

@st.cache_resource
def carrega_ocr():
    return easyocr.Reader(['en'])

reader = carrega_ocr()

# --- FUNÇÕES DE BUSCA NAS APIS ---

def buscar_magic(set_code, number):
    url = f"https://api.scryfall.com/cards/{set_code.lower()}/{number}"
    res = requests.get(url)
    if res.status_code == 200:
        d = res.json()
        return {"Jogo": "Magic", "Nome": d.get("name"), "Edição/Set": set_code.upper(), "Número": number, "Raridade": d.get("rarity").upper()}
    return None

def buscar_pokemon(set_code, number):
    url = f"https://api.pokemontcg.io/v2/cards?q=set.id:{set_code.lower()} number:{number}"
    res = requests.get(url)
    if res.status_code == 200:
        data = res.json()
        if data.get("data"):
            card = data["data"][0]
            return {"Jogo": "Pokémon", "Nome": card.get("name"), "Edição/Set": set_code.upper(), "Número": number, "Raridade": card.get("rarity", "Comum").upper()}
    return None

def buscar_lorcana(card_number, set_number):
    # Consulta a API pública de Lorcana filtrando pelo número da carta e do set
    url = f"https://api.lorcana-api.com/cards/fetch?id={set_number}-{card_number}"
    # Nota: Caso a API exija formato diferente, usamos busca por texto ou número estruturado
    url_alt = f"https://api.lorcana-api.com/cards/all" # Backup para filtragem local se necessário
    
    res = requests.get(url)
    if res.status_code == 200:
        data = res.json()
        # Se retornar uma lista ou objeto válido
        if isinstance(data, list) and len(data) > 0:
            card = data[0]
            return {"Jogo": "Lorcana", "Nome": card.get("Name"), "Edição/Set": f"Set {set_number}", "Número": card_number, "Raridade": card.get("Rarity", "UNKNOWN").upper()}
        elif isinstance(data, dict) and "Name" in data:
            return {"Jogo": "Lorcana", "Nome": data.get("Name"), "Edição/Set": f"Set {set_number}", "Número": card_number, "Raridade": data.get("Rarity", "UNKNOWN").upper()}
    return None

# --- CAPTURA DA CÂMERA ---

# Abre a câmera nativa do celular com qualidade máxima ao clicar
foto_upload = st.file_input("Tire uma foto bem de perto do rodapé esquerdo", type=["jpg", "jpeg", "png"])


if foto_upload is not None:
    bytes_data = foto_upload.getvalue()
    cv2_img = cv2.imdecode(np.frombuffer(bytes_data, np.uint8), cv2.IMREAD_COLOR)
    
    h, w, _ = cv2_img.shape
    recorte = cv2_img[int(h*0.7):h, 0:w]
    
    with st.spinner("Analisando rodapé da carta..."):
        result = reader.readtext(recorte, detail=0)
        texto = " ".join(result).upper()
        
        # 1. TESTA PADRÃO LORCANA (Ex: 102/204 EN 4 ou 102/204 EN·4)
        padrao_lorcana = re.search(r'([0-9]{1,3})\s*/\s*[0-9]{3}.*EN.*?([0-9]{1,2})', texto)
        
        # 2. TESTA PADRÃO TRADICIONAL (Magic/Pokémon - Ex: MH3 052)
        padrao_geral = re.search(r'([A-Z0-9]{3,4})\s+([0-9]{3,4})', texto)
        
        carta = None
        
        if padrao_lorcana:
            num_card, num_set = padrao_lorcana.group(1), padrao_lorcana.group(2)
            st.info(f"Detectado padrão Lorcana -> Card: {num_card} | Set: {num_set}")
            carta = buscar_lorcana(num_card, num_set)
            
        elif padrao_geral:
            set_code, num_card = padrao_geral.group(1), padrao_geral.group(2)
            # Tenta Magic, se não der, tenta Pokémon
            carta = buscar_magic(set_code, num_card)
            if not carta:
                carta = buscar_pokemon(set_code, num_card)
        
        # --- RESULTADO ---
        if carta:
            if not any(c['Nome'] == carta['Nome'] and c['Número'] == carta['Número'] for c in st.session_state.estoque):
                st.session_state.estoque.append(carta)
            st.success(f"🎉 [{carta['Jogo']}] Encontrado: {carta['Nome']} ({carta['Raridade']})")
        else:
            st.error(f"Não consegui identificar na API. Texto lido no rodapé: '{texto}'. Tente focar melhor.")

# --- EXIBIÇÃO E EXPORTAÇÃO ---
if st.session_state.estoque:
    st.subheader("📋 Lote de Boosters Aberto (Trindade TCG)")
    df = pd.DataFrame(st.session_state.estoque)
    st.dataframe(df)
    
    csv = df.to_csv(index=False).encode('utf-8')
    st.download_button(
        label="📥 Baixar CSV para o Sistema da Loja",
        data=csv,
        file_name=f"lote_barao_trindade_{datetime.now().strftime('%d-%m-%Y')}.csv",
        mime="text/csv",
    )
