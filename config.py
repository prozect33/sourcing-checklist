import os
import json
import streamlit as st

DEFAULT_CONFIG_FILE = "default_config.json"
default_config = {
    "FEE_RATE": 10.8,
    "AD_RATE": 20.0,
    "INOUT_COST": 3000,
    "PICKUP_COST": 1500,
    "RESTOCK_COST": 500,
    "RETURN_RATE": 0.1,
    "ETC_RATE": 2.0,
    "EXCHANGE_RATE": 350,
    "PACKAGING_COST": 500,
    "GIFT_COST": 0
}

def save_config(cfg: dict) -> None:
    with open(DEFAULT_CONFIG_FILE, "w") as f:
        json.dump(cfg, f)

@st.cache_data
def load_config(file_mtime: float) -> dict:
    """
    file_mtime를 키로 설정 파일을 캐시합니다.
    기본값(json) 읽기 실패 시 default_config 복사본을 반환.
    """
    if os.path.exists(DEFAULT_CONFIG_FILE):
        try:
            with open(DEFAULT_CONFIG_FILE, "r") as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError):
            return default_config.copy()
    else:
        return default_config.copy()
