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

try:
    reader = carrega_ocr()
except Exception as e:
    st.error(f"Erro ao inicializar IA de leitura: {e}")

# --- FUNÇÕES DE BUSCA ---
def buscar_magic(set_code, number):
    try:
        url = f"https://api.scryfall.com/cards/{set_code.lower()}/{number}"
        res = requests.get(url, timeout=5)
        if res.status_code == 200:
            d = res.json()
            return {"Jogo": "Magic", "Nome": d.get("name"), "Edição/Set": set_code.upper(), "Número": number, "Raridade": d.get("rarity").upper()}
    except:
        pass
    return None

def buscar_pokemon(set_code, number):
    try:
        url = f"https://api.pokemontcg.io/v2/cards?q=set.id:{set_code.lower()} number:{number}"
        res = requests.get(url, timeout=5)
        if res.status_code == 200:
            data = res.json()
            if data.get("data"):
                card = data["data"][0]
                return {"Jogo": "Pokémon", "Nome": card.get("name"), "Edição/Set": set_code.upper(), "Número": number, "Raridade": card.get("rarity", "Comum").upper()}
    except:
        pass
    return None

def buscar_lorcana(card_number, set_number):
    try:
        url = f"https://api.lorcana-api.com/cards/fetch?id={set_number}-{card_number}"
        res = requests.get(url, timeout=5)
        if res.status_code == 200:
            data = res.json()
            if isinstance(data, list) and len(data) > 0:
                card = data[0]
                return {"Jogo": "Lorcana", "Nome": card.get("Name"), "Edição/Set": f"Set {set_number}", "Número": card_number, "Raridade": card.get("Rarity", "UNKNOWN").upper()}
            elif isinstance(data, dict) and "Name" in data:
                return {"Jogo": "Lorcana", "Nome": data.get("Name"), "Edição/Set": f"Set {set_number}", "Número": card_number, "Raridade": data.get("Rarity", "UNKNOWN").upper()}
    except:
        pass
    return None

# --- COMPONENTE DE UPLOAD ---
foto_upload = st.file_uploader("Tire uma foto bem de perto do rodapé esquerdo", type=["jpg", "jpeg", "png"])

if foto_upload is not None:
    st.image(foto_upload, caption="Imagem carregada", width=300)
    
    if st.button("🚀 Processar e Escanear Carta"):
        try:
            bytes_data = foto_upload.getvalue()
            nparr = np.frombuffer(bytes_data, np.uint8)
            cv2_img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
            
            if cv2_img is None:
                st.error("Falha ao processar o formato da imagem. Remova o arquivo e tente tirar outra foto.")
            else:
                h, w, _ = cv2_img.shape
                
                # Try-catch no recorte para evitar crashes caso as dimensões sejam estranhas
                try:
                    # Tenta focar nos 40% inferiores da imagem
                    recorte = cv2_img[int(h*0.6):h, 0:w]
                    if recorte.size == 0:
                        recorte = cv2_img
                except:
                    recorte = cv2_img
                
                with st.spinner("A IA está analisando a imagem..."):
                    result = reader.readtext(recorte, detail=0)
                    texto = " ".join(result).upper()
                    
                    # Regex flexível para espaçamentos variados
                    padrao_lorcana = re.search(r'([0-9]{1,3})\s*/\s*[0-9]{3}.*EN.*?([0-9]{1,2})', texto)
                    padrao_geral = re.search(r'([A-Z0-9]{3,4})\s+([0-9]{3,4})', texto)
                    
                    carta = None
                    
                    if padrao_lorcana:
                        num_card, num_set = padrao_lorcana.group(1), padrao_lorcana.group(2)
                        st.info(f"Padrão Lorcana detectado -> Card: {num_card} | Set: {num_set}")
                        carta = buscar_lorcana(num_card, num_set)
                        
                    elif padrao_geral:
                        set_code, num_card = padrao_geral.group(1), padrao_geral.group(2)
                        st.info(f"Padrão Geral detectado -> Código: {set_code} | Número: {num_card}")
                        carta = buscar_magic(set_code, num_card)
                        if not carta:
                            carta = buscar_pokemon(set_code, num_card)
                    
                    if carta:
                        if not any(c['Nome'] == carta['Nome'] and c['Número'] == carta['Número'] for c in st.session_state.estoque):
                            st.session_state.estoque.append(carta)
                        st.success(f"🎉 [{carta['Jogo']}] Encontrado: {carta['Nome']} ({carta['Raridade']})")
                    else:
                        st.error(f"Não encontramos esse card na API.")
                        st.text_area("Texto cru lido pela IA (Útil para debugar):", value=texto)
                        
        except Exception as main_error:
            st.error(f"Ocorreu um erro inesperado ao ler o arquivo: {main_error}")

# --- EXIBIÇÃO DA TABELA ---
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
